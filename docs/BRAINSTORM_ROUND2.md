# Brainstorm, round 2

An independent second pass at the design, written after `DESIGN_BRAINSTORM.md` and by a different
model. It is kept separate rather than merged so the two passes can be compared. Where it disagrees
with round 1, it says so.

Round 1's core claim was: move to next-best-step prediction, take the gold from the case's real
trajectory, score against medical code sets, and both of v1's fatal problems go away. I agree with the
task change. I think the two mechanisms round 1 proposed for fixing the problems are weaker than it
claims, and there are two threats it does not address at all.

## 1. "The real trajectory is the gold" is behavior cloning

Round 1 treats the gap between "what the team did" and "what was best" as a caveat to be reported. I
think it is the central design problem.

Published case reports are a biased sample of trajectories:

- They are published *because* something was unusual. A common reason for publication is that the
  workup was circuitous — the team chased the wrong thing for a while. So the real trajectory
  contains genuinely bad next steps, and a trajectory-anchored metric rewards reproducing them.
- They are written retrospectively, so the order in the text is the order that tells the story well,
  not the order in which orders were placed.
- The trajectory encodes the resources and habits of one institution. What an academic center did
  next is not what a community hospital did next, and neither is "the best next step."

A metric anchored to the sequence therefore measures "can the model predict what this team did." That
is behavior cloning of median practice, and a model that is better than the team gets penalized. That
is not a caveat, it is a ceiling on what the benchmark can ever show.

**The fix I would use: grade by information yield, not by sequence position.**

Round 1 grades actions by *when* they appear (immediate next = full credit, later = decaying partial
credit). Position decay is arbitrary and it rewards mimicry of order.

But every action in a case report has a *result*, and the text says what that result did. Some results
narrowed the differential. Some ruled out the leading hypothesis. One of them clinched the diagnosis.
Some changed nothing. That is stated in the source, it is not a matter of taste, and it is the thing
we actually care about.

So grade actions by what their results did:

| Tier | Definition | Grounding |
| --- | --- | --- |
| 3 | The action whose result established the diagnosis | Stated in the source |
| 2 | An action whose result meaningfully changed the differential | Stated in the source |
| 1 | An action taken whose result was normal, non-contributory, or confirmatory only | Stated in the source |
| 0 | Not taken in this case | — |

This is still trajectory-anchored, so it keeps round 1's real advantage — the answer is extracted, not
invented. But it stops rewarding the low-yield detours that got the case published in the first place,
and it separates "what they did" from "what worked," which is the distinction that makes the metric
about medicine instead of about mimicry.

## 2. Ontology mapping reintroduces the judge one layer down

Round 1 rests its measurement claim on mapping predictions and golds to LOINC, CPT/SNOMED, and RxNorm.
It lists mapping reliability as open question #2. I think it is closer to a load-bearing assumption
that does not hold.

The model outputs free text: "MRI brain with and without contrast," "send autoimmune encephalitis
antibodies," "check a paraneoplastic panel." Turning that into a code is itself a fuzzy language task.
If an LLM does it, the judge is back — just one layer down, and now invisible, because it is buried in
a preprocessing step nobody reports the error rate of. That is the v1 mistake wearing a different hat.

There is also a granularity problem. Is "LP" the same action as "LP with opening pressure, cell count,
protein, glucose, cytology, and an autoimmune panel"? Different codes, clinically the same decision.
Exact code matching will be strict in ways that do not track clinical equivalence, and loose matching
needs a similarity threshold, which is a knob, which is where results go to get tuned.

Also worth saying plainly: LOINC, CPT and SNOMED are built for billing and lab interfacing. They are
enormous and their granularity is designed around reimbursement, not around how a clinician thinks
about "what to do next."

**The fix I would use: a small closed action vocabulary, hand-curated.**

Roughly 200–400 action classes at the granularity a clinician would actually name — "lumbar puncture,"
"brain MRI with contrast," "EEG," "anti-NMDAR antibody testing," "muscle biopsy," "start empiric
acyclovir." Build it once for the target specialties. Map to standard codes later if it is ever needed
for interoperability, but do not make the metric depend on it.

A closed vocabulary is small enough to audit by hand, coarse enough that mapping is reliable, and it
makes the next idea possible.

## 3. Add a ranking task next to the generation task

This is the largest thing I would add.

Free-text generation is the realistic task but it is the hard one to score. Ranking a fixed candidate
set is the easy one to score — it is exactly, trivially deterministic, with no mapping step at all.

For each decision point, build a candidate slate of maybe 10–15 actions:

- the action actually taken next,
- the pivotal action from later in the case,
- other actions taken in the case,
- **hard negatives**: actions taken at similar decision points in *other* cases with overlapping
  presentations — plausible, commonly ordered, wrong here,
- low-yield distractors.

The model ranks the slate. Score with graded relevance (nDCG) against the tiers from §1. No judge, no
ontology, no threshold. The scoring code is twenty lines and it is auditable by eye.

Run both tasks. Ranking is the reliable primary metric; generation is the realistic secondary one.
Then check whether they agree. If model ordering under the two tasks correlates, the cheap metric is
trustworthy and can be used for iteration. If they diverge, that divergence is itself a finding worth
publishing, and it is one v1 could never have produced.

The hard negatives are what make this non-trivial, and they are the part to spend effort on.

## 4. State construction is still the number one risk

Round 1 says the pivot "attacks the circular construction problem" because the answer is no longer
invented. That is half right. The *answer* is extracted. But constructing "the state at step k" is
still constructing a self-contained puzzle, and that is the thing that killed v1.

Case reports do not mark what was known when. Facts obtained on day 3 appear in the opening paragraph.
The history of present illness is written with hindsight — "a 34-year-old woman with no history of
travel" tells you someone already thought travel mattered, which is a leak about the differential.
Redacting later results does not remove that.

So this belongs at the top of the risk list, not in a subsection near the end.

**Prefer sources that are natively chronological.** If the document is already ordered in time, the
segmentation step mostly disappears:

- Clinicopathological conference transcripts are structured as "here is what we knew, here is what we
  did next," which is the format this benchmark wants.
- Structured EHR data has real timestamps on real orders. There is no narration and no hindsight.

On that second point, **MIMIC-IV deserves an explicit mention and an explicit rejection for the
headline benchmark.** It is the obvious suggestion and it does solve segmentation completely. But its
data use agreement restricts sending records to third-party model APIs, which is exactly what a
cross-model comparison requires; and it is long since public and heavily written about, so
contamination control is not achievable. It may still be useful for developing the extraction and
scoring code against real timelines before pointing them at case reports.

## 5. Triviality is the threat nobody has costed

For most decision points in most cases, the next step is obvious. Fever and headache, so do an LP.
Every frontier model will get it. If most items are trivial, the metric saturates, and the score is
dominated by noise on the small hard remainder. Whatever else was wrong with v1, its case set was
hard.

This needs to be handled at construction time, and there is a trap: selecting items by model failure
is exactly what v1 did wrong, and it made scoring that model circular.

**Select by disagreement, not by failure.** Pilot every candidate item against several models. Drop
items that all of them get. Keep items where they diverge. Disagreement is not anchored to any single
model's weaknesses, so it does not create the circularity that failure-mining does, and it selects for
exactly the items that carry information about model differences. Report the difficulty distribution,
and report scores stratified by it.

## 6. Predict a budgeted set, not a single action

Round 1 leaves "what counts as one step" open. I would settle it: clinicians order several things at
once, so ask for several. "You may order up to three things. Which three?"

That matches practice, it removes the artificial single-action constraint, and set scoring is a solved
problem — precision at k against the graded tiers. It also makes the cost axis in §7 meaningful,
because a budget forces a real tradeoff.

## 7. Cost and invasiveness are a second axis

A system optimizing only for information will recommend a brain biopsy on day one. Real next-step
decisions trade information against cost, risk, and delay. Attach a coarse cost/invasiveness weight to
each entry in the closed vocabulary — four or five tiers is enough — and report information yield per
unit of risk as a second metric.

This is also the axis on which a harness could show a benefit that has nothing to do with accuracy:
reaching the same diagnostic yield with less invasive testing is a real clinical win and a cleaner
thing to demonstrate than a two-point accuracy gain.

## 8. Scope discipline

v1 died of construction difficulty and API cost. The design above is cheaper than round 1's in
exactly the places that matter — a closed vocabulary instead of ontology mapping, a ranking task
instead of judged free text — but it is still possible to repeat the mistake.

Concretely: 100–150 decision points, hand-curated, one or two specialties. Not 400 cases through an
LLM pipeline. If the small version shows nothing, the large version would not have either.

---

# The harness

## The thesis

v1's actual lesson, stated plainly: **the gains came from how the model was asked, not from what was
fetched.** Multi-sampling beat retrieval. Retrieval that supplied answers competed with the model's
own knowledge and lost. So v2's harness should be primarily a *reasoning decomposition*, with
retrieval in a narrow supporting role — the opposite of the weighting v1 used.

## The idea: decompose next-step selection into value of information

v1's most durable finding was that models rank badly, not that they know badly. The correct diagnosis
was usually somewhere in the top five and often not first. Gemini 3.5 Flash was the extreme case:
mediocre at top-1, near the top at top-5.

That finding has a direct consequence for next-step prediction that I have not seen stated anywhere:

**One-shot next-step prediction inherits the top-1 error.** Ask a model "what next," and it silently
commits to its leading diagnosis and proposes the test that would confirm it. If its leading diagnosis
is wrong but the right one is third on its list, it orders a test that confirms the wrong thing — and
the case goes down the same detour that got the report published.

A good clinician does the opposite: orders the test that *distinguishes* between the live hypotheses.

So decompose:

1. **Enumerate.** Produce the differential with rough probabilities. Models are comparatively good at
   this — it is the top-5 that contains the answer.
2. **Simulate.** For each candidate action, and for each of the top hypotheses, predict what the
   result would be. "If this is autoimmune encephalitis, what does the MRI show? If it is CJD?"
3. **Discriminate.** Choose the action whose predicted results differ most across the leading
   hypotheses, weighted by their probabilities and penalized by cost and invasiveness from §7.

This is value-of-information / Bayesian experimental design, applied to the model's own stated beliefs.

## Why this might work where v1's harness did not

**The verifier question changes from defeasible to factual.** This is the important part. v1 died on
"no sound oracle": a verifier asked "is this diagnosis correct?" is making the same defeasible
judgment as the proposer, so it rubber-stamps. But step 2 asks a different kind of question — "does
this test come back differently under hypothesis A than under hypothesis B?" That is a fact about test
behavior, it is in textbooks, and it is checkable. It is not a clinical judgment about this patient.

That is a real crack in the no-sound-oracle wall. We never get an oracle for the answer. We may get
one for test characteristics, which is all this decomposition needs.

**Retrieval finally has a job it is good at.** Not "find the diagnosis" — that competes with
parametric knowledge and loses, which is exactly what v1 measured. Instead: look up sensitivity and
specificity, and look up the guideline pathway for this presentation. That is reference lookup, which
is what retrieval is actually for. It also explains v1's negative result rather than ignoring it,
which is a better position to argue from.

**It is do-no-harm by construction.** When the differential is narrow and the top hypothesis is
confident, the discrimination term collapses and the method reduces to "confirm it" — the same answer
the base model gives. The scaffold only changes behavior where there is genuine uncertainty, which is
where you want it to act, and it leaves confident correct answers alone. That is v1's one positive
harness result, built into the architecture instead of bolted on.

**It makes a falsifiable prediction before the run.** Gains should concentrate on decision points
where the model's top-1 diagnosis is wrong but the correct one is in its top-5, and should be near
zero elsewhere. That is a pre-registerable hypothesis, and if it fails, the mechanism is wrong even
if the aggregate number happens to improve. v1 had no such prediction, which is why every result was
arguable after the fact.

## Baselines it has to beat

State these before running anything, and expect the first one to be strong.

1. **Zero-shot.** Ask for the next steps directly.
2. **Self-consistency over plans.** Sample N complete workup plans at temperature 0 with varied
   framing, then take the actions that appear earliest and most often. This is v1's elicitation
   lesson applied properly. It is cheap and it may well win; if it does, that is the finding, and it
   should be reported as such rather than buried.
3. **One-extra-call approximation.** "Which of your hypotheses are you most likely to be wrong about?
   Order the test that addresses that." A cheap proxy for the full decomposition. If it captures most
   of the benefit, the expensive version is not worth it.

The full decomposition costs several calls per decision point. It has to earn that against #2 and #3,
not against #1.

## Development discipline

The trajectory is an oracle **at development time only** — we know what actually happened, so we can
honestly measure whether a scaffold's change to the top-ranked action moved it toward or away from the
pivotal step. v1 could never measure this, because it had no ground truth for whether an edit helped.
Use it on the development split; never touch the post-cutoff test split with it.

Everything in `AGENTS.md` still applies: temperature 0.0, persist every response, never re-judge
identical output, exclude the source article, fail loudly.
