# Design decisions

The authoritative record of what has been decided and why. `AGENTS.md` points here.

**How to use this file.** Do not silently revert or weaken a decision below. If you believe one is
wrong, add a new entry that supersedes it — state the new evidence, mark the old one
`Superseded by D-NN` — and then change the code. A decision recorded only in a commit message is
invisible to the next agent.

Status values: **Adopted** (implemented and in use), **Agreed** (decided, not yet implemented),
**Open** (not decided; see `HANDOFF.md`).

---

## D-01 — Separate repository from v1. **Adopted**

v1 (`ClinicalOrchestra`) is published, paused, and linked from a public Substack post. Continuing to
build in it would make that repository stop matching what the post describes.

The data schema and the metric are also incompatible: v1's unit is (case → ranked differential,
judged top-1..top-5); v2's is (state at step k → graded next events). Almost nothing in v1's
`benchmark/`, `judge.py`, `consensus.py`, or `diagnostic_ensemble.py` survives that change.

Only task-neutral infrastructure was copied: `model_client.py`, `ratelimit.py`, `ledger.py`,
`ncbi.py`, `pmc.py`, `pubmed.py`. Everything diagnosis-specific was deliberately left behind.

**Do not revert unless** the two projects need to be re-run side by side with shared tooling.

---

## D-02 — The task is next-step prediction, not diagnosis. **Adopted**

**Partially superseded by D-18:** documented-event forecasting does not establish optimal care or eliminate construction bias.

v1 died of two problems. Both are addressed by the task change:

1. *Circular construction.* An LLM had to invent a fair puzzle and its answer, so test quality was
   capped by the constructor model — a problem when the thing being tested is LLM reasoning. In v2
   the gold is **extracted** from what the clinicians actually did, not invented.
2. *Untrustworthy measurement.* Comparing free-text diagnoses needed an LLM judge, which was noisy
   even at temperature 0 and produced apparent differences between runs that were not real.

It is also closer to real practice: medicine is a sequence of decisions, not one guess.

---

## D-03 — A "step" is any next event, typed. **Adopted**

**Partially superseded by D-18:** keep the five types; use explicit knowledge cutoffs and endpoints rather than making every timeline row a question.

Santosh's extension to the original design, and the reason the dataset is dense. The next step is
whatever happened next, of five types:

| Type | Meaning |
| --- | --- |
| `action` | a test, image, procedure, referral, or treatment was ordered |
| `result` | what an action showed |
| `diagnosis` | a diagnosis was reached or revised |
| `progression` | the patient's condition changed on its own |
| `response` | the patient's condition changed after treatment |

This yields ~20 items per case instead of a handful of decision points.

**`result` is the strongest item type, and this is not obvious.** The behaviour-cloning objection
(D-04) applies to *actions* — the team's choice is not necessarily the best choice. It does not
apply to results: "what did the LP show" has exactly one correct answer, recorded in the text. The
result is a fact about the patient, not a choice, so the gold is determinate. It is also a better
probe of diagnostic reasoning than asking for the diagnosis, because predicting the finding requires
having the right disease in mind but cannot be pattern-matched off a disease name.

---

## D-04 — Score per type; never pool. **Adopted**

The five types measure different skills against golds of different quality. A single pooled number
is uninterpretable — a model could look strong purely by being good at the most common type.

**Corollary, equally important:** the prompt must state which type is being asked. Otherwise part of
the task is guessing what kind of event comes next in a case report, which is genre prediction, not
medicine. A model that has learned "case reports put imaging after the neuro exam" would score well
without reasoning. Implemented in `items.QUESTIONS`.

---

## D-05 — Grade by information yield, not sequence position. **Adopted**

**Superseded by D-18 for construction-v1:** retrospective information yield is not the primary forecasting label or score. Legacy code remains reproducible.

The original design graded by position: immediate next = full credit, later = decaying credit.
Rejected. Case reports are published partly *because* the workup was circuitous, so position decay
rewards reproducing detours the team should not have taken.

Instead, every event carries a `yield_tier` describing what its result actually did — which is
stated in the source and is not a matter of taste:

| Tier | Meaning |
| --- | --- |
| 3 | its result established the diagnosis |
| 2 | its result meaningfully changed the differential |
| 1 | normal, non-contributory, or merely confirmatory |
| 0 | not part of this case |

The extractor is told to use tier 1 when the text does not say, and never to infer importance from
its own medical knowledge. `validate_timeline` rejects a case with more than two tier-3 events,
since inflated importance would flatten the grading the whole metric rests on.

---

## D-06 — Every extracted event must quote the source, verbatim. **Adopted**

**Partially superseded by D-18:** exact span grounding plus semantic and temporal audit replaces quote membership as a sufficient acceptance rule.

This is the single mechanism that stops v2 from repeating v1's central failure. The extraction model
must supply a `source_span` for every event, and `events.is_grounded` checks it appears in the case
text after normalisation. An event whose quote cannot be found is **dropped, not repaired** — a quote
the model could not produce is a quote that probably was not there. A case losing more than 25% of
its events is rejected outright.

Normalisation folds Unicode, case, quote and dash variants, and whitespace runs. It deliberately does
not strip words: the quote must still match the source's wording. Spans under 12 characters are
rejected because a short quote matches by accident and proves nothing.

**Verified working.** Negative controls pass: changing one word in a real quote, or gluing two
fragments together, are both rejected. On the first real run, 0 of ~110 events were dropped, which
looked suspicious until the controls confirmed the check fires correctly — the extraction model was
genuinely copying faithfully.

---

## D-07 — Partial credit is later-only, type-matched, and capped. **Adopted**

**Partially superseded by D-18:** legacy partial credit remains an exploratory secondary measure; it is not used in construction-v1 labels.

Santosh's requirement was partial credit when a guess appears elsewhere in the case. Three rules make
that safe; all three are enforced in `items.credit_for` and covered by tests.

1. **Only events after the cut earn credit.** Naming something already visible in the state is
   repeating the prompt, not predicting. It scores zero. Without this the benchmark rewards
   regurgitation.
2. **Partial credit requires a type match.** Otherwise the optimal strategy is to name the case's
   final diagnosis at every single decision point and collect credit across the whole case.
3. **Credit is capped well below correct and decays with distance.** `CORRECT = 1.0`,
   `LATER_MAX = 0.3`, `LATER_DECAY = 0.6` per step.

A fourth, cheap safeguard is worth adding: log how self-similar a model's answers are across items
within one case. The degenerate strategy is directly detectable.

---

## D-08 — No ontology mapping. Use a small closed vocabulary. **Agreed, not implemented**

**Partially superseded by D-18:** retain rejection of ontology mapping; replace the planned hand-curated vocabulary with frozen per-item candidate IDs.

The original design mapped predictions and golds to LOINC, CPT/SNOMED, and RxNorm for deterministic
scoring. Rejected for two reasons:

- Turning free text ("send autoimmune encephalitis antibodies") into a code is itself a fuzzy
  language task. If an LLM does it, the judge is back — one layer down, buried in a preprocessing
  step whose error rate nobody reports. That is v1's mistake wearing a different hat.
- Granularity mismatch: "LP" and "LP with opening pressure, cell count, cytology, and autoimmune
  panel" are one clinical decision and several codes. Those code sets are built for billing, not for
  how a clinician thinks about what to do next.

Replacement: a hand-curated closed vocabulary of roughly 200–400 action classes at clinical
granularity. Small enough to audit by hand, coarse enough that mapping is reliable.

**Not built yet.** This is the main blocker on scoring the generation task.

---

## D-09 — Add a deterministic ranking task beside generation. **Agreed, not implemented**

**Superseded by D-18 for construction-v1:** blind candidate construction with a residual option replaces gold insertion and yield-tier nDCG as the primary task. The probability scorer is still to be built.

Generation is the realistic task but hard to score. Ranking a fixed candidate slate is trivially
deterministic — no judge, no mapping, no threshold.

For each item, build a slate of ~10–15 candidates: the real next event, the pivotal event, others
from the case, low-yield distractors, and **hard negatives** drawn from similar decision points in
*other* cases (plausible, commonly ordered, wrong here). Score with nDCG against the yield tiers.
`items.ndcg` is implemented and tested; the slate builder is not.

Run both tasks. Ranking is the reliable primary metric; generation is the realistic secondary one.
Whether the two agree is itself a result v1 could never have produced.

The hard negatives are what make this non-trivial and are the part worth spending effort on.

---

## D-10 — Select cases objectively; calibrate difficulty by disagreement. **Adopted / Agreed**

**Partially superseded by D-18:** objective reference sampling remains; disagreement-selected difficulty subsets must be reported separately and may not replace the reference set.

*Adopted:* case selection uses only publication window, article type, licence, and length. No model
sees a case before it is cached, so selection cannot be conditioned on model behaviour. v1's hard set
was built from one model's failures, which made scoring that model on it circular.

*Agreed, not implemented:* most decision points are trivial (fever plus headache, do an LP), so the
benchmark will saturate unless difficulty is calibrated. The trap is that dropping items by model
failure re-creates v1's circularity. **Select by disagreement instead** — pilot each item against
several models, drop what all of them get, keep where they diverge. Disagreement is not anchored to
any one model's weaknesses. Report the difficulty distribution and stratify scores by it.

---

## D-11 — Cases must be CC-BY, CC-BY-SA, or CC0. **Adopted**

A derived dataset of extracted spans is a derivative work, so no-derivatives licences are excluded
entirely. Non-commercial licences are excluded by default and available behind
`--allow-noncommercial`, so that choice is explicit rather than accidental.

**This costs about 60% of the corpus.** Of the first 40 candidates, 23 were NC or ND. Budget roughly
2.5 candidate articles fetched per usable case.

---

## D-12 — The model registry is a data file. **Adopted**

`models.toml` holds provider, model ID, base URL, key env var, API style, and tier. Nothing in the
codebase hardcodes a model ID. Adding a newly released model is a registry entry plus a re-run.

`scripts/discover_models.py` asks each provider what it actually offers, so IDs are verified rather
than guessed — this is how `gpt-5.6-luna` and `gemini-3.8-flash` were identified.

---

## D-13 — Muse Spark contributor tier is acceptable. **Adopted**

Meta's contributor tier is far cheaper ($0.10 / $0.20) because Meta may train on submitted prompts
and completions. Initially flagged as disqualifying on contamination grounds; **Santosh overruled,
and his reasoning is correct**: everything we send is derived from published PMC articles that a
future model would train on regardless, and the benchmark is intended for release.

**One carve-out, recorded so it is not lost:** do not send a split that is meant to stay unpublished
as a fresh held-out test set. Anything derived from already-published sources is fine.

---

## D-14 — Statistics cluster by case, not by item. **Adopted (as a rule)**

Items from one case share the patient, the disease, and the narration, so they are not independent.
200 cases × 20 items is closer to 200 samples than 4,000. Any confidence interval or significance
test must cluster by case. `scripts/build_items.py` prints this warning on every run so it cannot be
forgotten.

Consequence: **case count governs the strength of any claim.** Prefer breadth of cases over depth of
items once each case yields enough items to cover the types.

---

## D-15 — Rules carried over from v1 without change. **Adopted**

Full statements in `AGENTS.md`; the reasoning is in `docs/LESSONS_FROM_V1.md`.

- Temperature 0.0 wherever the provider allows it, and persist every response to disk before
  deriving anything from it. Temperature 0 is not determinism — batched provider inference reorders
  floating-point operations.
- Never re-judge identical output; reuse the earlier score. In v1 this faked effects that were not
  there.
- Post-cutoff cases are test-only. Never tune prompts, thresholds, or the harness against them.
- Exclude a case's own source article from any retrieval run by DOI, PMCID, and title, and record
  what was excluded. Say "reduced memorization risk," never "could not have seen it."
- Beat a strong multi-sample no-tool baseline before crediting any tool.
- A tool adds or flags; it never overwrites.
- A checker must be independent of what it checks.
- Fail loudly: truncation, empty plans, dropped items, changed denominators.

---

## D-16 — Proposal: evidence-audited event forecasting under the no-human constraint. **Partially adopted by D-18**

Santosh requested a new brainstorm of the most robust and efficient pipeline from licensed case
reports, including prompts and model roles, with no human reviewers. The full proposal is in
[BRAINSTORM_ROUND3.md](BRAINSTORM_ROUND3.md). The original proposal below is preserved. D-18 records the implemented subset and explicitly
supersedes affected earlier decisions; experiments outside that subset remain proposals.

The design review distinguishes three things: what a report says happened, what was predictable
from the information available beforehand, and what would have been best clinical care. Existing
source labels establish the first, subject to extraction accuracy. The current action prompt asks
for the third. Realized yield does not establish prospective action quality, an unperformed
alternative is not necessarily inappropriate, and multi-model disagreement selection is still
model-conditioned selection.

A synthetic negative control also showed that `validate_timeline` accepts a real quote supporting
an unrelated event and an unsupported presentation. Quote membership is necessary provenance but
does not establish entailment or information availability; see the 2026-09-16 journal entry.

Proposed changes: independent evidence extraction; per-fact support and knowledge time; mechanical
state rendering; prefix-only question audits; source-aware label/leakage audits; exact candidate
IDs and probability scoring; an objectively sampled reference set plus a separately reported hard
subset; and a separate development corpus followed by fresh confirmatory cases. The author's thesis
would guide target discovery while remaining hidden from prospective questions.

If adopted, explicitly supersede the affected parts of D-02/D-03/D-05/D-06/D-08/D-09/D-10 and clarify
D-07's secondary role before changing code. Preserve the five event types, per-type reporting,
verbatim grounding, case clustering, model registry and response logging. The existing
implementation and historical decisions remain intact during this proposal stage.

---

## D-17 — Maintain linked clinical-course and clinician-information chronologies. **Adopted in construction-v1 by D-18**

Santosh explicitly requested organizing both what physically happened to the patient and what the
medical professionals knew, in chronological order, and using both to create inputs and outputs.

Maintain a source-supported clinical-course chronology and a separate information-availability
chronology. The latter controls visible inputs at each cutoff. Hidden targets may concern later
clinical developments or later discoveries of earlier events; distinguish these in task metadata.
Do not expose an earlier physical event before evidence says the team knew about it. Do not infer
unreported biological onset or a complete physical state from the final diagnosis.

Preserve uncertainty and partial ordering. For available results versus actual clinician awareness,
use only distinctions the source supports and state the availability proxy where necessary. Team
suspicions are beliefs, not established patient facts. Later corrections must not overwrite the
historical information state.

Initially agreed as an extension of D-16; the first implementation is now specified by D-18.
Further proposed checks and experiments are in section 10 of
[BRAINSTORM_ROUND3.md](BRAINSTORM_ROUND3.md).


---

## D-18 — Implement the first auditable construction pipeline and requested constructor pool. **Adopted, 2026-09-17**

Santosh authorized setting up prompts and API infrastructure to convert a batch of case studies
into multiple benchmark inputs and outputs, comparing GLM “3.5 flash,” DeepSeek 4.1 Flash off peak,
Gemini 3.8 Flash and Muse Spark 1.3. The first implementation is isolated in
`clinical_orchestra.construction`; the older modules and data are retained for reproducibility.
Operational details, commands and limitations are in [CONSTRUCTION_PIPELINE.md](CONSTRUCTION_PIPELINE.md).

**Task and labels.** Questions forecast the next documented action, result, diagnostic assessment,
clinical development or response at a specified endpoint. They do not ask what would constitute
optimal care. Two independent source extractions represent clinical timing separately from information
availability. Exact quotations and complete paragraph coverage are required. Code compiles visible
states from knowledge phases; it never serializes hidden thesis metadata or future facts. Facts in
one information phase are explicitly unordered. Unknown ordering is not filled in from prose order.

A prefix-only request constructs plausible alternatives without the gold or source ending. Code adds
OTHER and shuffles labels and positions. A source-aware auditor from another provider checks claims,
omissions, chronology and every visible fact, then maps the documented answer to one frozen candidate
ID. Ambiguous/unsupported items are rejected. Semantic acceptance is still model-assisted; exact-ID
scoring does not make the labels deterministic or clinically certified. Probability predictions are
specified in exported inputs; the evaluation runner and probability scorer are not implemented yet.

**Explicit supersessions.** D-02/D-03 retain next-event typing but lose claims that source extraction
alone removes circularity or yields a question for every event. D-05's retrospective yield grading,
D-08's hand-curated vocabulary and D-09's gold-inserted yield-tier ranking are replaced for this new
path. D-06's verbatim-support requirement is retained and strengthened with semantic/temporal audits;
quote membership is insufficient. D-07 is secondary legacy exploration, not a new primary score.
D-10 retains objective selection but disagreement-selected subsets must remain separately reported.
D-01, D-04 and D-11 through D-15 otherwise remain. No ontology mapping is reintroduced.

**API behavior.** The construction registry contains only the requested pool. Three IDs are documented,
not live-probed. The GLM slot remains disabled pending name clarification; missing keys are reported,
not silently skipped. Two provider families suffice for a pilot, three separate constructor/witness/
auditor roles when available. Requests are stateless and case-ordered. Every transport response is
logged before parsing; identical stage requests reuse exact saved responses. Failures and denominators
remain visible. Request hashes include prompts, schema, model settings and trial. Live requests require
`--live`. DeepSeek's schedule gate applies before every retry, with a timeout margin; it controls
dispatch rather than certifying the provider's eventual charge.

**Evaluation boundary.** Development comparison requires declared development cases. Test construction
requires preselected roles with `--purpose test --single`. The old post-cutoff sample is not repurposed
as development. Case clustering is retained. The current per-case cap is a pilot bound, not a claim
of representative sampling. Reviewer rotation means constructor comparisons also change reviewer
configuration; report that limitation rather than attributing every difference to the constructor.

**Evidence so far.** Fifty-two no-network tests pass, including synthetic temporal leakage, wrong claims
attached to real quotes, audit omission, schema failure, response reuse, transport logging and peak
boundaries. The scripted demo exports eight pairs from one invented patient across two constructor
roles. These establish software behavior only. No paid construction calls, real constructor-quality
estimates, difficulty calibration or clinical label error estimates have been obtained.

---

## D-19 — Architect a shared harness for typed next-step forecasts. **Adopted as design, 2026-10-05; implementation pending**

**Extended by D-20** for programmatic execution, evidence records, review and recovery. The one-action
policy remains an experimental control; the task contracts and evaluation rules below remain in force.

Santosh reaffirmed that the project covers next tests, progression, outcomes and other mineable
continuations, with diagnosis only one task family, and authorized further relevant research and
overall architecture work. The design is in [NEXT_STEP_ARCHITECTURE.md](NEXT_STEP_ARCHITECTURE.md);
additional forecasting evidence is in [NEXT_STEP_FORECASTING_LITERATURE.md](NEXT_STEP_FORECASTING_LITERATURE.md).

Retain D-17's two chronologies and D-18's five families, independent extraction, prefix-only
alternatives, source audit and exact candidate IDs. Add explicit forecast contracts for target scope,
visible anchor, endpoint kind and origin, and observation status. Distinguish clinician behavior,
information discovery, documented assessments and clinical developments. An unreported outcome is
not a negative label; OTHER is not missingness or abstention. Treatment-associated responses do not
establish causal effects. No optimal-care or hypothetical-intervention target is added.

The next construction version will allocate a fixed per-case cap across eligible task families
under a declared deterministic policy. This replaces the early-first allocation for that new
version only; D-18's implemented pilot cap and saved artifacts remain unchanged. Endpoints chosen
retrospectively from reporting must be identified and separated from prospective-window results.
Ambiguous simultaneous events require supported bundles or explicit exclusion, not invented order.

Use one inference engine with family-specific instructions. Begin with direct and repeated-request
probability baselines, then measure each added mechanism separately. Preserve initial predictions;
tools add or flag evidence and any revised forecast is a separate saved candidate. Fresh solver
state at every cutoff prevents cross-item information leakage. Keep current temperature, source
exclusion, split, logging and independent-checker rules.

Separate construction, input-only solving and post-run scoring. The worker cannot access hidden
labels, full sources, or source-aware audit records. Broker evidence reads so even a quoted source
paragraph cannot disclose future clauses. Enforce credentials, tool permissions and all nested-call
budgets on the host. Inspect AI is the first outer-runner integration candidate; the scoring core
remains independent and no new dependency is adopted before an integration check.

Report proper probability scores for valid distributions with their denominator, plus completion
and error counts and operational accuracy over all assigned items. Report families separately and
aggregate with explicit case weights and clustered uncertainty. Never promote a strategy on
valid-only scores while hiding its failures. Generated trajectories remain hypotheses, not facts.

Evidence: Foresight, ETHOS/ARES and DT-GPT provide non-diagnostic forecasting precedents; AgentRx
provides a directly relevant comparison of agent configurations and calibration. Their EHR data,
training and evaluation settings do not validate our case-report benchmark. Code inspection found
free-text endpoints and early-first cap selection in construction-v1, motivating explicit contracts
and family allocation. No new implementation, live evaluation or clinical validation accompanies
this design decision. Earlier decisions otherwise remain in force.

---

## D-20 — Separate forecast policies from brokered execution and durable evidence. **Adopted as design, 2026-10-08; implementation pending**

**Extended by D-21** for controlled harness comparisons, attempt-level outcomes and implementation gates.

Santosh requested deeper intelligence on Claude Science and other strong harnesses to inform the
next-step design. The [science harness investigation](SCIENCE_HARNESS_INTELLIGENCE_2026-10-08.md)
records primary sources, limitations, and a pinned Prime Agent source inspection. It extends D-19;
it does not replace construction, target families, the information boundary or exact scoring.

The worker supports direct prediction, repeated-request averaging, a one-action control, and a
bounded programmatic policy. Separate policy, host capability broker, optional execution runtime,
and durable event/artifact store. Keep gold outside every solver component. Ordinary tools and
generated code receive the same capabilities. A Python subprocess is not a security sandbox.

Authorize, meter and record every underlying operation, including unprinted results, nested model
calls, retries and review. Reserve budget before parallel dispatch. Keep reported facts immutable
and distinguish references, calculations, hypotheses, review findings and forecast versions.
Preserve lineage and conflicts without equating citations with entailment. Actual execution records
take precedence over reconstructed descriptions of work.

Test evidence-integrity review separately from diagnostic critique. Rules check mechanical claims;
an independent model may flag unsupported interpretations. Neither sees labels. Review-enabled
strategies have fixed pre-submission schedules and explicit incomplete-review behavior. Late review
cannot rewrite the scored forecast. Preserve initial predictions for regression analysis.

Recover from durable responses and artifacts rather than silently resampling or assuming live kernel
state survives. Log uncertain request outcomes and retries. Freeze skills, routing, environments and
memory policy during evaluation; current-item notes may change, but cross-item learning remains
outside the primary protocol. Declare capabilities for unattended runs without human approval steps.

Evidence includes Science's documented REPL/MCP bridge, execution history and narrow review contract;
Kosmos's credential proxy; Prime's runtime protocol and reported refinement exploit; and BixBench3's
Inspect-based artifact scoring. These support engineering choices, not clinical accuracy claims.
Inspect remains the outer-runner candidate and the existing client/ledger remain reusable. Define
interfaces now, implement the simplest baselines first, then compare each addition at declared limits
and observed cost, completion and per-family probability scores. No model experiment accompanies D-20.

---

## D-21 — Make harness additions earn their place under matched, failure-complete evaluation. **Adopted as design, 2026-10-10; implementation pending**

Santosh requested a further general harness-engineering investigation before development. The
[review](GENERAL_HARNESS_ENGINEERING_2026-10-10.md) records recent controlled medical and general
comparisons, counterevidence to elaborate agents, infrastructure effects, harness-selection bias,
and evaluation-harness defects. These sources do not establish that any agent policy will improve
clinical next-event forecasts.

Treat input isolation, immutable assigned tasks, durable attempts, an input-only worker, host-enforced
budgets, failure accounting and a deterministic scorer as the shared measurement instrument. Treat
planning, retrieval, review, compaction, programmatic execution, delegation and model routing as
separate forecast policies. Start with direct prediction and a fixed repeated-request probability
average. Keep the same frozen items, information access, provider identity, runtime, output contract
and scorer in paired policy comparisons. Record actual rendered model context and executed tool
arguments/results, not just intended templates and calls.

Build an attempt state machine: assignment precedes dispatch; raw response persistence precedes
parsing; the final submission channel and error categories are explicit. A request with unknown
provider outcome is not a cost-free retry. Failures after assignment stay in the operational
denominator. Report completion, failure classes and valid-only probability scores with their
denominators, plus operational accuracy across all assigned items. A leakage or scorer-integrity
failure stops the run. Test that each negative control actually exercises the route it purports to
protect. Mechanical replay must reproduce scores.

Choose prompts and policies on development cases, compare extra mechanisms with a matched
extra-inference baseline, disclose the number of variants tried, and confirm on untouched case
clusters. Report family-specific paired uncertainty and cost/latency, including provider and
model–harness interactions. Add context management only if it solves a measured overflow or evidence
management problem; add nested execution, review or delegation only after their narrower controls
are understood. Use one common-protocol model comparison and separately label any model-specific
prompt/tool adaptations chosen on development data. Preserve D-19's task contracts and D-20's
broker and evidence model.

Implementation begins with contracts/fixtures and framework-independent deterministic scoring,
then the durable direct worker and isolation broker. No code, paid model calls, real constructor
comparison, evaluation result or clinical validation accompanies D-21.

---

## D-22 — Prespecify journal discovery and verify each article before construction. **Adopted as dataset intake design, 2026-10-10; filtering implementation pending**

The old project preserved PMC provenance and article-level license distinctions, but its broad
journal registry is not a current quality allowlist. The current fetcher searches all PMC open-access
case reports; that search alone admits outlets whose editorial process has not been checked. The
[dated sourcing review](DATASET_SOURCING_2026-10-10.md) records a narrower discovery cohort and
current provider pricing/cutoffs. PLOS ONE is explicitly excluded because it does not accept
clinical case reports under its current criteria. A journal's open-access label also does not settle
reuse: several established case-report journals offer CC BY alongside CC BY-NC or CC BY-NC-ND.

For the next intake version, declare eligible journals, journal strata, time window and sampling
rule before seeing model results. Keep a full candidate/rejection ledger. Admit each article only
after checking actual case-report content, article-level license, first public version date,
corrections/retractions, patient/report duplication and chronological completeness. Preserve exact
publisher, NLM and PMC identifiers, dates, license evidence and retrieval time. An absent or
conflicting license or unknown first-public date must not silently pass the public post-cutoff gate.
Published case outcomes remain observations, not optimal-care labels. Do not select a reference set
by model failure or perceived surprise. Preserve journal and family denominators and cluster
statistics by case.

Training-cutoff dates are model-specific. OpenAI, Anthropic and Google disclose different cutoffs;
several other current vendors do not disclose a model-specific date. The earliest public version
must postdate the solver's documented cutoff plus a prespecified buffer to qualify for the stronger
temporal subset. This reduces contamination risk; it cannot prove the model never saw the case.
Unknown cutoffs remain unknown, and moving model aliases require resolved-version logging.

The existing construction prompts, model pool and 99 historical items are unchanged. The fetcher
now retains its already parsed journal and PMID in new case records; prespecified journal filtering,
full publication-date capture and live constructor comparisons are still pending.

---

## D-23 — Build three exclusive psychiatry/neurology tracks with an enriched intersection. **Adopted as discovery design, 2026-10-16; clinical labeling pending**

Santosh requested pure psychiatry, pure neurology and mixed neuropsychiatric next-step benchmarks,
with an effort to find many mixed cases. Treat them as three separately scored tracks under D-18/19's
shared item and harness protocol. Assign each patient/report cluster to at most one track. The pure
tracks require material clinical work in their own specialty and no material work in the other.
The mixed track requires both domains to affect the case, and its headline items require
source-backed psychiatric and neurological information already available at the cutoff plus a
target linked to both. A paper with both words, a routine rule-out test, or only a retrospective
discussion does not qualify. Unresolved cases stay outside headline sets.

Prespecify a narrow journal/date frame and independent specialty reviews before seeing solver
behavior. Keep a hash-sampled frame reference slice for prevalence within the retrieved search
frame and separately report specialty-enriched and mixed-enriched routes. Search all mixed-route
hits within the frame;
do not cap them by perceived interest. D-22's article-level rights, first-public-date, quality,
duplication and chronology gates still apply. Do not assign final specialty or temporal test status
from title, search query, JATS type, publication year or a single LLM. Mixed difficulty is a
hypothesis to test on frozen, family-matched items with case-clustered uncertainty, not an inclusion
criterion. The [track contract and search plan](PSYCHIATRY_NEUROLOGY_BENCHMARKS.md) give the exact
rules and sources.

The deterministic discovery script and 2026-10-16 candidate ledger implement the retrieval stage.
A strict two-family specialty-review prompt and runner are implemented for prepared development
cases, but no live review, independent chronology audit, accepted case assignment, real input/output
pair, solver run or difficulty result accompanies this decision. The prior 99 post-cutoff items
remain untouched.
