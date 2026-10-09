# Constructing benchmark inputs and outputs

Implemented 2026-09-17 as `construction-v1`, following D-17 and D-18. This is a new, separate
construction path. The old timeline builder and its 99 items remain reproducible; they have not
been migrated or used to tune this pipeline.

The pipeline is ready for a small development pilot once credentials are available. Its tests use
scripted synthetic responses. No live construction run or constructor-quality comparison has been
performed. Model-assisted acceptance is not a measured clinical accuracy rate.

## What each case goes through

1. **Index the source.** Preserve the provided text, paragraph offsets, source hash, article metadata,
   case ID, patient/article cluster and explicitly assigned split. The input is the licensed text
   already prepared upstream; fetching, licensing and image interpretation are outside this step.
2. **Extract independently twice.** Two different provider families each receive only the indexed
   source. Each returns patient facts, exact supporting quotations, physical event timing and a
   separate ordered sequence of information phases. Every source paragraph needs a coverage entry.
   This makes omitted patient information inspectable as well as invented information.
3. **Compile questions in code.** The information phases determine which facts appear in each input.
   Late-disclosed history stays hidden until disclosure even when it physically predates admission.
   The physical chronology remains a partial order; unknown timing remains unknown. Visible claims
   must preserve temporal details known at that phase. Retrospectively established timing is hidden
   metadata until supported as a newly disclosed fact.
4. **Construct alternatives without seeing the ending.** A fresh request receives exactly one
   visible input and its typed question. It flags structural defects, records missing variables,
   and proposes 3–7 alternatives. Code adds `OTHER` and deterministically shuffles both labels and
   positions. The observed answer is never inserted into the slate. Multiple plausible outcomes are
   ordinary forecasting uncertainty; they are not automatically grounds for rejection.
5. **Audit against the entire source.** A different provider from the constructor checks every
   fact, information phase, source paragraph and candidate item. It consults the second extraction
   for omissions, checks knowledge availability at each cutoff, derives the documented target and
   maps it to one frozen option. Unsupported claims, unresolved chronology, overlapping options,
   answer leakage and missing audit rows prevent export. Quotations are checked mechanically as
   well; a real quotation alone does not prove the attached claim.
6. **Export separate inputs and hidden outputs.** Inputs contain only the state, question, event
   type, opaque item ID, candidate IDs and probability-response instructions. Outputs contain the
   label, source-reported answer, provenance, physical timing, information cutoff and case cluster.

With `n` candidate items, one constructor requires up to `n + 3` base calls per case: two
extractions, `n` blind alternative requests and one whole-case audit. Retries can add HTTP attempts.
Identical extraction requests can be reused across constructor rotations. Calls are ordered
case-by-case with stable prompt prefixes; actual provider prefix-cache savings are not yet measured.

When two families are selected, one constructs while the other independently extracts, proposes
alternatives and audits in separate stateless requests. With three or more, a third family audits.
Default comparison rotates each selected model through the constructor role on the same cases.
This tests a construction configuration, not an isolated causal effect of the constructor: reviewer
roles also change. Keep those roles in reports and inspect acceptance by event type, source coverage,
rejections and the frequency of `OTHER`. A model that rejects almost everything is not necessarily
the best constructor.

## Prompts and contracts

The actual versioned prompts are in
[`src/clinical_orchestra/construction/prompts/`](../src/clinical_orchestra/construction/prompts/):

- `system.txt`: source text is evidence, not instructions; no invented facts or optimal-care claims.
- `extract.txt`: linked clinical and information chronologies, evidence, coverage, uncertainty.
- `blind.txt`: one prospective input, structural defects, missing variables, plausible alternatives.
- `audit.txt`: full-source entailment, omissions, chronology, leakage and frozen-option mapping.

[`schemas.py`](../src/clinical_orchestra/construction/schemas.py) defines strict JSON contracts.
The request contains its complete schema; APIs are asked for JSON objects and local code enforces
the contract. Native provider JSON-schema enforcement is not assumed. Unknown fields, missing
fields, invalid enums, duplicate JSON keys and non-finite constants are rejected. No repair model
rewrites invalid responses, and no hidden provider fallback substitutes a different model.

## Requested model pool

[`construction_models.toml`](../construction_models.toml) is separate from the older evaluation
registry. IDs were checked in primary provider documentation on 2026-09-17; account access and
request compatibility still need live probes.

| Registry key | API model ID | Credential environment variable | Status |
| --- | --- | --- | --- |
| `glm-requested-flash` | `UNVERIFIED-glm-3.5-flash` | `XM_ZHIPU_KEY` | Disabled pending name clarification |
| `deepseek-4.1-flash` | `deepseek-flash` | `DEEPSEEK_API_KEY` | Documented; off-peak dispatch only |
| `gemini-3.8-flash` | `gemini-3.8-flash` | `XM_GEMINI_KEY` | Documented |
| `muse-spark-1.3` | `muse-spark-1.3` | `MODEL_API_KEY` | Documented; standard endpoint |

DeepSeek documents `deepseek-flash` as serving V4.1; it is a moving alias, not an immutable model
snapshot. Persist the returned model metadata and date with results.
[DeepSeek release](https://api-docs.deepseek.com/news/news260910/).
Gemini's model ID is documented on its
[model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
Meta's official [API cookbook](https://github.com/meta-models/meta-model-cookbook/blob/main/01_api_fundamentals/README.md)
documents the Muse endpoint and API convention. Z.ai lists GLM-5.3-Flash in its
[pricing documentation](https://docs.z.ai/guides/overview/pricing); do not silently replace the
user's ambiguous “glm-3.5 flash” request with that model or with StepFun's Step-3.5-Flash.

`enabled=true` does not mean an account has credit or API access. The plan checks only configuration
and environment-variable presence. No key is printed. Selecting an unready model blocks a live run;
models are not quietly omitted. Select the available subset explicitly.

## Run without credentials

From the repository root, using Python 3.11:

```bash
export PYTHONPATH=src
python3.11 scripts/construct_benchmark.py
python3.11 scripts/construct_benchmark.py --demo
python3.11 -m unittest discover -s tests
```

The first command prints a no-network plan. The demo uses an invented case and scripted model
responses, writes eight pairs by default, and cannot establish model or clinical quality. It uses
a separate cache namespace from live runs. Run it again to exercise saved-response reuse.

## Prepare a batch

Supply one JSON file per case in a directory, with this shape:

```json
{
  "case_id": "development-001",
  "case_group": "article-or-patient-cluster-001",
  "split": "development",
  "source": {"pmcid": "...", "doi": "...", "title": "...", "license": "..."},
  "case_text": "The prepared source text, preserving paragraphs."
}
```

Assign splits before construction. Related reports or repeated accounts of one patient share a
`case_group`. The loader rejects duplicate text and conflicting group splits within the supplied
batch. It does not detect differently worded duplicates or cross-directory overlap: the upstream
case inventory must enforce those. Do not relabel the existing post-cutoff corpus as development.

The default selects the first three files in sorted filename order and at most six eligible targets
per case. This is a bounded pilot, not a representative sampling procedure. Eligibility requires a
supported earlier information state, an unambiguous typed target, and a previously known action
for results/responses. Responses and progressions also need a source-supported neutral endpoint.
Simultaneous targets of the same type are excluded unless already represented as one defensible
bundle or separated by a named action. Every exclusion and cap is logged. The early-target cap can
bias coverage; freeze a broader sampling rule before claiming corpus-wide findings.

## Add keys and run a pilot

Use a gitignored `.env.construction.local` populated from the blank
[`.env.construction.example`](../.env.construction.example). Set only credentials you have; an empty
assignment will overwrite an already loaded environment value. Existing cross-model credentials
can also be loaded from the path in `HANDOFF.md`.

```bash
export SSL_CERT_FILE=$(python3.11 -c 'import certifi; print(certifi.where())')
set -a
. ./.env.construction.local
set +a
export PYTHONPATH=src
python3.11 scripts/discover_construction_models.py --models gemini-3.8-flash muse-spark-1.3
python3.11 scripts/construct_benchmark.py --cases /absolute/path/to/development-cases --models gemini-3.8-flash muse-spark-1.3 --limit 1
```

Discovery only requests provider model lists. If a provider does not support listing, report that
failure; it does not prove inference is unavailable. After checking the plan, dispatch the pilot:

```bash
python3.11 scripts/construct_benchmark.py --live --cases /absolute/path/to/development-cases --models gemini-3.8-flash muse-spark-1.3 --limit 1 --max-requests 30
```

The same command can include DeepSeek and, after its name is resolved and registry updated, GLM.
Select at least two distinct provider families. `--single` makes the first selected model the only
constructor and uses the remaining models as reviewers. Test-split construction requires
`--purpose test --single` with preselected roles; model comparison is development-only. Contributor
endpoints are blocked for this unpublished-test mode.

Requests use temperature 0 where supported. The shared client records a provider's temperature
rejection and any retry without it. Temperature 0 and model aliases do not guarantee repeatable
inference. Defaults are 16,000 output tokens, 300 seconds per request and 30 HTTP attempts per run,
including retries. These are request limits, not a dollar cap. Shared RPM/TPM limits can be set
through the example environment file.

DeepSeek's weekday peak windows are 01:00–04:00 and 06:00–10:00 UTC; other times, including weekends,
are off-peak. The guard runs before **every** HTTP attempt, after rate limiting, and refuses dispatch
within one timeout plus 15 seconds of the next peak window. See the
[official pricing schedule](https://api-docs.deepseek.com/quick_start/pricing/).
This controls client dispatch and leaves a completion margin; only the provider can confirm the
actual billing regime. Peak deferrals exit immediately rather than sleeping or scheduling work.

## Outputs, failures and reuse

Each invocation creates a fresh directory under `runs/construction/`:

| File | Contents |
| --- | --- |
| `manifest.json` | Run status, model settings, source/prompt/implementation hashes, budgets, trial, request/cache counts |
| `sources.jsonl`, `timelines.jsonl` | Indexed sources and both extractions; timelines are candidates pending audit |
| `requests.jsonl`, `transport.jsonl`, `calls.jsonl` | Exact stage requests, transport attempts/raw bodies, parsed transport envelopes and usage |
| `excluded_targets.jsonl`, `rejected.jsonl` | Eligibility exclusions, invalid outputs and audit rejections |
| `audits.jsonl`, `case_results.jsonl` | Complete audits and per-case counts |
| `inputs.jsonl` | Exported model-facing inputs; no gold answers or source metadata |
| `outputs.jsonl` | Paired hidden labels, provenance and case clusters, joined by `item_id` |
| `construction_metrics.json` | Candidate/accepted/rejected counts per constructor, event-type counts and cluster count |

An exit code of `0` means construction completed with at least one accepted item; it does not mean
all candidates passed. `2` means invalid CLI/preflight input or a completed run with no accepted
items; inspect the message and manifest. `1` means a failed run. `75` means deferred by the schedule
or request budget. A failed/deferred run can contain partial exports: **consume only completed
runs**, and retain rejection denominators when reporting them.

Rerunning with the same settings resumes through exact response reuse in `runs/construction_cache/`
and creates a new ledger. Request identity includes model configuration, prompt/schema hashes,
payload, token/timeout settings, trial and synthetic/live namespace. Saved stage responses include
malformed stage JSON so an identical invalid response is not repeatedly regenerated. Transport
errors, invalid envelopes and truncated completions are logged but are not successful stage-cache
entries. Changing `--trial` explicitly requests another sample. Changing a prompt or token budget
also changes request identity. Do not delete caches to hide failed attempts or pool favorable retries.

## What remains before a benchmark release

Run the small development comparison and measure source coverage, audit rejection reasons, option
ambiguity, output validity, latency and provider-reported usage. Inspect exported examples; software
tests and model agreement do not certify labels. Full-source extraction can still inject hindsight
into a prefix, and the independent audit can still miss it. The current ending-invariance test covers
the compiler; extraction invariance needs a separate development experiment.

The evaluation runner, probability-score implementation, repeated forecasts, empirical difficulty
calibration, automatic near-duplicate detection, uncertainty intervals and final dataset release
are not built here. Keep an objectively sampled reference set. Any subset selected by model
disagreement or failures must be separately labeled and reported. Cluster statistics by case and
report forecast scores by event type. Freeze prompts and selection rules before fresh test cases.

With no human reviewers, the resulting labels remain model-assisted. Source provenance, independent
checks, negative controls and transparent rejection logs reduce identifiable errors; they cannot
establish that every accepted item is clinically complete, uniquely predictable or free of bias.
