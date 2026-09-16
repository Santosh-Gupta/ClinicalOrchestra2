# Clinical Orchestra 2

A benchmark for predicting **what happens next in a clinical case**, and a harness to be built on top
of it.

**Status: the dataset pipeline works end to end on real data. No model has been evaluated yet.**
There is no evaluation runner and no harness. If you are picking this project up, start with
[HANDOFF.md](HANDOFF.md).

## Why this exists

The previous project, [ClinicalOrchestra](https://github.com/Santosh-Gupta/ClinicalOrchestra), built
a diagnosis benchmark and a retrieval harness, then paused. The write-up is
[My [failed] Attempt at making a Medical Diagnostic LLM Harness and Benchmark](https://santoshguptaml.substack.com/p/my-failed-attempt-at-making-a-medical).

Two problems ended it:

1. **The benchmark was built circularly.** An LLM had to turn a case report into a fair,
   self-contained puzzle and supply the answer, so the quality of the test was capped by the model
   writing it — a problem when the thing being tested is LLM reasoning.
2. **The scoring could not be trusted.** Comparing free-text diagnoses needed an LLM judge, and the
   judge was noisy enough at temperature 0 to produce differences between runs that were not real.

Asking what happens *next* addresses both. The correct answer is **extracted from what actually
happened**, stated in the case report, rather than invented. And many answers can be graded
mechanically instead of by a judge.

## What the benchmark asks

A case report is split into an ordered timeline of events. Each event past a short warm-up becomes an
item: the model sees everything up to that point and predicts what comes next. One case yields around
twenty items.

Events are typed, and scores are always reported **per type**, never pooled:

| Type | The question |
| --- | --- |
| `action` | What should be done next? |
| `result` | This test was performed — what did it show? |
| `diagnosis` | What is the diagnosis? |
| `progression` | What happened to the patient next? |
| `response` | How did the patient respond to treatment? |

`result` is the strongest type. "What did the LP show" has exactly one correct answer recorded in the
text — it is a fact about the patient, not a choice — so unlike action prediction it has no
behaviour-cloning ceiling. It also probes diagnostic reasoning without accepting a disease name.

Two rules make the grading defensible, and both are easy to get wrong:

- **Credit follows information yield, not sequence position.** Case reports are published partly
  because the workup was circuitous, so rewarding the order a team happened to work in rewards
  detours. Each event is graded by what its result actually did, which the source states.
- **Partial credit is later-only, type-matched, and capped.** Naming something already visible scores
  zero, or the benchmark rewards repeating the prompt. Partial credit requires a type match, or the
  best strategy is to name the final diagnosis at every decision point.

Every extracted event must quote the source text, and the quote is checked verbatim. An event whose
quote cannot be found is dropped. That check is what stops this project from repeating v1's failure.

## Repository map

| Path | What it is |
| --- | --- |
| [HANDOFF.md](HANDOFF.md) | **Start here.** Current state, setup, what is not built, gotchas. |
| [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) | What has been decided and why (D-01…D-15). |
| [AGENTS.md](AGENTS.md) | Working rules, each with the v1 failure it came from. |
| [docs/LESSONS_FROM_V1.md](docs/LESSONS_FROM_V1.md) | What went wrong last time. |
| [docs/BRAINSTORM_ROUND2.md](docs/BRAINSTORM_ROUND2.md) | The design the code follows, and the proposed harness. |
| [DESIGN_BRAINSTORM.md](DESIGN_BRAINSTORM.md) | The earlier first pass. Parts were rejected — check the decision registry. |
| `src/clinical_orchestra/` | The package. |
| `scripts/` | The pipeline and the operational tools. |
| `models.toml`, `pricing.toml` | Model registry and API prices, as data. |
| `data/` | The working corpus: 16 cases, 5 timelines, 99 items. |

## Quick start

All four setup steps are required; each has caused a confusing failure at least once.

```bash
export SSL_CERT_FILE=$(python3.11 -c "import certifi;print(certifi.where())")
set -a && . /Users/santoshg/Coding/ClinicalHarness/.env.crossmodel.local && set +a
export PYTHONPATH=src
python3.11 -m unittest discover -s tests
```

Then:

```bash
PYTHONPATH=src python3.11 scripts/fetch_cases.py --from 2026/06/01 --limit 40 --query "neurology" --email santosh.gupta.eng@gmail.com
```

```bash
PYTHONPATH=src python3.11 scripts/build_timelines.py --model gemini-3.5-flash --limit 6
```

```bash
PYTHONPATH=src python3.11 scripts/build_items.py
```

Extraction takes 20–30 seconds per case, so run larger batches in the background.

## Current corpus

16 cases published from June 2026 onward, CC-BY or CC0 only, neurology-weighted. 5 extracted
timelines, 99 items. This is a working sample that proves the pipeline, not a dataset — the fetch
query matched 4,719 candidates.

Two known problems, both recorded in the data rather than hidden: 27% of action items bundle several
orders into one event, and item difficulty is not yet calibrated, so many items are probably trivial.

## Costs

A 200-case corpus at 5 samples per item runs from about $2.63 (Muse Spark contributor) to $34
(Gemini 3.8 Flash). Cost is not the binding constraint on this project; construction difficulty is.
Run `scripts/estimate_cost.py` for current figures — it prices against the corpus actually on disk.
