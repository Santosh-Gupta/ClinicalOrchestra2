# AGENTS.md — start here

This repo is worked on by multiple agents, sometimes running on different models. Read this before
changing anything.

## Read first

1. **[HANDOFF.md](HANDOFF.md)** — current state, environment setup, what is not built yet, and the
   gotchas that cost real debugging time. Start here.
2. **[docs/DESIGN_DECISIONS.md](docs/DESIGN_DECISIONS.md)** — what has been decided and why, D-01
   through D-15. Most of the code looks like it has removable complexity until you read the decision
   that forced it.
3. **[docs/LESSONS_FROM_V1.md](docs/LESSONS_FROM_V1.md)** — the mistakes this project exists to avoid.
   Most of the rules below look removable until you read why they're here.
4. **[docs/BRAINSTORM_ROUND2.md](docs/BRAINSTORM_ROUND2.md)** — the design the current code follows,
   and the proposed harness, which is not built.
5. **[DESIGN_BRAINSTORM.md](DESIGN_BRAINSTORM.md)** — the earlier first-pass design, kept for
   comparison. Parts of it were explicitly rejected (see D-05 and D-08). Do not implement from this
   file without checking the decision registry first.

## Rules that came from v1 failures

Each of these cost real time and money to learn. Don't drop one without writing down what changed.

- **Every model call runs at temperature 0.0 where the provider allows it**, and every response is
  written to disk before anything is derived from it. Note that temperature 0 is not the same as
  determinism — batched inference on the provider side can reorder floating-point operations, so
  identical inputs can still produce different outputs. Persist responses; don't assume you can
  regenerate them.
  **Some models reject the parameter** and run at their own default — `gpt-5.6-luna` and Anthropic's
  OpenAI-compat layer both do. The client drops temperature after a 400 and retries, and the probe
  report records which models this happened to. Those models need multi-sampling instead of a pinned
  temperature, and any claim of reproducibility must exclude them.
- **Never re-judge identical output.** If a model's answer is unchanged between two conditions, reuse
  the earlier score. In v1, re-judging identical lists produced score differences that looked like
  real effects and were not.
- **Post-cutoff cases are test-only.** Never tune the harness, prompts, or thresholds against them.
  Development happens on the development split.
- **Exclude a case's own source article** from any retrieval run, by DOI, PMCID, and title, and record
  in the run manifest what was actually excluded. Describe the result as "reduced memorization risk,"
  never as proof the model hadn't seen the case.
- **Beat the no-tool baseline before claiming a tool helped.** The baseline must be a strong one:
  multiple samples from the model, combined. Much of v1's apparent retrieval improvement was really
  the model getting more chances to say what it already knew.
- **A tool adds or flags; it does not overwrite.** v1's only clearly positive harness result came from
  leaving the model's confident answers alone and letting retrieval fill only the slot it wasn't using.
  Letting retrieval replace the model's answers made results worse.
- **A checker must be independent of what it is checking.** A model verifying its own edit approves
  it. Use a rule, a different and stronger model, or — during development only — the case's real
  trajectory as an oracle.
- **Don't select cases by one model's failures.** v1's hard set was built from one model's wrong
  answers, which makes scoring that model on it circular. Select by objective criteria, and report
  any model-conditioned subset separately.
- **Fail loudly.** Truncated responses, empty plans, dropped items, and changed denominators must
  raise, not degrade quietly. Log every fallback and the exact denominator behind every number.
- **Report what was scored deterministically versus by a model judge**, separately. Don't fold a soft
  signal into a headline number.

## When you make a change

- A significant design decision goes in `docs/DESIGN_DECISIONS.md` with the reason and the evidence,
  as the next D-NN entry. Superseding an earlier decision means writing a new entry that says so and
  marking the old one `Superseded by D-NN`, not editing the old one away.
- Keep `HANDOFF.md` current as you go. It is what the next agent reads first, and a stale handoff is
  worse than none.
- Something durable learned about the data or the task goes in `journal.md`, citing the case.
- A decision recorded only in a commit message is invisible to the next agent. Don't do that.

## Boundaries

- This is benchmark and information-retrieval research. It is not a clinical decision-support system,
  and nothing here should be presented as one.
- API keys live in a gitignored local env file and are never committed.
