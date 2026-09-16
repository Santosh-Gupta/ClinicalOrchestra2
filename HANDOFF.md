# Handoff — Clinical Orchestra 2

Written 2026-09-16, at the end of the first build session. Everything below is current as of commit
`a69be2b` plus the documentation commit that adds this file.

If you read nothing else, read **§1**, **§3**, and **§8**.

---

## 1. What this project is, in one paragraph

A benchmark that asks a model to predict **what happens next in a clinical case**, and a harness to
be built on top of it later. The previous project (`ClinicalOrchestra`, published and paused) tried
to benchmark *diagnosis* and failed for two reasons: the test items were invented by an LLM, so their
quality was capped by the model writing them; and scoring free-text diagnoses needed an LLM judge
that was noisy enough to fake results. Predicting the next event fixes both, because the correct
answer is **extracted from what actually happened in the case report** rather than invented, and
because many answers can be graded mechanically. The full reasoning is in
[docs/LESSONS_FROM_V1.md](docs/LESSONS_FROM_V1.md).

**Status: the dataset pipeline works end to end on real data.** There is no evaluation runner and no
harness yet. Nothing has been evaluated against any model.

---

## 2. Read these first, in this order

1. **[README.md](README.md)** — orientation.
2. **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** — what has been decided and why, D-01
   through D-15. **This is the most important file in the repo.** Most of the code looks like it has
   removable complexity until you read the decision that forced it.
3. **[AGENTS.md](AGENTS.md)** — the working rules, each stated with the v1 failure it came from.
4. **[docs/LESSONS_FROM_V1.md](docs/LESSONS_FROM_V1.md)** — what went wrong last time.
5. **[docs/BRAINSTORM_ROUND2.md](docs/BRAINSTORM_ROUND2.md)** — the design the current code follows,
   *and* the proposed harness (§"The harness"), which is not built.
6. **[DESIGN_BRAINSTORM.md](DESIGN_BRAINSTORM.md)** — the earlier first-pass design. Kept for
   comparison. **Several of its proposals were explicitly rejected** — see D-05 and D-08. Do not
   implement from this file without checking the decision registry first.

---

## 3. Environment setup — all four parts are required

Every one of these has caused a confusing failure at least once.

```bash
# 1. python3.11 specifically. The system python3 is 3.8 and will fail on modern syntax.
# 2. Without SSL_CERT_FILE every HTTPS call dies with CERTIFICATE_VERIFY_FAILED.
export SSL_CERT_FILE=$(python3.11 -c "import certifi;print(certifi.where())")

# 3. API keys. They live in the v1 repo and are gitignored. Never commit or print them.
set -a && . /Users/santoshg/Coding/ClinicalHarness/.env.crossmodel.local && set +a

# 4. The package is not installed; everything runs from source.
export PYTHONPATH=src
```

Run the tests to confirm the setup: `PYTHONPATH=src python3.11 -m unittest discover -s tests`
(26 tests, all passing, no network required).

**Note on the working directory:** the shell's cwd does not reliably persist between tool calls. Use
`cd /Users/santoshg/Coding/clinical-orchestra-two && ...` in each command rather than assuming it.

---

## 4. What exists

~2,100 lines of source across 13 modules, 7 scripts, 26 tests.

### Carried over from v1, task-neutral (do not rewrite these)

| Module | Purpose |
| --- | --- |
| `model_client.py` | Clients for OpenAI-compatible `/chat/completions` and OpenAI's `/responses`. Handles provider quirks, retries, and **raises loudly on truncated output** rather than passing partial results downstream. The system prompt is a parameter (it was hardcoded to diagnosis in v1). |
| `ratelimit.py` | Shared sliding-window RPM/TPM limiter. Unchanged. |
| `ncbi.py`, `pmc.py`, `pubmed.py` | NCBI E-Utilities, PMC full text, PubMed. `pmc.py` was **modified** — see §8. |
| `ledger.py` | Append-only run logging. Rewritten to be schema-agnostic (v1's imported diagnosis schemas). Writes a manifest, an event log, and named JSONL streams; refuses to write into an existing run directory. |

### Written for this project

| Module | Purpose |
| --- | --- |
| `registry.py` | Loads `models.toml` and builds clients from it. Nothing hardcodes a model ID. |
| `licensing.py` | Classifies article licences. Stricter than a substring check for a reason — see §8. |
| `events.py` | The event schema (`Event`, `CaseTimeline`), the five event types, the yield tiers, and **`is_grounded` / `validate_timeline`** — the check that every extracted event quotes the source. This is the core integrity mechanism (D-06). |
| `extract.py` | The extraction prompt and the parse/validate/drop loop. |
| `items.py` | Turns timelines into items, and holds **all the grading rules** (`credit_for`, `later_credit`, `ndcg`). The grading constants live here by name, so a change to the scheme is one edit. |
| `peak.py` | Whether a DeepSeek request falls in the peak-price window. Fixed UTC clock, computed locally. |

### Scripts

| Script | What it does |
| --- | --- |
| `discover_models.py` | Asks each provider which model IDs it exposes. Run this before guessing an ID. |
| `probe_models.py` | Sends one small real request per model; records latency, tokens, JSON compliance, and whether temperature 0 was honoured. Writes to `runs/probes/`. |
| `fetch_cases.py` | PMC search + fetch + licence filter + length filter → `data/cases/*.json`. |
| `build_timelines.py` | Extraction + validation → `data/timelines/*.json`, with rejects logged to `runs/extraction/`. |
| `build_items.py` | Timelines → `data/items.jsonl`, plus a type/flag summary. |
| `estimate_cost.py` | Prices a run using sizes **measured from the corpus on disk**. |
| `peak_check.py` | Is DeepSeek at peak rates right now, and the next 24h in UTC and local time. |

---

## 5. The pipeline, end to end

These commands have all been run successfully. Do the environment setup in §3 first.

```bash
# 1. Fetch cases. Objective selection only; no model sees a case before it is cached.
PYTHONPATH=src python3.11 scripts/fetch_cases.py \
  --from 2026/06/01 --limit 40 \
  --query "neurology OR neurological OR seizure OR encephalitis" \
  --email santosh.gupta.eng@gmail.com --out data/cases
```

```bash
# 2. Extract timelines. Slow: roughly 20-30s per case. 6 cases exceeded a 120s foreground timeout,
# so run larger batches in the background.
PYTHONPATH=src python3.11 scripts/build_timelines.py --model gemini-3.5-flash --limit 6
```

```bash
# 3. Build items.
PYTHONPATH=src python3.11 scripts/build_items.py
```

```bash
# 4. Price a bigger run before committing to it.
PYTHONPATH=src python3.11 scripts/estimate_cost.py --cases 200 --samples 5
```

### Current data state (committed to the repo)

- **16 cases** in `data/cases/` — post-cutoff (published from 2026-06-01), CC-BY/CC0 only.
  Mean 20,353 characters.
- **5 timelines** in `data/timelines/` — 12 to 30 events each. One case was rejected by the
  validator (`too_many_established`), which is the validator working.
- **99 items** in `data/items.jsonl` — 41 action, 29 result, 15 progression, 7 diagnosis,
  7 response. Mean 19.8 items per case.
- `runs/` is gitignored and holds the probe and extraction logs.

**The corpus is deliberately tiny.** It is a working sample to prove the pipeline, not a dataset. The
fetch query matched 4,719 candidates, so scaling is a matter of raising `--limit`.

---

## 6. What is NOT built, in priority order

1. **The evaluation runner.** Nothing has been evaluated against any model yet. This is the single
   largest gap. It needs to: load items, ask the model the typed question, record the raw response,
   match the answer to an event, apply `items.credit_for`, and report per type (D-04). **Order
   evaluation case-by-case, not shuffled**, so the shared prompt prefix hits provider caches — see
   §9.
2. **The answer matcher.** `credit_for` takes a `matched_event_index` and applies the grading rules;
   *deciding* that index from free text is not implemented. This is blocked on the closed vocabulary
   (D-08). Until then, the honest options are the ranking task (D-09) or a recorded-and-audited LLM
   mapping with its error rate reported.
3. **The closed action vocabulary** (D-08). 200–400 hand-curated action classes at clinical
   granularity. Blocks item 2.
4. **The candidate-slate builder** for the ranking task (D-09). `items.ndcg` exists and is tested;
   the slate builder and its hard negatives do not. Hard negatives are the part that matters.
5. **Difficulty calibration by model disagreement** (D-10). Needs at least two working models, so it
   is partly blocked on §10.
6. **Corpus scale-up.** Straightforward once the above is settled; budget ~2.5 fetched articles per
   usable case (D-11).
7. **The harness.** Not started, by design — the benchmark comes first. The proposed approach is in
   `docs/BRAINSTORM_ROUND2.md` under "The harness": decompose next-step selection into value of
   information over the model's own differential. Its key property is that it turns the verifier's
   question from "is this diagnosis right" (defeasible, no oracle — what killed v1) into "does this
   test distinguish A from B" (factual, checkable). It must beat a strong multi-sample
   self-consistency baseline, which may well win.

---

## 7. Known problems with the current data

All three were found by inspecting real output, and all three are recorded in the data rather than
hidden.

1. **Triviality.** The first case inspected is a goat farmer who drinks unpasteurized milk and
   handles abortion material — the presentation hands you brucellosis before any test. Many decision
   points will be obvious, and the benchmark will saturate without D-10.
2. **Bundled actions.** 11 of 41 action items (27%) name several orderable things in one event
   ("doxycycline and rifampin", "blood cultures and Wright agglutination test"). These are not
   errors in the source — clinicians really do order several things at once — but they cannot be
   graded as a single answer. They carry a `bundled_action` flag. This is the argument for the
   budgeted-set variant ("name up to three things").
3. **Hindsight leakage in the presentation.** Case reports are written backwards from a known answer.
   "A 34-year-old with no history of travel" reveals that someone already thought travel mattered.
   Redacting later events does not remove this, and no code currently detects it. This is the
   deepest unsolved problem in the dataset; see `docs/BRAINSTORM_ROUND2.md` §4.

---

## 8. Gotchas discovered the hard way

Each of these cost real debugging time. Do not rediscover them.

**`SSL_CERT_FILE` is mandatory.** Without it every HTTPS call fails with
`CERTIFICATE_VERIFY_FAILED`. Carried over from v1.

**TOML table keys containing dots must be quoted.** `[gemini-3.8-flash]` parses as nested tables
`gemini` → `3` → `8-flash`. Write `["gemini-3.8-flash"]`. This is why `pricing.toml` quotes every key.

**PMC licences are not in the `license-type` attribute.** Current records put the licence in an
`ali:license_ref` child element holding a URL. v1's attribute-only lookup returned `None` for *every*
article, which silently rejected the entire corpus. `pmc.py::_license_type` was modified to read the
child element, prefer the URL (it names the exact variant), and fall back to attributes.

**`"cc-by" in text` also matches `"cc-by-nc-nd"`.** A naive substring check admits the most
restricted licences in the corpus. `licensing.py` tests patterns most-specific-first and excludes
no-derivatives licences entirely.

**Result items must be graded on `detail`, not `summary`.** The gold summary
"Wright agglutination test result" simply restates the question; the answer is in `detail`
("positive at a titer of 1/160"). `items.answer_field` picks the right field per type. Grading
`summary` for every type would make every result item trivially correct.

**Zero dropped events is not proof the grounding check works.** It fired zero times on the first run.
Confirm with negative controls before trusting it — change one word in a real quote and check it is
rejected. (It is; see `is_grounded`.)

**Extraction is slow.** ~20–30 seconds per case. Six cases exceeded a 120-second foreground timeout.
Run batches in the background and poll the output file.

**Piping output through `tail` buffers everything** until the process exits, which makes a
backgrounded run look hung. Write to a file or leave it unpiped.

---

## 9. Models, API status, and cost

Verified by real API calls on 2026-09-07 via `scripts/probe_models.py`. Model IDs came from
`discover_models.py`, not from guesswork.

| Model | ID | Status |
| --- | --- | --- |
| Gemini 3.8 Flash | `gemini-3.8-flash` | Works, ~3.2s |
| Gemini 3.5 Flash | `gemini-3.5-flash` | Works, ~1.7s. **Used for all extraction so far.** |
| ChatGPT Luna | `gpt-5.6-luna` | Works, ~3.7s. **Rejects a custom temperature** — see below |
| Claude Sonnet 5 | `claude-sonnet-5` | **HTTP 400, credit balance too low** |
| GLM Flash | — | **No API key configured** (`XM_ZHIPU_KEY`) |
| Kimi K3 | — | **No API key configured** (`XM_MOONSHOT_KEY`) |

**`gpt-5.6-luna` cannot run at temperature 0.** It returns HTTP 400 on the parameter; the client
drops it and retries, so the model runs at its own default. The project-wide temperature-0 rule
cannot apply to it — use multi-sampling instead. The registry records this.

**Gemini bills thinking tokens at the output rate** and spends them freely: a 74-token probe billed
245 total tokens. This is most of why it is ~13x more expensive than the cheapest option.

### Cost, priced against measured corpus sizes

200 cases (~3,960 items), 5 samples per item. Reproduce with
`scripts/estimate_cost.py --cases 200 --samples 5`.

| Model | Extraction (one-time) | Eval pass | Total |
| --- | --- | --- | --- |
| Muse Spark 1.3 contributor | $0.21 | $2.42 | **$2.63** |
| GLM-5.3-Flash | $0.40 | $4.47 | $4.87 |
| DeepSeek V4 Flash | $0.55 | $6.01 | $6.56 |
| GPT-5.6 Luna | $0.77 | $9.60 | $10.37 |
| Gemini 3.8 Flash | $2.55 | $31.55 | $34.10 |
| Muse Spark 1.3 standard | $3.35 | $37.45 | $40.81 |

**Cost is not the binding constraint.** v1 died partly of API spend; at these prices a full
cross-model study is tens of dollars. Construction difficulty is the real constraint.

**Prompt caching is the biggest lever, and it fits this benchmark unusually well.** Every item from
one case repeats that case's presentation and course so far, so items within a case share a long,
strictly growing prefix. DeepSeek cache hits are ~30x cheaper than misses; GLM's are 5x. **Order
evaluation case-by-case rather than shuffling items** and most input tokens become cache hits. Design
the runner around this from the start.

**DeepSeek has peak/off-peak pricing.** Peak is 01:00–04:00 and 06:00–10:00 UTC, Monday–Friday, and
costs exactly double. It is a fixed clock, not a load signal, and the API does not report it — use
`scripts/peak_check.py`. In US Pacific that is 18:00–21:00 and 23:00–03:00, so evening runs pay
double by accident. Caveat: DeepSeek's own pricing page still describes the surcharge as inactive,
but that page predates the 2026-08-16 change; the schedule is corroborated by two independent
secondary sources and should be sanity-checked against a real invoice.

**Prices go stale fast.** `pricing.toml` stamps each entry with the date it was checked. GLM's launch
promo expired on 2026-09-09 and its rates doubled, which is already reflected. Re-check before
quoting any budget.

---

## 10. Blockers that need Santosh

1. **Fund the Anthropic account.** The key is valid; the balance is not. This blocks `claude-sonnet-5`
   and therefore blocks difficulty calibration, which needs several models.
2. **Add `XM_ZHIPU_KEY` and `XM_MOONSHOT_KEY`** if GLM and Kimi are still wanted. Both entries exist
   in `models.toml`, disabled, with `UNVERIFIED` model IDs — run `discover_models.py` after adding a
   key and pin the real ID rather than guessing.
3. **Confirm the specialty scope.** Everything so far is neurology-weighted because that is what the
   fetch query asked for. Widening it is a one-line change but affects what the benchmark claims.

---

## 11. Suggested plan for the next session

1. Re-run the tests and `probe_models.py` to confirm the environment still works and to see whether
   the blocked models are now available.
2. Build the **candidate-slate builder** and run the **ranking task** first (D-09). It is fully
   deterministic, it needs no vocabulary and no matcher, and it gets a real number on the board
   fastest. Hard negatives from similar decision points in other cases are the part to do carefully.
3. With two or more working models, run **difficulty calibration by disagreement** (D-10) on the
   existing 99 items, and see how many survive as non-trivial. This will probably be sobering, and
   it is better to learn it at 99 items than at 4,000.
4. Only then scale the corpus.

Resist scaling the corpus before the metric is trustworthy. The v1 failure was not a shortage of
data; it was data whose labels and scoring could not be defended.

---

## 12. House style

Santosh wants documentation and prose to be **plain, literal, and easy to understand** — not clever,
not mannered, not "interesting." He does his own editing pass and adds his own voice. Write direct
declarative sentences, state numbers and facts plainly, and do not add flourish or content he did not
ask for. This applies to commit messages, docstrings, comments, and any user-facing writing.
