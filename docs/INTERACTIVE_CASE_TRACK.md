# Interactive case-report track

Design adopted 7 November 2026 in D-24. An offline pack validator and observed-only request
resolver are implemented in [`interactive.py`](../src/clinical_orchestra/interactive.py), with
negative-control software tests. **No accepted interactive cases, isolated runner, solver runs or
scores exist yet.** This is a separate experimental benchmark track, not another score for the fixed-prefix
items. It can use the same eligible, article-licensed case pool and the same psychiatry, neurology
and integrated neuropsychiatry assignments, but requires its own case-level inclusion audit.

## Why add it

[SDBench](https://microsoft.github.io/sdbench/) begins with a short summary, lets an agent ask
questions and order tests, and uses a gatekeeper with access to the full published case narrative.
Its [case schema](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/case_data.py)
contains `case_summary`, `full_text` and `final_diagnosis`. For its NEJM series, the source is the
published Case Records article, not an additional unpublished chart according to the public
[dataset description](https://microsoft.github.io/sdbench/). That makes an interactive task
possible in principle for our published cases too. The article may contain far more information
than the initial presentation, but its discussion, later course and final diagnosis cannot be
shown to a solver at the starting cutoff.

SDBench returns a plausible synthetic result when a requested test is absent from the report.
This is useful for a simulated diagnostic game, but the synthetic result is not an observed patient
fact. Our first track will answer only from documented evidence and return `not_documented` or
`not_available_at_cutoff` otherwise. A synthetic-continuation study, if ever added, needs a separate
dataset version and report; it must not enter any observed-result or clinical-outcome score.

## First task contract

One case is one isolated encounter. The agent sees a short, audited presentation and a frozen
**common request menu** of patient questions and orderable tests. The menu comes from a
development-only clinical vocabulary, not from the tests mentioned in this case; otherwise the
menu itself reveals the article's course. The agent may request menu IDs within a fixed budget and
may submit a terminal prediction at any turn. A pilot should use a frozen diagnosis candidate slate
made from the initial presentation only, plus exact candidate-ID scoring. A later general next-step
endpoint can use the same request history
before a fixed-prefix forecast, but must be reported as a different task. Never merge either with
the existing five-family score.

The host stores a case pack with an initial presentation, an anchor time/phase, permitted request
IDs, and evidence cards. Each card has a request ID, a response, source quote and source location,
clinical time, known-at phase, status, and any prerequisites. Construction validates the quote in
the article and the two chronologies before freezing the pack. A card can answer an order only if
the test was actually performed in the report and its finding belongs to the declared stable
episode. If progression, treatment or a major state change intervened, an earlier order cannot
be assumed to have produced the later result. Such a card is ineligible at that anchor. Multiple
facts reported in one phase remain an unordered bundle.

At runtime the solver receives only the presentation, menu, its own requests and the broker's
responses. The full article, source quotes, hidden cards, final diagnosis, construction/audit files
and score are absent from the solver process and tool mounts. The host resolves exact menu IDs;
free-text query routing is a separate policy experiment because semantic matching can introduce
model bias and leakage. The broker returns one of:

| Status | Meaning |
| --- | --- |
| `documented` | A source-supported finding valid for the request and anchor; return its clinical wording and evidence-card ID, but no future article text. |
| `not_documented` | The article does not report the requested result. This says nothing about what the actual patient result would have been. |
| `not_available_at_cutoff` | The record has a finding, but its timing or prerequisites make it unavailable under this encounter contract. |
| `ambiguous` | Evidence cannot support one unambiguous response; exclude the card from scored release until resolved. |

Do not let a model fill `not_documented` with a plausible value. A test may be requested repeatedly,
but the host returns the same frozen response, counts every request, and records the repeated call.
The agent can reason about uncertainty; the broker cannot manufacture information to keep a
conversation moving.

The current Python resolver is a **host-side component**, not an isolation mechanism. A solver
running in the same process with access to its `CasePack` could inspect hidden cards and gold.
The future worker must put the pack in a separate host process or inaccessible mount, validate it
before assignment, enforce request budgets, and journal every request/result. A missing card
currently means `not_documented`; construction audit must check that this is not merely an omitted
reported result.

## Construction and admission

1. Use D-22's article-level rights, correction, duplication and date checks, then D-23's exclusive
   specialty assignment. Split by article/patient before prompt or menu development. Use only
   development cases to design menus, prompts, routing and scoring.
2. Extract the two D-17 chronologies and identify a genuine clinical anchor. Create a short
   presentation from facts known by that anchor; audit every sentence against its quote. Remove
   article framing, title clues, expert discussion and retrospective diagnoses.
3. Independently extract candidate question/test cards. For each, verify the request-to-result
   relation, verbatim quote, known-at phase and clinical-time stability. A separate audit model
   checks omissions, contradictions and leakage; mechanical checks reject missing quotes and
   invalid references. Disagreement or unresolved chronology excludes the card.
4. Select cases under **predeclared** criteria: a supported terminal endpoint, a non-revealing
   presentation, at least two usable nontrivial cards in the common menu, and no unresolved
   timing/identity problem. Do not select on one solver's mistakes or SDBench's NEJM case list.
   Report the case and card rejection funnel by specialty.
5. Freeze case packs, menu, prompt, endpoint options, budgets and scores before comparing models.
   Hold out full cases, not turns or cards from cases used in development. Run negative controls
   for requests for the diagnosis, future course, article text and tests not in the source.

The first pilot should be small and deliberately audited. The old 99 post-cutoff items and the
unreviewed specialty discovery candidates cannot be used to tune this track. The current five
historical timelines are insufficient as interactive packs: their event quotes establish some
reported events, but not complete request coverage or safe response timing.

## Evaluation and interpretation

Report terminal exact-choice accuracy and probability scores for valid submissions, with every
assigned case in the operational denominator. Also report request count, repeated requests,
`not_documented` and `not_available_at_cutoff` rates, completion/failure classes, actual API cost
and latency. Show accuracy by request budget and against a matched no-request baseline with the
same model and final-answer contract. If a request has a standardized *estimated* clinical charge,
report it separately from API expense and from actual patient charges; do not optimize a combined
score until its tradeoff is declared in advance. Cluster uncertainty by case/article and report
the three specialty tracks separately.

This measures performance in a constrained published-case information game. It does not show that
the agent chose clinically optimal tests, that an unreported test was negative, or that its actions
would cause the published outcome. The authored case narrative may make some trajectories unusually
predictable; report the selection funnel and avoid general-population claims. Model-mediated
construction without human review cannot establish clinical validity, so the first release remains
an exploratory benchmark with explicit error audits.
