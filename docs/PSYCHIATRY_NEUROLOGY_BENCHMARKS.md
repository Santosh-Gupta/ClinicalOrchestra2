# Three specialty tracks for next-step forecasting — 2026-10-16

These are three **separate benchmark tracks** using one construction and scoring protocol:
psychiatry, neurology, and integrated neuropsychiatry. The first two are deliberately strict
"pure" cohorts. The third is enriched to find many cases in which psychiatric and neurological
information interact. It is a challenge cohort, **not** an assertion that every item in it is
harder. Difficulty must be measured on frozen items, with case-clustered uncertainty.

This page is the intake and labeling contract. The linked
[`specialty_candidates_2026-10-16.json`](../data/discovery/specialty_candidates_2026-10-16.json)
is a search ledger, **not** an accepted dataset or a list of benchmark inputs/outputs. Search hits
have not received clinical labels. The 99 historical post-cutoff items are outside this design and
must not be used to adjust its definitions or queries.

## What qualifies

Classify the **patient/report cluster** once, before choosing question cutoffs. A source belongs to:

| Track | Case-level rule | Item-level headline rule |
| --- | --- | --- |
| Psychiatry | Psychiatric presentation, assessment, management or course is material; neurological disease, signs and workup are absent or incidental to the documented decision sequence. | The next event is a psychiatric action, result, assessment, progression or treatment response. |
| Neurology | Neurological presentation, assessment, management or course is material; psychiatric disease, signs and workup are absent or incidental. | The next event is a neurological action, result, assessment, progression or treatment response. |
| Integrated neuropsychiatry | Both domains materially affect the same patient's assessment, management or trajectory, with source evidence for the interaction. Mere keyword co-occurrence, routine screening, or a late discussion-section theory is insufficient. | At least one psychiatric and one neurological fact are known **before the cutoff**, and the forecast target is linked to both. Record the exact facts, their first-known times and source spans. |

A mixed report can contain single-domain items, but only its integrated items contribute to the
mixed headline score. It must not be duplicated into the pure cohorts. If classification remains
uncertain after independent review, keep it in an unresolved ledger and out of headline sets. One
report with several patients is ineligible until patient-specific chronology and outcomes can be
separated; linked reports about the same patient share a cluster and a split.

The mixed track should include different interaction mechanisms rather than only famous diagnostic
reversals: psychiatric symptoms during neurological illness; neurological findings that change a
psychiatric assessment; treatment interactions or adverse effects across specialties; functional
neurological symptoms with psychiatric care; and longitudinal changes in cognition, mood, behavior
or seizures. These are discovery strata, not answers. A psychiatric symptom with a neurological
cause is **not automatically** an integrated case; the psychiatric phenomenology or care must
actually matter. Conversely, a normal neurological screen alone does not move a psychiatric case
into the mixed track.

## Discovery and sampling

The frozen journal frame is BMC Neurology, BMC Psychiatry, BJPsych Open, Frontiers in Neurology,
Frontiers in Psychiatry, Journal of Medical Case Reports, BMJ Case Reports, Clinical Case Reports,
and Oxford Medical Case Reports. The last four are broad case venues so cross-specialty cases are
not restricted to specialty journals. Source rationale and article-level license rules are in
[D-22](DESIGN_DECISIONS.md). [BJPsych Open accepts case reports](https://www.cambridge.org/core/journals/bjpsych-open/information/author-instructions/preparing-your-materials),
[Frontiers in Psychiatry](https://www.frontiersin.org/journals/psychiatry/about) and
[Frontiers in Neurology](https://www.frontiersin.org/journals/neurology/about) list case reports
among their article types, and [BMC Psychiatry publishes case reports](https://link.springer.com/article/10.1186/s12888-026-08158-y).
This is a vetted **discovery frame**, not a claim that every article from these journals qualifies.
Some Frontiers sections exclude case reports; article type must be verified at the article level.

The script searches two prespecified publication-date windows: 2024-01-01 through 2025-12-31 as
development **candidates**, and 2026-07-01 through 2026-10-16 as temporal-test **candidates**.
These are search windows, not final split assignments. First public version dates, preprints and
model-specific cutoffs still need checking under D-22. A 2026 article may be ineligible as a clean
post-cutoff test if it appeared earlier or the solver cutoff is unknown.

Five routes run in each window. A stable hash sample of the whole journal frame gives an objective
reference slice. Stable hash samples of psychiatry and neurology specialty journals improve yield
for the pure tracks. Two **uncapped** mixed routes search (a) psychiatric and neurological terms in
title/abstract and (b) bridge terms such as neuropsychiatric, functional neurological, anti-NMDA,
postictal psychosis and psychogenic nonepileptic. These routes are high-recall signals, not case
labels. Retain all query hits and selected IDs, translated PMC queries, retrieval time, source
metadata, preliminary license and JATS article-type decisions, and rejection counts. The official
[PMC search guide](https://pmc.ncbi.nlm.nih.gov/about/userguide/) describes fielded title/abstract
and journal searches. Live checks on 2026-10-16 showed PMC translating `case reports[Publication
Type]` to an all-fields search; systematic reviews appeared among the hits. Do not equate the
search result count with case-report yield.

The broad reference slice is the only route suitable for estimating the frequency of the three
tracks *among records retrieved by this journal/date/search frame*. It does not estimate prevalence
among all published case reports because the PMC query has both false positives and possible misses.
The specialty and mixed routes are enriched; report their
yield and solver scores separately. Do not collapse the enriched mixed score into a population
average. Keep journal, publication window, patient/report and target-family denominators. Search
selection and case adjudication must be independent of solver failures or disagreement.

## From candidates to benchmark pairs

1. Verify the actual publisher article type and patient-level narrative, article-level CC0/CC BY/
   CC BY-SA license, first public version date, corrections/retractions, journal identity,
   duplication and usable chronology. JATS metadata is a screen, not final proof. Exclude figures or
   other third-party material without compatible rights.
2. Run two independent source-aware specialty reviews from different provider families. Each must
   return `track`, two-domain evidence spans (when mixed), how the domains interact, first-known
   phase, possible one-domain-only cutoffs, and reasons for exclusion. A third independent audit
   resolves conflicts or marks unresolved. None sees solver outputs. Freeze this adjudication
   prompt on development cases before test construction; preserve every raw response and decision.
3. Feed accepted, split-assigned cases into the existing dual clinical/information chronology
   construction pipeline. For every proposed mixed item, require a psychiatric and neurological
   pre-cutoff fact with source offsets and a later documented target connected to both. Audit
   prospective information boundaries and alternate answers as in D-18/D-19. The target is what
   happened, not the best clinical action. Do not discard an item merely because the actual event
   was improbable; flag uncertainty and observation status.
4. Export separate input-only records and hidden labels, each with `benchmark_track`,
   `interaction_stratum` (mixed only), source/patient cluster, split, event family, cutoff and
   endpoint. Prevent a patient's cases or alternative reports from crossing tracks or splits.
   Release and score each track separately. Use the same solver protocol and deterministic scorer;
   compute uncertainty by case, and compare task-family mix before any cross-track difficulty claim.

The repo now has a versioned [specialty prompt](../src/clinical_orchestra/construction/prompts/specialty.txt),
strict JSON contract, quote-membership/flag checks and a
[two-family review runner](../scripts/review_specialty_cases.py). The runner accepts only prepared
development records with article-level license, article-type and first-public-date evidence, and
requires `--live` to make calls. It logs every raw response before validation and leaves model
disagreement unresolved. Its agreements remain **provisional**: quote membership and matching
votes do not prove that a clue was known at the claimed cutoff. A separate independent chronology
audit and integrated-item gate are needed before export. There have been no live specialty reviews,
verified case assignments, or constructed item exports for these tracks. The next pilot should
validate a small development batch before expanding the mixed search beyond this frozen frame.
