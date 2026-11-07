# Microsoft's released SDBench: implications for Clinical Orchestra

Checked 7 November 2026. This review uses the [Science paper's PubMed record](https://pubmed.ncbi.nlm.nih.gov/42912144/),
[Microsoft's October announcement](https://microsoft.ai/news/building-medical-superintelligence/),
the [SDBench site](https://microsoft.github.io/sdbench/),
[PhysioNet's MIMIC dataset description](https://physionet.org/content/mimic-iv-ext-sdbench/1.0.0/),
and a read-only inspection of [`microsoft/sdbench` at `304ce962`](https://github.com/microsoft/sdbench/tree/304ce9625a046cea97d64e3b1ba5d19217b5095c).
The 2025 [arXiv preprint](https://arxiv.org/abs/2506.22405) is an earlier version; do not use
its o3 results as if they were the October 2026 Science results. The publisher's full Science
text was not accessible in this review, so detailed implementation claims below come from the
released code and README, not from an assumed identical final manuscript.

## What was released

SDBench is an **interactive sequential-diagnosis** environment. An agent starts with a short
summary, asks questions or orders tests, and eventually commits a diagnosis. A gatekeeper with
the full case file answers requests; a model judge grades the committed diagnosis on a 1–5 scale,
with 4–5 counted correct. It estimates clinical workup cost. The source code is MIT licensed and
includes the gatekeeper, judge, baseline agent, costing, run/resume/reporting code and five
synthetic demonstration cases. In the pinned checkout, `sdbench/agents/` contains only
`baseline.py`; the full MAI-DxO physician-panel orchestrator is **not present**. The README lets
users provide a custom agent, but reproducing the released baseline does not reproduce MAI-DxO.
See the [repository README](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/README.md)
and [agent directory](https://github.com/microsoft/sdbench/tree/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/agents).

The clinically sourced data are separate from the MIT code. NEJM cases require licensing from
NEJM; MIMIC-IV-Ext-SDBench requires PhysioNet credentialing, training and a data-use agreement.
The five bundled synthetic cases are development fixtures only. The MIMIC release has 488 distinct
patients: 163 train, 254 validation and 71 clinician-reviewed test cases. Its developers used
LLMs in curation and then corrected 13 ground-truth diagnoses during clinician review of the
71-case test split. That is a concrete reminder that LLM extraction plus a source document does
not automatically produce an error-free clinical label. We have no human reviewers, so our
clinical-validity claim must remain narrower. [Dataset methods and access](https://physionet.org/content/mimic-iv-ext-sdbench/1.0.0/).

The [Science abstract](https://pubmed.ncbi.nlm.nih.gov/42912144/) reports MAI-DxO accuracy of
83.2% on NEJM cases and 80.3% on MIMIC-IV-ED cases, versus 36.1% and 46.8% for the studied
generalist physicians. These are controlled text-simulation results, not patient outcomes.
PhysioNet also reports that, on the 325 MIMIC validation-plus-test cases, a GPT-5 baseline
achieved 76.6% accuracy with approximately $4,240 estimated workup cost per case; the
unrestricted DxO achieved 80.3% at approximately $4,980. Thus the accuracy gain did **not**
reduce estimated workup cost in that configuration. The cost estimates are clinical tests and
visits, not API spend. [MIMIC usage notes](https://physionet.org/content/mimic-iv-ext-sdbench/1.0.0/).

## What the code teaches us

| SDBench mechanism | Evidence in pinned release | Clinical Orchestra decision |
| --- | --- | --- |
| Separate agent, gatekeeper and judge | [`harness/harness.py`](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/harness/harness.py) calls the three components separately; named `science` config pins gatekeeper/judge models and prompts. | Keep solver, evidence broker and deterministic scorer separate, as D-19–D-21 already require. Pin every actual rendered prompt and model/version in a run manifest. |
| An agent can request absent findings | The [NEJM gatekeeper prompt](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/prompts/gatekeeper_synthetic_tests/v6_fixed/prompt.yaml) explicitly tells it to fabricate plausible results for absent ordered tests and mark them synthetic. Both gatekeeper prompts receive the full case text; the [MIMIC prompt](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/prompts/gatekeeper_synthetic_tests/v13_mimic/prompt.yaml) also interpolates the final diagnosis. The NEJM prompt mentions the final diagnosis but does not interpolate that field. | Do **not** use this gatekeeper as the source of our factual next-event labels. An optional interactive track would be separate; it must identify observed, unavailable and simulated information, and score simulated continuations separately. |
| Model-mediated secrecy and provenance need tests | The [gatekeeper parser](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/gatekeeper.py) defaults a missing `<is_synthetic>` tag to `false` and returns `Results not available` for missing blocks. | Our host should enforce the input-only boundary before any model call and reject missing provenance. Use adversarial source-leak and missing-status controls rather than trusting an instruction-only gatekeeper. |
| Model-judged diagnosis | The [judge](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/sdbench/judge.py) applies a 1–5 rubric; the judge prompt can see case context and test logs. | Keep our typed, frozen-option next-event score deterministic. If diagnosis free text is analyzed later, report its model-judged metric separately from the headline score. |
| Reproducible run controls | The [README](https://github.com/microsoft/sdbench/blob/304ce9625a046cea97d64e3b1ba5d19217b5095c/README.md) documents named configs, own agents/datasets, repetitions, resuming, cost recomputation and per-case JSON logs. | Adopt the *engineering pattern* of frozen config, complete case/repetition identity and recovery. Preserve our stricter attempt log and assigned-item failure denominator from D-21; don't infer completeness from a final aggregate alone. |
| Cost is a distinct outcome | SDBench separates agent diagnosis from estimated clinical workup charges; grounded costing may still fall back to LLM estimates. | Our fixed next-event forecast does not order real tests, so clinical workup cost is not a valid primary score. Track actual API cost/latency now; add clinical test cost only if a separately defined interactive action task warrants it. |

The SDBench code can be a reference or a **separate comparator** for sequential diagnosis, subject
to data access and a matched protocol. It is not a base for our general next-step benchmark:
our targets include tests, results, diagnosis, progression and treatment response at a fixed
information cutoff, and their gold labels must quote the documented course. An interactive
gatekeeper can answer a test that the clinicians never ordered, which changes both the task and
the evidence. This distinction is strongest for the mixed psychiatry/neurology track, where a
plausible but invented finding could falsely settle the specialty crossover.

## Limited follow-up

When implementing the evaluation worker, inspect SDBench's config/resume/report layout for
small reusable ideas. Add negative controls for hidden-answer requests, missing `observed` versus
`simulated` status, non-existent tests, repeated tests and failure recovery. Compare any future
interactive policy with our direct and repeated-request baselines under the same access limits.
Do not add SDBench's judge or synthetic gatekeeper to the current fixed-prefix scorer. No code,
prompts, clinical cases or reported SDBench numbers were imported into the benchmark by this
review.
