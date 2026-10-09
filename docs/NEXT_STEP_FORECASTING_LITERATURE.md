# Clinical event forecasting research

Reviewed 5 October 2026. This focused follow-up to the [harness review](HARNESS_LITERATURE_REVIEW_2026-10-04.md) covers eight additional works selected for next actions, longitudinal outcomes, observation timing, and probabilistic prediction. It informs the [next-step architecture](NEXT_STEP_ARCHITECTURE.md). This is a targeted search, not a systematic review; none of the experiments were reproduced.

The central distinction is between a patient's course, clinicians' actions, information becoming available, and the eventual report of those events. Our interpretation is that these need different prediction contracts even when they share an inference engine. Studies of EHR forecasting provide useful methods, but their larger, more regularly recorded datasets differ from selected published case reports.

## 1 Foresight

[Foresight, Lancet Digital Health 2024](https://doi.org/10.1016/S2589-7500(24)00025-6). [Author manuscript](https://discovery.ucl.ac.uk/id/eprint/10190262/1/1-s2.0-S2589750024000256-main.pdf). [Code](https://github.com/CogStack/Foresight).

Foresight models patient timelines and forecasts multiple kinds of biomedical concepts, including disorders, procedures, substances, and findings. Its pipeline structures EHR text before training a generative temporal model. This is a closer task reference than a pure diagnosis benchmark. **Design implication:** one temporal representation can support several target families, with separate evaluation by family. **Limit:** it is an EHR-trained model using extracted concepts; it is not evidence that a prompt-only harness can achieve the same results on case reports. Borrow the task decomposition without reinstating our rejected ontology-based answer matcher.

## 2 ETHOS and ARES

[Foundation Model of Electronic Medical Records for Adaptive Risk Estimation, 2025, v4](https://arxiv.org/html/2502.06124v4). [Code](https://github.com/ipolharvard/ethos-ares).

ETHOS generates future patient timeline tokens; ARES estimates risks for specified events. Simulations stop at defined events or time limits, and the evaluation includes probability calibration as well as discrimination. **Design implication:** every forecast needs an explicit target and stopping boundary. **Limit:** this approach requires EHR model training. Generated trajectories are samples from a model, not additional observations. We can study sampled futures as a later inference strategy, but must never feed them back as real patient facts or use them to manufacture labels.

## 3 DT-GPT

[Large language models forecast patient health trajectories enabling digital twins, npj Digital Medicine 2025](https://www.nature.com/articles/s41746-025-02004-3). [Code](https://github.com/MendenLab/DT-GPT).

DT-GPT forecasts longitudinal clinical variables across several disease and care settings, rather than restricting prediction to diagnostic labels. **Design implication:** clinical progression and measured test values are legitimate separate prediction targets. **Limit:** its numeric trajectory evaluation depends on longitudinal measurements. Our case reports may provide only a sparse observation at one follow-up. Begin with well-defined categorical outcomes; continuous trajectories require an additional contract for units, measurement times, missing observations, and scoring. A forecast of the next reported value is not a forecast of the complete underlying physiological curve.

## 4 AgentRx

[AgentRx, CHIL 2026](https://proceedings.mlr.press/v333/al-jorf26a.html). [Methods](https://arxiv.org/html/2605.10286v1). [Code](https://github.com/nyuad-cai/AgentRX).

AgentRx evaluates clinical outcome prediction, including in-hospital mortality and length of stay, using different data modalities and agent configurations. Its results favor single-agent configurations over naive multi-agent configurations overall, with calibration problems in some voting systems. **Design implication:** preserve full probability distributions when combining forecasts, and evaluate calibration separately from top-choice correctness. **Limit:** conclusions depend on the particular models, tasks, and aggregation rules. They do not prove that all multi-agent approaches fail or that averaging probabilities automatically yields calibration.

## 5 ClinicRealm

[ClinicRealm, npj Digital Medicine 2026](https://www.nature.com/articles/s41746-026-02539-z). [Publisher manuscript](https://www.nature.com/articles/s41746-026-02539-z_reference.pdf).

ClinicRealm compares generative LLMs, text encoders, and conventional prediction methods on clinical notes and structured EHR tasks. It reports different relative strengths depending on data format and the amount of training data. **Design implication:** choose baselines appropriate to the target and available development data. Do not infer that a model strong at diagnosis is necessarily strong at progression, utilization, or numeric trends. **Limit:** task-specific trained baselines have access to supervision that a zero-shot method does not; report that difference. The reviewed overview does not identify a universal winning model for our task.

## 6 CliniBench

[CliniBench, EACL 2026](https://aclanthology.org/2026.eacl-long.247/).

Despite its broad title, the benchmark specifically studies discharge diagnosis prediction from admission notes. Its overview reports advantages for encoder-based classifiers and improvements from retrieving similar patients for generative models. **Design implication:** label each evaluation by its actual input cutoff and endpoint, not just “clinical prediction.” **Limit:** this is still a diagnosis target, and its result should not be conflated with ClinicRealm's different tasks and models. Similar-case retrieval, if tested here, must use development cases and exclude the evaluated patient's article and related reports. This entry was assessed at abstract depth.

## 7 Informative observation

[Informative presence bias in analyses of electronic health records-derived data: a cautionary note, JAMIA 2022](https://doi.org/10.1093/jamia/ocac050). [Accessible indexed article](https://pmc.ncbi.nlm.nih.gov/articles/PMC9196698/).

This original study combines healthcare data and simulations to examine how the observation process affects analyses. It reports that adjusting for visit counts can reduce without eliminating bias. **Design implication, by analogy:** a test being ordered and a result being documented are informative events; neither can be treated as random observation of a complete patient state. Case-report authors introduce an additional reporting selection process. Missing mention must remain unknown. **Limit:** the study addresses EHR inference, not case-report benchmark construction, and does not quantify the bias in our proposed dataset. The publisher/PMC full-text tools were intermittently inaccessible; the indexed primary-source abstract and article passages supplied this limited summary.

## 8 Foresight-England

[Foresight-England, August 2026 preprint](https://arxiv.org/abs/2608.16273).

The paper describes national-scale timeline modeling with absolute and relative timing and a temporally held-out evaluation plan. Crucially, it states that quantitative results are unavailable because project data access was paused. **Design implication:** temporal evaluation design and explicit timing are useful methodological references. **Limit:** this is not performance evidence, despite the scale of the described dataset. Included at abstract depth to distinguish an architectural proposal from an evaluated result.

## Changes to our design

These are our design conclusions from the search, rather than claims directly tested by the papers:

1. Keep a shared case representation and five typed forecast families; diagnosis is one family.
2. Specify the event category, what information the model has, and the endpoint before producing answer options.
3. Separate event occurrence from event discovery. Preserve partial orders and simultaneous bundles.
4. Track follow-up availability. A report ending before an endpoint does not provide a negative label.
5. Preserve clinician plans as input evidence, but report already-announced actions separately from unannounced choices.
6. Evaluate probability quality and operational reliability, including failures, by task family and case cluster.
7. Keep hypothetical future trajectories separate from observations and from subsequent benchmark inputs.
8. Use EHR forecasting repositories as methodological references. Reuse our existing construction and provider infrastructure for the first case-report implementation.
