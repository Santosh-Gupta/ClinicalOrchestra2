# Harness learning agenda

Adopted 7 November 2026 in D-25. The purpose of the evaluation program is to learn **when, why
and for whom** a harness component changes a forecast. A best-scoring configuration may emerge,
but it is not the only useful outcome. A null result, a harm on one task family, or a cost increase
without a reliable gain is a result worth reporting. This agenda applies to the fixed-prefix
next-event benchmark and, once it has accepted cases and an isolated runner, the separate D-24
interactive track. Their outcomes are never pooled into one headline score.

No experiment in this page has been run. D-21's frozen tasks, input isolation, attempt journal,
deterministic scoring, assigned-item denominators and case-clustered analysis are prerequisites.
The [general harness review](GENERAL_HARNESS_ENGINEERING_2026-10-10.md) gives the evidence and
measurement rules behind those prerequisites.

## Questions and identifiable contrasts

| Question | First controlled contrast | What it can teach |
| --- | --- | --- |
| Does external information help at all? | Direct forecast versus a fixed, permitted evidence packet, using the same model and final-answer contract. Compare also with an extra-call no-evidence control. | Evidence value separate from merely giving the model more inference. |
| When should retrieval occur? | Give the **same frozen evidence packet** before the first forecast, after a saved provisional forecast, or after a saved self-directed uncertainty assessment. Match final-call budget and total information. | Timing effect, rather than a change in retrieved content. |
| When should retrieval be triggered? | Fixed one-request policy versus a predeclared confidence/uncertainty trigger versus model-chosen request, at the same maximum budget. | Whether selective retrieval saves cost or avoids harm. This is a different experiment from timing because selected evidence can differ. |
| Should the model finish an initial pass first? | Save a provisional probability vector before tool access; compare a condition that receives evidence immediately with one that must first submit that vector and a short uncertainty note. | Effects of committing an initial view, including anchoring and correction. Internal private reasoning completion cannot be observed or reliably timed; the intervention is an observable checkpoint. |
| How many agents help? | One agent versus two and three independent agents with a fixed aggregation rule, holding total calls, token ceiling, evidence access and final-answer schema as close as possible. Include one-agent repeated samples. | Diversity or review benefit beyond simply spending the same compute on one model. |
| What capability should each agent have? | Under the same total budget: strong single agent; several cheaper independent agents; cheap scouts plus strong final integrator; strong independent agents. Record actual model IDs and prices. | Whether specialization or model mix changes accuracy, calibration, failure rate and cost. These are **systems**, not intrinsic model rankings. |

For the interactive track, retrieval means requesting a documented evidence card. Its missing and
later-unavailable responses are outcomes, not negative findings. For an external-literature tool,
exclude the case's own article and identifiable copies and log what was excluded. Do not mix the
two evidence sources in a first timing experiment: article-card disclosure and literature search
have different semantics and risks.

## Minimum experiment sequence

1. Build the common measurement core and run direct and repeated-request baselines on accepted
   **development** cases. Verify that a nonconforming response and a failed call remain in the
   assigned denominator. Keep the initial vector for every enhanced policy.
2. Test the value of one fixed evidence packet against both baselines. If the packet is useless or
   harmful, investigate coverage and delivery before optimizing its timing. Record retrieval
   eligibility, actual response, source date, empty results and provenance.
3. With packet content fixed, randomize or counterbalance timing across the same cases and model.
   Do not let early versus late conditions retrieve different facts; that would conflate timing
   with content. Equalize maximum calls and report realized calls separately.
4. Then test fixed versus selective triggering. Choose trigger thresholds on development cases
   only. Compare to a cost-matched random trigger as a control for simply retrieving less often.
5. Only after the one-agent behavior is understood, compare agent count and capability mixes.
   Use fixed aggregation or reviewer schedules, no undeclared debate rounds, and a strong
   repeated-sample single-agent control. Run at least two backbone/provider families before
   claiming a general harness effect.
6. Freeze a small set of contrasts and repeat them on untouched case clusters. Report the full
   exploratory search history and keep the confirmatory result distinct. If no accepted cases or
   second constructor family is available, remain at software validation rather than substituting
   the historical post-cutoff 99 items for development.

This is a staged sequence, not a demand to run every factorial combination. A full crossing of
timing, trigger, agent count and capability would consume many comparisons and obscure which
mechanism mattered. Start with simple main effects, then examine interactions only where pilot
data and a declared hypothesis justify them.

## What every run must preserve

The unit of assignment is a frozen item or interactive case; the unit of uncertainty is the
patient/article cluster. The source split, visible information, options, scoring rule, model
version, provider settings, runtime, tool permissions, maximum budget and prompt version are
recorded before the run. Interleave policy conditions within provider time windows while keeping
each case's growing prefixes in order for caching. Do not transfer generated memory between
cutoffs or cases. Record actual rendered messages, request/response IDs, tool results, token use,
latency, cache use, price basis, failures and every submitted forecast. If a model's answer is
identical across conditions, reuse the deterministic score rather than calling any judge again.

The primary outcomes are per-family operational accuracy across **all assigned** items, valid-only
Brier and log loss with denominators, completion, and API cost/latency. For the interactive track,
also show accuracy by request budget, observed-card coverage and unavailable-request rates. Show
paired within-case changes from initial to final forecast: wrong-to-right, right-to-wrong, Brier
change even when the top choice stays fixed, and confidence change after evidence. Do not call a
retrieval-induced change clinically correct merely because it matches a published course; inspect
whether the returned evidence truly supports it. Report heterogeneity by task family, specialty,
initial uncertainty and evidence availability without turning exploratory subgroups into claims.

The goal is to estimate a **frontier**, not crown one winner: what accuracy and calibration are
achievable at each call, token, time and dollar budget, and where extra complexity ceases to help.
Predeclare a practical cost ceiling and the smallest effect worth pursuing for each confirmation
study. If an enhancement helps only a narrow subgroup, publish that conditional result instead
of silently routing cases using knowledge of their labels.

## Main confounds to guard against

- **More thinking versus better information:** extra model calls must have a matched no-evidence
  control. Saving a provisional answer must not itself receive answer-bearing feedback.
- **Retrieval timing versus retrieval content:** freeze the packet in the timing study. Test adaptive
  query choice separately.
- **Agent count versus budget or model strength:** account for every scout, integrator, reviewer,
  retry and tool call; compare equal-budget systems and report realized spend.
- **Case dependence and selection:** keep all items from a patient/article together, do not select
  cases by one model's mistakes, and preserve the specialty and construction rejection funnels.
- **Outcome versus task validity:** exact scoring does not prove clinical adequacy. Keep source
  support, chronology uncertainty, synthetic/unavailable status and LLM-only audit limits visible.
