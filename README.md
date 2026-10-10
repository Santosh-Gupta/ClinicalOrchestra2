# Clinical Orchestra 2

A research benchmark for predicting **what was documented next in a clinical case**.

The new construction pipeline is implemented and tested with synthetic fixtures. It converts a
prepared case report into multiple prospective inputs and separately stored answers, while tracking
both physical clinical timing and what the team knew at each point. **No live constructor comparison
or model evaluation has been run.** Start with [HANDOFF.md](HANDOFF.md) and the
[construction guide](docs/CONSTRUCTION_PIPELINE.md).

## Why this exists

The previous [ClinicalOrchestra](https://github.com/Santosh-Gupta/ClinicalOrchestra) project relied on
LLM-written diagnostic puzzles and noisy free-text judging. The
[project write-up](https://santoshguptaml.substack.com/p/my-failed-attempt-at-making-a-medical)
describes those failures. This project anchors answers to reported events and uses fixed candidate
IDs so evaluation need not repeatedly judge free text. Extracting and auditing the labels still
requires models; a true quotation alone does not establish that a label is correct or predictable.

## Construction

Two provider families independently extract evidence and linked chronologies. Code renders only
information available at each cutoff. A separate prefix-only request proposes plausible alternatives;
a source-aware audit checks support, omissions, chronology and label mapping before export.

| Event type | Question |
| --- | --- |
| `action` | What action or action bundle was next documented? |
| `result` | What result was reported for an already documented test? |
| `diagnosis` | What diagnostic assessment or revision was next documented? |
| `progression` | What change was reported at a specified follow-up? |
| `response` | What change was reported after a documented treatment at that follow-up? |

These are forecasts of a recorded course, not labels for optimal clinical care. Inputs request
probabilities over frozen candidate IDs, including an `OTHER` option. Outputs retain the source
answer and supporting evidence. Report eventual forecast scores by event type and cluster statistics
by case. The probability scorer and evaluation runner remain to be built.

## Run locally

Use Python 3.11 from the repository root. These commands need no keys or network:

```bash
export PYTHONPATH=src
python3.11 -m unittest discover -s tests
python3.11 scripts/construct_benchmark.py
python3.11 scripts/construct_benchmark.py --demo
```

The default command prints model readiness and a plan. The demo writes eight input/output pairs
from one **invented software fixture**, across two scripted constructor roles. It tests plumbing,
not model quality. See the [construction guide](docs/CONSTRUCTION_PIPELINE.md) for the case-record
format, credentials, provider discovery, live pilots, request limits, logs and response reuse.

The requested constructor pool is configured in [construction_models.toml](construction_models.toml):
DeepSeek 4.1 Flash (off-peak only), Gemini 3.8 Flash, Muse Spark 1.3, and an unresolved disabled GLM
slot pending clarification of “glm-3.5 flash.” Public model documentation has been checked; account
access has not. Missing keys do not prevent setup or synthetic testing.

## Repository map

| Path | Purpose |
| --- | --- |
| [HANDOFF.md](HANDOFF.md) | Current state, setup, limitations and next work |
| [docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md) | Authoritative decisions, through D-21 |
| [docs/CONSTRUCTION_PIPELINE.md](docs/CONSTRUCTION_PIPELINE.md) | Current prompts, API workflow and commands |
| [docs/NEXT_STEP_ARCHITECTURE.md](docs/NEXT_STEP_ARCHITECTURE.md) | Planned next-step evaluation and harness design |
| [docs/PREDICTION_TARGET_CATALOG_2026-10-10.md](docs/PREDICTION_TARGET_CATALOG_2026-10-10.md) | Candidate things to forecast from case reports and eligibility tiers |
| [docs/GENERAL_HARNESS_ENGINEERING_2026-10-10.md](docs/GENERAL_HARNESS_ENGINEERING_2026-10-10.md) | Controlled harness evidence, experiment controls and build gates |
| [docs/PROJECT_WATCHLIST.md](docs/PROJECT_WATCHLIST.md) | Outside projects to consult when specific design issues arise |
| [docs/BRAINSTORM_ROUND3.md](docs/BRAINSTORM_ROUND3.md) | Design proposal; implemented subset recorded in D-18 |
| [AGENTS.md](AGENTS.md) | Working rules and lessons from the predecessor |
| `src/clinical_orchestra/construction/` | New evidence extraction, compilation, audit and comparison runner |
| `tests/fixtures/construction/` | Invented source and expected chronologies for software tests |
| `construction_models.toml`, `.env.construction.example` | Requested constructor pool and blank key configuration |
| `models.toml`, `pricing.toml` | Older evaluation registry and historical price configuration |
| `data/` | Original working corpus: 16 cases, 5 timelines, 99 items |

## Original corpus and pipeline

The earlier pipeline ran end to end on published cases. Its code and 99 items remain intact for
reproducibility. The earlier yield-weighted scoring, questions and plans in
[Round 2](docs/BRAINSTORM_ROUND2.md) are superseded in the new construction path where D-18 specifies.
The old post-cutoff corpus is not used as development data for the redesign. Its item counts and
historical cost estimates are not evidence for the new pipeline's yield, quality or cost.
