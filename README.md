# Clinical Orchestra 2

A benchmark and harness for predicting **the next best step in a clinical case**, instead of
predicting the final diagnosis.

**Status: early. Nothing is built yet.** This repository currently holds a design document and the
shared infrastructure carried over from the previous project. There is no benchmark data and no
harness code.

## Why this exists

The previous project, [ClinicalOrchestra](https://github.com/Santosh-Gupta/ClinicalOrchestra), built
a diagnosis benchmark and a retrieval harness. It was paused. The write-up explaining what worked,
what didn't, and why is here:
[My [failed] Attempt at making a Medical Diagnostic LLM Harness and Benchmark](https://santoshguptaml.substack.com/p/my-failed-attempt-at-making-a-medical).

Two problems ended that project:

1. **The benchmark was built circularly.** An LLM had to turn a case report into a fair, self-contained
   puzzle and supply the answer. That means the quality of the test was capped by the model writing
   it, which is a problem when the thing being tested is LLM diagnosis.
2. **The scoring couldn't be trusted.** Comparing free-text diagnoses required an LLM judge, and the
   judge was noisy even at temperature 0, which was enough to fake small differences between runs.

Switching the task from "what is the diagnosis" to "what should be done next" addresses both:

- The correct answer comes from **what the clinicians actually did next**, which is already written
  in the case report. We extract a real sequence instead of inventing an answer.
- Next steps are **actions** — a lab, an imaging study, a procedure, a drug — and actions can be
  mapped to standard code sets (LOINC, CPT/SNOMED, RxNorm). That makes most of the scoring
  deterministic, with no judge in the common path.

It is also closer to how medicine is actually practiced: a sequence of decisions, not one guess.

Full design notes, including the scoring scheme and the open questions: [DESIGN_BRAINSTORM.md](DESIGN_BRAINSTORM.md).

## What's in the repo right now

Shared infrastructure copied from v1 and adapted. These files were reused because they are not
specific to the diagnosis task; everything task-specific was deliberately left behind.

| File | What it does |
| --- | --- |
| `src/clinical_orchestra/model_client.py` | Standard-library client for OpenAI-compatible chat APIs and OpenAI's `/responses` API. Handles retries, provider quirks, and raises loudly on truncated output instead of passing partial results downstream. The system prompt is now a parameter rather than hardcoded. |
| `src/clinical_orchestra/ratelimit.py` | Shared sliding-window RPM/TPM limiter for providers with rate caps. |
| `src/clinical_orchestra/ledger.py` | Append-only run logging: a manifest recording exactly what was run, an event log, and named JSONL streams. Rewritten to be schema-agnostic. |
| `src/clinical_orchestra/ncbi.py`, `pmc.py`, `pubmed.py` | NCBI E-Utilities, PubMed, and PMC full-text access. Used both for finding source cases and for excluding a case's own source article during retrieval. |

## What comes next

In rough order:

1. Decide the case source. It needs to be openly licensed, published after the model cutoffs being
   tested, and contain a clearly ordered workup. (NEJM case records have the right shape but are not
   openly licensed.)
2. Build and validate timeline extraction: split a case into `state at step k → the action taken next`.
3. Build deterministic scoring on top of a coded action vocabulary.
4. Establish a strong no-tool baseline before building any harness on top of it.

## Rules carried over from v1

See [AGENTS.md](AGENTS.md). The short version: every model call runs at temperature 0.0, every
response is written to disk, post-cutoff cases are test-only, and pipeline problems fail loudly
rather than degrading quietly.
