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

v1 died of two problems. Both are addressed by the task change:

1. *Circular construction.* An LLM had to invent a fair puzzle and its answer, so test quality was
   capped by the constructor model — a problem when the thing being tested is LLM reasoning. In v2
   the gold is **extracted** from what the clinicians actually did, not invented.
2. *Untrustworthy measurement.* Comparing free-text diagnoses needed an LLM judge, which was noisy
   even at temperature 0 and produced apparent differences between runs that were not real.

It is also closer to real practice: medicine is a sequence of decisions, not one guess.

---

## D-03 — A "step" is any next event, typed. **Adopted**

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
