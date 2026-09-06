# Clinical Orchestra Two — design brainstorm

Status: brainstorm, not decided. This is the starting point for the next-generation project, built on the
lessons from ClinicalHarness / ClinicalOrchestra (`~/Coding/ClinicalHarness`, write-up published at
santoshguptaml.substack.com/p/my-failed-attempt-at-making-a-medical).

## 1. The pivot: from "final diagnosis" to "next best step"

v1 asked: given a case, what is the diagnosis (ranked differential)? v2 asks: given the case *so far*, what is
the best next step (test, imaging, referral, treatment, etc.)?

A single case study becomes a sequence of decision points. At each point there can be many reasonable next
steps, but some are better than others: the step that matches what actually moved the case forward (or that a
guideline recommends) scores highest; a step that the team also took, but later, gets partial credit; a step
never taken gets little or no credit from the primary metric.

Why this pivot is worth making — it directly attacks the two things that sank v1:

- **It attacks the circular-construction problem.** In v1 the "gold" diagnosis and the whole challenge were
  built *by an LLM*, so challenge quality was capped by the constructor model. In v2 the gold comes from the
  **real trajectory the clinicians actually followed** — the case report already contains the ordered steps
  they took and what each revealed. We extract that structure; we do not invent the answer. The LLM's job
  shrinks from "invent a fair puzzle and its answer" to "segment a real timeline," which is a much smaller,
  more checkable job.
- **It attacks the untrustworthy-measurement problem.** In v1 scoring needed an LLM judge on free-text
  diagnoses, and the judge was noisy even at temperature zero. In v2, **actions are enumerable and codeable**
  (a lab, an imaging study, a procedure, a drug). Map both the prediction and the gold to a controlled
  vocabulary and scoring becomes largely **deterministic** — no LLM judge for the common case.

It is also closer to real clinical usefulness (medicine is sequential decisions, not one guess), and partial
credit is natural (position in the real sequence).

Honest caveat up front: "best next step" is *more* subjective than diagnosis in the abstract — reasonable
doctors disagree. The design below only works because we anchor the score to the case's real trajectory and
to guidelines, and we are explicit about the ceiling (a model that suggests something genuinely better than the
team did will be under-credited). We report that bias rather than hide it.

## 2. The benchmark

### 2.1 Unit of evaluation: (state, next-action) at each decision point

Parse each case into an ordered timeline:

    state_0 (presentation) --action_1--> result_1 --action_2--> result_2 --> ... --> diagnosis --> outcome

- **State at step k** = everything revealed up to and including result_k, with everything after k redacted.
- **Gold next action** = action_{k+1} (what the team actually did next), plus its result.
- One case yields several evaluation items (one per decision point), which is data-efficient.

### 2.2 Ground truth comes from the real trajectory (not an LLM's opinion)

- The primary gold is *what actually happened next*, extracted from the source. This is grounded and auditable
  against the source text.
- **Pivotality / value** also comes from what actually happened: which step changed the differential, which
  step clinched the diagnosis, which step was low-yield. The case reveals this; we do not guess it.

### 2.3 Scoring: graded relevance, trajectory-anchored, ontology-normalized

Frame it as **graded relevance** (think nDCG), where each candidate action has a *grade* derived from the real
trajectory:

- **Grade the gold actions.** The immediate next action = highest grade. Actions the team took later in the
  trajectory = decaying partial grade (they were on the path, just not now). The pivotal/diagnostic action can
  carry extra weight. Actions never taken = grade 0 from the primary metric.
- **Normalize to a controlled vocabulary** before matching: LOINC (labs), CPT/SNOMED procedures (imaging,
  procedures), RxNorm (drugs). Both prediction and gold map to codes, so matching is **deterministic**. This
  is the single biggest measurement upgrade over v1.
- **LLM judge only for the residue** — predictions that don't map cleanly to a code — and every such case is
  flagged and audited, never silently trusted. (v1 lesson: a soft judge inflates the headline.)
- **Report the reward per decision point and the curve across the case**, not one number. Also report the
  fraction scored deterministically vs by fallback judge.

If the model outputs a *ranked list* of next steps (it should — v1's clearest keeper was "score the whole
ranked list"), score the ranking against the graded golds (nDCG-style): full credit if the top suggestion is
the pivotal next step, partial if the right step is lower in its list.

### 2.4 The hard part: valid steps that aren't in the case

A genuinely good step the team didn't take is the known weakness. Handle it honestly, in tiers:

1. **Primary score** credits only trajectory-anchored actions. Defensible, deterministic, grounded.
2. **Secondary "guideline-consistent" signal**: where a formal pathway exists (e.g., workup algorithms,
   McDonald / Duke / DSM-adjacent criteria, specialty guidelines), a not-in-case step that the guideline
   endorses gets credit from a *separate*, clearly-labeled metric — reported alongside, never mixed into the
   primary number.
3. **Small expert-panel calibration set**: for a few dozen cases, have clinicians grade off-trajectory steps,
   to measure how badly the primary metric under-credits good-but-not-taken actions. Use this to *report* the
   bias, not to train on.

### 2.5 Construction discipline carried over from v1

- **Contamination:** post-cutoff cases; exclude the source article by DOI/PMCID/title for any retrieval run,
  with an audit trail. "Reduced memorization risk," never "could not have seen it."
- **Don't failure-mine against one model** (v1's biggest sampling flaw — the 68-case set was DeepSeek-Flash
  failures, which is circular). Sample cases by *objective* criteria (specialty coverage, number of decision
  points, presence of a clear pivotal step), and report any model-conditioned slices separately.
- **Adapted four-question audit per decision point:** (a) is the state complete and fair at step k (nothing
  needed to choose the next step was redacted)? (b) is the gold action actually in the source? (c) does the
  state leak the future (later results, the diagnosis)? (d) is the action at the right granularity (one
  orderable action, not a bundle)?
- **Segmentation is the new construction risk.** The LLM that splits the timeline can split it wrong. Validate
  segmentation against the source, and prefer cases with an explicit, easy-to-parse workup sequence.

## 3. The harness, rebuilt from the ground up

### 3.1 Push the no-tool baseline first (v1 lesson: elicitation beat retrieval)

Before crediting any tool: strong closed-book baseline — multi-sample the model's next-step distribution, take
a self-consistency / union of samples. Much of v1's "retrieval lift" was really the model getting a second
chance to say what it already knew. Establish that ceiling first, and only count tool gains beyond it.

### 3.2 Why a tool has a better shot here than in diagnosis

"Next step" is more *structured* than free diagnosis. There are real decision rules and workup algorithms for
"given this state, what do you order next." That means retrieval can fetch something closer to a **partial
oracle** (a guideline pathway) instead of just literature-salient noise. The harness's job becomes "check the
model's proposed next step against the applicable pathway," which is more checkable than "was this differential
right."

### 3.3 Do-no-harm architecture (carry over)

The tool **adds or flags, it does not overwrite.** v1's clearest positive result was do-no-harm fusion: keep
the model's confident choices, let the tool only add a missed candidate or raise a flag. Never let the tool
crowd out the model's own correct answer. Same principle here.

### 3.4 Verification needs an *independent* checker (v1's deepest lesson)

Self-verification rubber-stamps — the model that proposes the edit approves its own edit. So a v2 verifier must
be independent of the proposer:

- **A formal rule where one exists** (guideline: "if X and Y, order Z"). This is the closest thing to Lean that
  medicine offers — partial, but real, and it exists more often for *actions* than for *diagnoses*.
- **A stronger, independent model** as checker (not the same model checking itself).
- **The trajectory as an offline oracle *for development only*.** This is new and important: unlike v1, we have
  a real oracle at development time — the actual future of the case. We can honestly measure move precision
  ("when the harness changed the model's #1 next step, was the new one closer to the real pivotal step?")
  because we know what happened. At inference the harness cannot peek at the future, but at development we can
  finally measure whether an edit helped — which v1 never could.

### 3.5 Measurement discipline (v1 lesson: observability is part of the experiment)

- Deterministic ontology scoring wherever possible; within-run judging for the residue; reuse a rank when the
  list is unchanged (don't re-judge identical outputs — judge noise faked deltas in v1, even at temp 0).
- Fail loudly on pipeline errors (truncated output, empty plans, dropped evidence, changed denominators). Log
  every fallback, every dropped item, the exact denominator, and model/prompt versions.
- Report the reward curve and the deterministic-vs-judged split, not a single headline number.

## 4. Framing that might help

- This is essentially **process supervision / offline RL**: each (state, action, reward) triple is a step; the
  case trajectory is an expert demonstration; the graded-relevance score is a process reward. Worth borrowing
  vocabulary and metrics from offline RL and process-reward-model work.
- The trajectory gives a natural **behavior-cloning baseline** (predict what the team did) and a **value**
  signal (which steps paid off), cleanly separated.

## 5. Open questions to resolve next session

1. **Scope of "action":** diagnostic workup only, or include management/treatment? Diagnostic workup is cleaner
   to code and to ground; treatment is higher-value but fuzzier.
2. **Ontology + mapping reliability:** which vocabularies, and how reliably can we map free-text predictions to
   codes? Mapping errors reintroduce judge-like noise.
3. **State boundaries:** what counts as one "step"? A single order, or a batch a clinician would place together?
4. **Pivotality weighting:** define it objectively — information gain on the differential, or
   diagnosis-clinching, or outcome change? Prefer something computable from the source.
5. **The off-trajectory problem:** how big is the under-credit bias, and can we afford a small expert-graded
   calibration set to quantify it?
6. **Case sourcing:** which post-cutoff, openly-licensed sources have clean, parseable workup timelines? (NEJM
   case records are the gold standard in *format* but are not open-licensed — need CC-BY equivalents.)
7. **Segmentation validation:** how do we check the timeline split is faithful without a human on every case?

## 6. One-line summary

Move from guessing the diagnosis to predicting the next best step; take the gold and the partial-credit grades
from the case's *real* trajectory (not an LLM's opinion) and score against a coded action vocabulary
(mostly deterministic) — which is exactly what fixes v1's circular construction and untrustworthy measurement —
then build a do-no-harm harness whose checker is independent (a guideline, a stronger model, or the trajectory
as an offline development oracle), and always beat a hard multi-sample no-tool baseline before claiming a tool
helped.
