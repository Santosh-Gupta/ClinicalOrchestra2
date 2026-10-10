# What can a case report support as a prediction target?

Working catalog, 10 October 2026. This is a search guide for benchmark construction, **not** a list of implemented tasks or a decision to add every category. The current five task families and eligibility rules in [D-19](DESIGN_DECISIONS.md) and the [architecture](NEXT_STEP_ARCHITECTURE.md) remain authoritative. A published case report describes a selected and incomplete record. We can forecast what was **documented** next under a stated cutoff; we cannot treat everything omitted from the report as absent from the patient's life or care.

## Existing lists worth using

The closest answer to “there may be a list somewhere” is the [CARE case-report checklist](https://static1.squarespace.com/static/5db7b349364ff063a6c58ab8/t/5db7bf175f869e5812fd4293/1572323098501/CARE-checklist-English-2013.pdf), linked by [EQUATOR](https://www.equator-network.org/reporting-guidelines/care/). CARE asks authors to report patient concerns and history, examination, a timeline, diagnostic tests and challenges, diagnoses considered, prognosis, interventions and changes, clinician- and patient-assessed outcomes, follow-up tests, adherence/tolerance, and adverse or unexpected events. Its [flow diagram](https://www.equator-network.org/wp-content/uploads/2013/09/CAREFlowDiagram-updated-2019.pdf) adds a useful visit-by-visit view. CARE is a **reporting checklist**, not a benchmark taxonomy or a guarantee that every item is present in every article.

The [SCARE 2023 surgical case-report guideline](https://doi.org/10.1097/js9.0000000000000373) expands operative details, perioperative management, follow-up setting and timing, adherence, complications and longer-term outcomes. [FHIR's guide to clinical resources](https://hl7.org/fhir/R4/resourceguide.html) distinguishes orders, administrations, procedures, observations, diagnostic reports, conditions and adverse events; its [workflow model](https://hl7.org/fhir/R4/workflow.html) distinguishes a request from the event that fulfills it. We use those distinctions as a checklist, **not** to revive the ontology-mapping approach rejected in D-08. [EHRSHOT's 15 prediction tasks](https://som-shahlab.github.io/ehrshot-website/docs/intro/benchmark/) illustrate four target classes—operational outcomes, forthcoming lab results, new diagnoses and imaging findings—but its dense EHR records make fixed windows and negative labels easier than sparse case reports do.

## Build a target from several dimensions

A flat list hides important differences. Each proposed question should specify these dimensions before an LLM writes options:

| Dimension | Possible values | Why it matters |
| --- | --- | --- |
| **What changes** | Patient's physical state; what clinicians learn; clinicians' assessment; care decision; delivered care; care setting; patient choice | A result may reveal a pre-existing condition. A diagnosis is a recorded judgment. An order is not its completion. |
| **What to predict** | Identity; categorical finding; direction; severity band; occurrence within a window; timing; set of simultaneous events; numeric value | Each needs a different answer contract and scorer. Start with identity/categorical state. Numeric, timing and set targets need further rules. |
| **What is already known** | Action announced; test pending; treatment started; assessment proposed; nothing planned | “Which test is next?” is different from “What will the already ordered test show?” Announced actions may be trivial but need their own stratum. |
| **When to stop** | Next documented event of a named kind; result of a named pending test; next reported follow-up; predeclared time window | A future-selected window can leak the event. The endpoint must be neutral and supported at the cutoff. |
| **How the answer is observed** | Explicit result/event; explicit nonoccurrence through a complete interval; incomplete follow-up; silence | Silence and incomplete follow-up cannot become a negative label. |

This makes many task templates possible without pretending every future event has an unambiguous order. The two chronologies already planned are essential: physical occurrence and time of clinical knowledge need separate fields.

## Candidate target inventory

Each line is a **subtype to look for**, not an independent headline metric. Brackets show its likely current family: **A** action, **R** result of a *known* test/procedure, **D** documented diagnosis or assessment, **P** clinical progression/outcome, **T** treatment-associated response. **I** marks a possible *information-discovery* family that the current five-family design does not cleanly cover. Some entries can move between families depending on the question's anchor and what was known; such cases need an explicit contract, not automatic relabeling.

### 1. Patient's evolving clinical picture

- [P] New symptom or sign; change in symptom pattern, location, frequency, intensity or duration.
- [P] Deterioration, stability, improvement, remission or spontaneous resolution.
- [P] Relapse, recurrence, flare, spread or a new complication.
- [P] Change in function: mobility, speech, cognition, breathing, eating, work or activities of daily living.
- [P] Vital-sign trajectory, physiological instability, organ failure or recovery, if the report gives enough observations.
- [P] New comorbidity, co-infection or pregnancy-related development documented during the episode.
- [P] Crisis, emergency presentation, disability, death or survival at a supported follow-up.

### 2. New information about the patient

- [I] Later-disclosed symptom onset, exposure, travel, occupational history, substance use or contact history.
- [I] Later-discovered prior diagnosis, surgery, medication, allergy, treatment failure or family history.
- [I] Newly elicited patient-reported symptoms or a physical-examination finding that *already existed* at the cutoff.
- [I] Information from an outside record, relative, collateral history or earlier specimen.
- [I] Reinterpretation of an earlier finding after new information, without inventing that the underlying condition began then.

These are forecasts of **discovery**, not forecasts of a new biological event. They are a real gap in the five current families. A history question can also be more vulnerable to author-selection bias because the “surprise” may be why the report was written. Keep this as a proposed sixth family until a development pilot establishes yield and reliable labels.

### 3. Diagnostic actions clinicians choose or complete

- [A] Next bedside examination, repeated examination, questionnaire, point-of-care test or monitoring step.
- [A] Next blood, urine, fluid, microbiology, pathology, immunology, genetic or molecular test ordered.
- [A] Next imaging modality, anatomical target, contrast study, ECG/EEG or other physiological investigation.
- [A] Next biopsy, endoscopy, lumbar puncture, catheterization or other diagnostic procedure.
- [A] Repeat, confirmatory or second-line investigation after an equivocal result.
- [A] Specialist consultation, multidisciplinary review, transfer for testing or referral.
- [A] Explicit decision to defer, cancel, decline or substitute a test **only when the decision is documented**.
- [A] Test order versus specimen collection versus completed procedure versus issued report: separate stages, not interchangeable labels.

### 4. Results of already known investigations

- [R] Positive, negative, indeterminate, normal or abnormal laboratory result; clinically meaningful severity band.
- [R] Trend on a repeated measurement, if the previous value and repeated test are known.
- [R] Imaging location, pattern, lesion count/size band, incidental finding or absence of an explicitly assessed finding.
- [R] Microbial culture, organism identification, susceptibility or resistance result.
- [R] Histology, cytology, immunostaining, molecular variant or genetic finding.
- [R] ECG/EEG/physiology, endoscopy, biopsy or intraoperative finding, when the procedure was known before the cutoff.
- [R] A test that fails technically or is inconclusive, if the report explicitly says so.
- [R] A follow-up study showing persistence, progression or resolution of an earlier finding.

“What will the CT show?” requires CT to be known at the cutoff. “Which test will they order and what will it show?” combines two uncertain steps and should not be silently treated as an ordinary result item. Result subtypes may themselves need separate reporting because laboratory, imaging and pathology interpretation differ.

### 5. Clinical reasoning and assessment

- [D] A newly documented working diagnosis, differential diagnosis or change in its ranking.
- [D] A diagnosis explicitly ruled out, strengthened, revised or withdrawn.
- [D] The documented final diagnosis, including competing or coexisting diagnoses if supported.
- [D] Disease stage, extent, severity grade, subtype or risk category as *assessed* by the team.
- [D] Clinician-attributed etiology, mechanism, prognosis or expected course, clearly distinguished from what later happened.
- [D] Reassessment after treatment failure, unexpected finding or consultation.

Assessments may be wrong or incomplete; the benchmark label is what the report says the team concluded, not a claim that the conclusion was biologically true. An author's discussion of possible mechanisms written after the case is not necessarily a contemporaneous assessment and may be ineligible.

### 6. Treatment and management decisions

- [A] Start, stop, switch, escalate, de-escalate or withhold a medication or other therapy, when documented.
- [A] Choice of drug class, combination, route, duration or intensity; exact dose only with a separate numeric contract.
- [A] Surgery, radiation, endovascular procedure, drainage, device placement/removal, transfusion or transplant.
- [A] Supportive management: oxygen, ventilation, fluids, nutrition, dialysis, pain control, rehabilitation or preventive care.
- [A] Observation/watchful waiting, active surveillance, palliative approach or goals-of-care change if explicitly described.
- [A] Inpatient admission, emergency intervention, outpatient management or specialist referral.
- [A] Explicitly considered but rejected treatment, including a reason, only when documented before or after the decision as appropriate.

The action target is **what clinicians chose or delivered in this report**, not which action would be best for another patient. A plan already visible in the prefix should be tagged as announced, rather than presented as an unannounced choice.

### 7. Delivery, adherence and procedural course

- [A] Whether an ordered intervention was actually administered or performed, when completion is documented.
- [A] A planned procedure changed, was converted, aborted, repeated or followed by a revision procedure.
- [A/I] Patient acceptance or refusal, adherence, self-care action or inability to follow a plan when explicitly recorded.
- [P/T] Treatment intolerance, adverse effect or procedural complication; note timing and avoid assuming causality.
- [A] Postoperative instructions, monitoring, rehabilitation or a change in management after an intervention.

These are especially visible in [SCARE](https://doi.org/10.1097/js9.0000000000000373) and CARE follow-up reporting. Order, administration and adherence belong to different actors and information states.

### 8. Response after a known intervention

- [T] Symptom relief, functional recovery, stable disease, nonresponse or deterioration at a reported follow-up.
- [T] Change in examination finding, vital sign, laboratory marker, imaging lesion or pathology after treatment.
- [T] Microbiological clearance, recurrence after therapy, or need for rescue treatment.
- [T] Improvement in patient-reported pain, quality of life or other stated measure.
- [T] Adverse or unexpected change temporally following treatment, with causal attribution kept separate.

The treatment must already be known to the solver, and the outcome needs an eligible endpoint. A report of improvement after a drug does **not** establish that the drug caused the improvement.

### 9. Course, complications and longer-term outcomes

- [P] New organ dysfunction, bleeding, infection, thromboembolism, metastasis or other complication.
- [P] Spontaneous resolution, persistent disease, recurrence, relapse or progression at next follow-up.
- [P] Survival, mortality, disability, return to baseline, return to work or other functional status.
- [P] Pregnancy, neonatal or reproductive outcome where applicable.
- [P] Patient-assessed health or quality of life when actually reported.
- [P] A specified adverse event within a *predeclared and completely observed* interval; explicit absence in the same interval can be a negative label.

“No complication” is not supported by a report that merely does not mention complications. A later follow-up time chosen because the outcome was dramatic is retrospective and belongs in a separate analysis.

### 10. Care trajectory and follow-up process

- [A] Referral, admission, transfer, ICU transfer, step-down, discharge or change in care setting.
- [A] Planned follow-up, surveillance test, repeat visit or rehabilitation program.
- [P] Length-of-stay band, readmission, reoperation or unplanned emergency return when the endpoint is defined.
- [I/A] Follow-up actually completed, delayed, missed or lost, if explicitly described.
- [A] Change in responsible service or multidisciplinary management.

These resemble [EHRSHOT's operational tasks](https://som-shahlab.github.io/ehrshot-website/docs/intro/benchmark/) but case reports are often too sparse for a reliable 30-day negative label or a precise length-of-stay target. “Next documented disposition” is a more realistic first template.

### 11. Obstacles, surprises and patient choices

- [A/I] Test or treatment unavailable, delayed, unaffordable, contraindicated or refused when the report explicitly records the obstacle and its timing.
- [A/I] Patient preference, consent to a *clinical* intervention, self-management choice or change of preference when documented.
- [R/P] Incidental finding, unexpected test result, unexpected disease course or unforeseen complication.
- [D] Diagnostic error recognized and corrected later, if the stages of belief are separately supported.

Do not convert publication consent, author commentary or a clinical option never mentioned in the report into an event label. An “unexpected” event may be hard to forecast; difficulty does not make a supported prospective question invalid, but the source must establish a fair cutoff and a precise answer.

## Which target forms are ready for which stage?

| Stage | Candidate forms | Main condition |
| --- | --- | --- |
| **Start with** | Next documented test/treatment/care action; categorical result of a known test; documented diagnostic assessment; next reported development; response after a known treatment; explicit adverse event or disposition | Existing five families can express these with source support, clean cutoffs and fixed options. Report announced actions and retrospective follow-up separately. |
| **Pilot as an extension** | Later-disclosed history or examination finding; patient choice/adherence; intraoperative course; severity/stage; simultaneous bundles; explicitly documented non-action | Requires a clear discovery/actor/state contract and enough eligible real examples. Do not automatically create a sixth family or multi-label scorer. |
| **Defer until new contracts** | Exact numeric values, time-to-event, dose, multi-event sequence, broad set of findings, fixed-window negatives, length of stay | Needs units, tolerances, observation windows, ordering and missingness rules. Sparse case reports may not support them. |
| **Outside this benchmark's current target** | Optimal test or treatment; causal treatment benefit for this individual; outcome of an intervention never performed; event inferred solely from silence; author “lesson” as a patient event | These need different evidence, counterfactual assumptions or a different task. |

## How the construction pipeline should use the catalog

For each case, enumerate **candidate events** from the physical and information chronologies, then attach actor, event kind, order/planned/performed/result status, available-at phase, source span and links to known tests/treatments. Search each catalog subtype for a supported *future* event. Do not require a case to fill every subtype; an empty category is a result about reporting yield. For each candidate, test a neutral question and endpoint, source support, whether the action/anchor was known at the cutoff, whether simultaneous events make “next” ambiguous, and whether a categorical answer set can be made exclusive. Preserve all rejected candidates with reasons.

The author's stated teaching point can help find dense passages but must remain hidden from the option writer and solver. The catalog can guide extraction prompts toward less obvious targets, especially care transitions, adverse events, follow-up results and information disclosures. It must not force a question from an unsupported line or turn the report's editorial structure into a clinical chronology.

Before changing the five-family schema, run a small **development-only coverage audit**: count source-supported candidates and accepted items by subtype, case and reason for rejection; inspect whether the proposed information-discovery family adds enough clean, nontrivial items. The existing 99 post-cutoff items remain test-only. A schema change with real evidence belongs in a new design decision and construction version.
