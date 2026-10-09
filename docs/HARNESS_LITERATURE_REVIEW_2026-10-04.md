# Literature review for the Clinical Orchestra harness

Search conducted 4 October 2026; review completed 5 October 2026. Status: design guidance and proposed experiments, not adopted architecture.

Follow-up: [eight additional works on event and outcome forecasting](NEXT_STEP_FORECASTING_LITERATURE.md) informed the [D-19 next-step architecture](NEXT_STEP_ARCHITECTURE.md). That later design keeps diagnosis as one of five target families. The review below remains the original 31-entry research record.

This review covers clinical and diagnostic agents, scientific research agents, context management, and evaluation infrastructure. It contains 31 research entries plus software references. The purpose is to decide what to build and test around Clinical Orchestra's models after the construction pilot establishes a usable benchmark.

**Recommendation:** start with a small forecasting loop that preserves the initial prediction, uses an explicit record of available evidence, and can call a few bounded tools. Measure retrieval, repeated sampling, critics, programmatic orchestration, and editable context separately. The literature supports trying these components; it does not establish that combining all of them produces the best clinical harness.

The review is a targeted narrative search, not a systematic review or meta-analysis. Searches covered medical agents, sequential diagnosis, medical retrieval, biomedical tool use, scientific agents, recursive inference, context editing, and agent evaluation, followed by primary papers and their repositories. Selected methods, ablations, and limitations received closer reading where they affect our design. Some secondary entries were assessed from abstracts and repository documentation; these are marked. Reported experiments were not reproduced. Selected repository documentation and implementation files were inspected; this is not a dependency or security audit. Older preprints are identified where that version supplied the methodological details.

## What transfers to this project

Clinical Orchestra forecasts **the next documented event given information available at a cutoff**. It does not currently evaluate which treatment is best, which test should be ordered, or whether an agent can improve a patient's outcome. This distinction is established in [D-18](DESIGN_DECISIONS.md) and the [construction guide](CONSTRUCTION_PIPELINE.md).

That makes some impressive diagnostic and scientific systems only partly comparable. An agent selecting tests changes what it observes. A scientist running an experiment receives a new measurement. Our solver receives a fixed case prefix and predicts a withheld continuation. Adding a patient simulator that invents answers would change the task and reintroduce the label problem from version one.

Published evidence also comes with different forms of support:

| Evidence source | What it can establish | Limit for our project |
| --- | --- | --- |
| Frozen answer IDs and executable grading | Reproducible scoring against a specified reference | The reference or task specification can still be wrong |
| Source quotations and temporal checks | Evidence that a report contains a claim and that the input respects its cutoff | A quote alone does not establish semantic support or predictability |
| Independent tool output | A calculation, database lookup, or execution result | Correct execution does not establish correct inputs or clinical applicability |
| Repeated model agreement | A possible signal for allocating effort or abstaining | Correlated mistakes can be stable |
| Expert adjudication | A separate assessment of clinical or scientific validity | We do not have this resource |
| Laboratory experiments | Observed feedback on a proposed intervention | We cannot manufacture an equivalent with an LLM judge |

These distinctions are our interpretation of the studies below, not a claim that all papers use the same evaluation protocol.

## Findings that should guide the first design

### Make every extra component removable

Clinical papers contain useful negative results. The September 2026 on-premise study's diagnostic critic did not improve overall accuracy. The AMIE management paper also found that the value of its history-taking scaffold changed with the underlying model. These motivate measuring each component again when the model changes, rather than preserving an elaborate workflow because it helped an older model. See clinical entries 2 and 4.

### Prefer feedback with an identifiable source

The transferable pattern across EHRAgent, AgentMD, Biomni, PaperQA2, and scientific experiment systems is an action followed by a result that can be inspected: a query result, calculation, source passage, execution error, or physical measurement. Our inference is that the first tools should serve explicit information needs. A second agent's opinion remains a model output, even when assigned a specialist role.

### Preserve missing information

An unavailable patient value must remain unavailable. General medical literature can inform a probability; it cannot establish that this patient had a particular result. AgentMD's documented missing-input failures make this more than a theoretical concern. Our proposed tools should reject unsupported calculator inputs and return a structured missing-input result instead of silently substituting values. See clinical entry 9.

### Compare against a strong sampling baseline

Medprompt and the MedAgents comparison with self-consistency make a single short answer an inadequate sole control for a multi-call harness. A useful comparison includes independent predictions with a frozen aggregation rule at several comparable spending levels. Report both inference expenditure and latency. More successful answers after more calls do not by themselves establish better orchestration. See clinical entries 7 and 15 and general entry 4.

### Treat judges as measurements with error

ChemCrow reported disagreement between its LLM evaluator and expert evaluators. The co-scientist paper explicitly distinguishes its internal ranking from independent truth. Deterministic scoring avoids that particular judging variability, but the SciCode-Verified audit shows why deterministic graders and task specifications need their own validation. We should keep model-assisted construction audits distinct from mechanically computed solver scores. See science entries 5, 6, and 10.

### Keep the observation process explicit

Diagnosis, treatment choice, and forecasting a published narrative are different tasks. A published case is selected and written after the fact. Even perfect reconstruction of the information cutoff does not make its next event uniquely predictable. Our probability outputs should express that ambiguity; harness complexity cannot remove it. Task-type results and error analysis should distinguish missing information, narrative uncertainty, unsupported assumptions, retrieval failure, and execution failure.

## Clinical and diagnostic research

### 1 AMIE diagnostic dialogue

[Towards conversational diagnostic artificial intelligence, Nature 2025](https://www.nature.com/articles/s41586-025-08866-7).

AMIE combines self-play training with an inference procedure that summarizes clinical information, identifies missing information, and develops a response. Its evaluation uses simulated consultations with patient actors and specialist assessments. **Useful pattern:** maintain a concise state containing relevant findings, uncertainty, and unresolved questions. **Limit:** its result is not an estimate of what a prompt-only wrapper adds to an unchanged model, and simulated consultations are not patient outcomes. The expert evaluation component is unavailable to us.

### 2 AMIE disease management

[Towards conversational artificial intelligence for disease management, Nature 2026](https://www.nature.com/articles/s41586-026-10764-5).

This system separates conversational work from management reasoning and uses guideline retrieval. A particularly relevant ablation reports substantial history-taking gains from scaffolding for the older Gemini 1.5 Flash-based AMIE, but little or no improvement when supplied to Gemini 2.5 Flash in auto-evaluated simulations. **Useful pattern:** separate fast interaction from slower evidence work when the task requires both. **Limit:** the ablation is model- and evaluation-specific; it does not establish that every management component becomes unnecessary. For our fixed-prefix task, retain only components that improve our own comparisons.

### 3 MAI-DxO sequential diagnosis

[Sequential Diagnosis with Language Models, 2025 preprint, v1 methods](https://arxiv.org/html/2506.22405v1).

MAI-DxO uses roles for hypotheses, tests, challenges, resource stewardship, and checks. The roles are simulated by one model; they are not independent clinical experts. Its environment lets the solver request information, and its gatekeeper can generate plausible findings absent from the source case. Reported cost includes estimated medical tests and visits, which must not be confused with API expenditure. **Useful pattern:** explicit competing hypotheses and bounded decision cycles. **Limit:** borrowing the gatekeeper would change our observed-event benchmark into a partly synthetic environment. Its free-text diagnostic judging also differs from our intended answer-ID scoring.

### 4 On-premise medical agents

[On-premise medical AI agents for reliable clinical decision-making, Nature Medicine, September 2026](https://www.nature.com/articles/s41591-026-04609-x). [Code](https://github.com/KatherLab/onprem-medical-agents).

The study compares confidence signals in retrospective diagnostic simulations. Agreement across repeated runs was the most informative evaluated correctness signal. Its critic ablation reported 87.1% accuracy with a critic versus 88.4% without; this is a descriptive comparison, not a claim of statistically established harm. High retained-set accuracy came with reduced coverage. **Useful pattern:** investigate disagreement as an effort-allocation signal and report risk against coverage. **Limit:** agreement is not proof, threshold values are configuration-dependent, and the study includes physician adjudication. We cannot replace unavailable human escalation by quietly excluding difficult benchmark items.

### 5 Direct comparison of clinical agent systems

[Benchmarking large language model-based agent systems for clinical decision tasks, npj Digital Medicine, February 2026](https://www.nature.com/articles/s41746-026-02443-6).

The authors evaluate Manus and medical adaptations of OpenManus on simulated diagnosis and difficult question answering. They report modest accuracy gains alongside substantially increased resource use, including more than tenfold token use and more than doubled latency in the reported comparisons. Fabricated patient statements and measurements remain an issue. **Useful pattern:** audit tool traces and quantify the cost of each architecture. **Limit:** this tests particular systems and models on structured benchmarks; it does not show that all agents are inefficient or that the same ratios apply to our models.

### 6 DeepRare

[DeepRare, Nature 2026](https://www.nature.com/articles/s41586-025-10097-9). [Code](https://github.com/MAGIC-AI4Med/DeepRare).

DeepRare combines a coordinating agent with specialized tools and evidence traces for rare-disease diagnosis, including phenotype and genetic information. Evaluations span multiple datasets and include expert assessment of reasoning traces. **Useful pattern:** route a concrete subproblem to a relevant database or tool and retain evidence supporting the result. **Limit:** rare-disease and genomics workflows differ from general next-event prediction; expert-reviewed traces are stronger validation than we can currently supply. Its use of structured phenotype inputs does not justify reinstating the rejected ontology-based benchmark answer matcher.

### 7 MedAgents

[MedAgents, Findings of ACL 2024; preprint methods](https://arxiv.org/html/2311.10537v1). [Code](https://github.com/gersteinlab/MedAgents).

MedAgents recruits specialist roles, obtains analyses, summarizes them, and discusses a final answer. It is a useful prompt-level example of medical collaboration without model training. The paper's conclusion describes results comparable to strong few-shot self-consistency as well as improvements over simpler prompting. **Useful pattern:** solicit independent proposals before exposing agents to one another's answers. **Limit:** medical multiple-choice results do not establish that a committee improves prospective forecasting. Role diversity is not equivalent to independent evidence or independent model errors.

### 8 MDAgents

[MDAgents, NeurIPS 2024](https://papers.nips.cc/paper_files/paper/2024/file/90d1fc07f46e31387978b88e7e057a31-Paper-Conference.pdf). [Preprint v1 methods inspected](https://arxiv.org/html/2404.15155v1). [Code](https://github.com/mitmedialab/MDAgents).

MDAgents varies the collaboration structure according to an estimated task difficulty, from individual reasoning to larger teams. **Useful pattern:** spend additional effort selectively and put limits on discussion. **Limit:** an LLM's difficulty estimate is itself fallible, and comparisons must include a fixed strategy with comparable total spending. The earlier preprint and final publication have different evaluation coverage; this review does not mix their numerical results. For us, adaptive routing is a later experiment after fixed-budget baselines are stable.

### 9 AgentMD and RiskCalcs

[AgentMD, Nature Communications 2025](https://www.nature.com/articles/s41467-025-64430-x). [Code and calculators](https://github.com/ncbi-nlp/Clinical-Tool-Learning).

AgentMD selects and executes clinical calculators, with separate evaluations of tool construction and use. Its real-note analysis reports errors from assumptions about missing values, including poor results for two particular calculators. Generated calculators also were not uniformly correct; human checks and boundary cases exposed errors. **Useful pattern:** a small library of tested calculations with explicit eligibility, units, and required inputs. **Limit:** successful execution is not clinical validity. Do not import an automatically generated calculator collection as a trusted oracle, and do not fill missing patient fields to make a calculation run.

### 10 EHRAgent

[EHRAgent, EMNLP 2024; preprint methods](https://arxiv.org/html/2401.07128v1). [Code](https://github.com/wshi83/EhrAgent).

EHRAgent uses code to plan and execute queries across EHR tables, then revises code using execution feedback. It also uses demonstrations and memory of successful cases. **Useful pattern:** programmatic access to structured evidence, with errors returned to the solver. **Limit:** retrieving a value correctly is different from predicting a future event. Any case memory in our evaluation must be restricted to development data; the solver's record access must enforce patient identity and knowledge cutoff in code, rather than relying on its prompt to ignore future rows.

### 11 MedAgentBench

[MedAgentBench, 2025; v1 methods](https://arxiv.org/html/2501.14654v1). [Code](https://github.com/stanfordmlgroup/MedAgentBench).

MedAgentBench provides patient-specific tasks and a FHIR environment, with explicit tool schemas and rule-based grading. The inspected v1 executes reads but checks proposed write payloads rather than applying every write to a fresh environment. **Useful pattern:** validate actions and distinguish tool success from task success. **Limit:** it is an EHR task benchmark, not a forecasting engine, and the v1 design should not be described as universal verification of resulting database state. Its graders and tasks were manually curated.

### 12 AgentClinic

[AgentClinic, npj Digital Medicine 2026](https://www.nature.com/articles/s41746-026-02674-7). [Code](https://github.com/SamuelSchmidgall/AgentClinic).

AgentClinic models doctor, patient, measurement, and moderator interactions. In the published description, the patient agent receives symptoms and history without the final diagnosis, while other roles have their own information. Performance depends partly on interaction length and the patient model. **Useful pattern:** explicit information boundaries and evaluation of partial observations. **Limit:** changing the simulator changes the test. For Clinical Orchestra, replay grounded observations if an interactive track is later added; unreported test results must remain unavailable rather than becoming plausible synthetic measurements.

### 13 MedRAG and MIRAGE

[Benchmarking Retrieval-Augmented Generation for Medicine, Findings of ACL 2024](https://aclanthology.org/2024.findings-acl.372/). [Paper](https://arxiv.org/abs/2402.13178). [Code](https://github.com/gzxiong/MedRAG).

The study systematically varies retrieval corpora, retrievers, and models across medical QA tasks. **Useful pattern:** treat those choices as separate experimental factors, and retain retrieved documents so the same evidence can be replayed. **Limit:** published medical QA gains do not establish a gain on rare case continuations. We should compare no retrieval, fixed retrieval, and bounded adaptive retrieval while controlling corpus and information access. This entry was assessed from the paper overview and toolkit documentation, rather than a replication of its parameter sweep.

### 14 Iterative medical retrieval

[Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions, PSB 2025](https://arxiv.org/abs/2408.00727). [Implementation in MedRAG](https://github.com/gzxiong/MedRAG).

i-MedRAG asks further search questions based on earlier retrieval results. The paper reports medical vignette and knowledge-test improvements and studies iteration and query counts. **Useful pattern:** search for the unresolved question exposed by the previous evidence, with an explicit stopping limit. **Limit:** extra searches need an equal-budget comparison with simpler retrieval. Medical references do not supply missing facts about an individual patient. This entry was assessed at abstract and implementation-overview depth.

### 15 Medprompt

[Can Generalist Foundation Models Outcompete Special-Purpose Tuning, 2023](https://arxiv.org/html/2311.16452v1).

Medprompt combines dynamic examples, model-generated reasoning demonstrations, and ensembles that shuffle answer choices. It includes an evaluation set withheld from prompt development. **Useful pattern:** establish a strong multi-sample control and test sensitivity to option order. **Limit:** demonstrations must come only from our development split, and generated rationales are not verified clinical explanations. When shuffling choices, maintain a deterministic mapping back to frozen option IDs. We should not attribute a gain from additional samples or examples to a more elaborate agent architecture.

## Scientific agent research

### 1 Biomni

[Biomni A1 and E1, 2025 report](https://biomni.stanford.edu/paper.pdf). [Code](https://github.com/snap-stanford/Biomni).

Biomni pairs an agent with a broad biomedical environment of tools, databases, and software. It retrieves relevant tools and composes actions through code. The environment includes expert work on tool validation. **Useful pattern:** choose a small relevant tool subset and use programmatic control when a task requires several operations. **Limit:** the curated environment contributes to performance; installing an agent loop does not reproduce it. This entry refers to A1/E1, not later trained variants. For our task, borrowing the tool interface is more appropriate than importing the entire environment.

### 2 PaperQA2

[Language agents achieve superhuman synthesis of scientific knowledge, 2024 report](https://arxiv.org/html/2409.13740v1). [Code](https://github.com/Future-House/paper-qa).

PaperQA2 exposes literature search, evidence gathering, citation traversal, and answer generation as tools. Its fixed-sequence ablation performed worse on LitQA2, supporting adaptive search in that setting. However, its evidence reranking and summarization helped some models and hurt smaller ones. **Useful pattern:** bound an evidence-search loop and preserve source passages behind compressed evidence. **Limit:** evidence summaries remain model outputs, and the paper's literature evaluations do not establish clinical forecast accuracy. We should test raw passages against summaries rather than assuming compression is harmless.

### 3 Aviary and language decision processes

[Aviary report, 2024](https://arxiv.org/html/2412.21154v1). [Environment library](https://github.com/Future-House/aviary). [Agent and optimization library](https://github.com/Future-House/ldp).

Aviary separates agents from tool environments and includes scientific tasks with measurable outcomes. The associated work also studies learning and inference-time sampling. **Useful pattern:** a stable environment interface so policies can be swapped without changing available evidence or scoring. **Limit:** gains involving training or additional sampling are not gains from the environment abstraction alone. It is a plausible foundation for a later interactive benchmark, while a fixed-prefix forecast currently needs less infrastructure.

### 4 Robin

[A multi-agent system for automating scientific discovery, Nature 2026](https://www.nature.com/articles/s41586-026-10652-y). [Code and trajectories](https://github.com/Future-House/robin).

Robin connects literature work and proposed experiments with experimental results and subsequent analysis. The workflow includes human laboratory and data-processing contributions. **Useful pattern:** retain the observation that caused a hypothesis to change and distinguish proposed work from completed work. **Limit:** measured biological feedback is a major source of information. A conversation among models cannot provide an equivalent feedback channel for unobserved clinical events. We can borrow trace structure and bounded revision, not the evidential strength of laboratory validation.

### 5 Google AI co-scientist

[Towards an AI co-scientist, 2025 report](https://arxiv.org/html/2502.18864v1).

The system generates, critiques, ranks, and evolves hypotheses using multiple agents. Its internal Elo ranking is supported by some external checks, but the paper explicitly notes that the ranking is not independent ground truth. Biomedical validations involve expert guidance and experiment selection. **Useful pattern:** keep multiple proposals and compare them using explicit criteria. **Limit:** rising internal scores do not by themselves demonstrate improvement. We should not use a solver committee's preferred clinical prediction as a benchmark label or use its internal ranking as the final metric.

### 6 ChemCrow

[Augmenting large language models with chemistry tools, Nature Machine Intelligence 2024](https://www.nature.com/articles/s42256-024-00832-8). [Accessible preprint methods](https://arxiv.org/html/2304.05376v3). [Code](https://github.com/ur-whitelab/chemcrow-public).

ChemCrow combines an LLM with specialized tools and execution feedback. In its evaluation, expert chemists favored the tool-using system, while the LLM evaluator favored the baseline on average, influenced by fluent and apparently complete responses. **Useful pattern:** assess evidence and outcomes separately from prose quality. **Limit:** the demonstrations use chemistry tools and expert evaluation; they do not justify a universal agent advantage. This is a particularly direct precedent for our concern that a model judge can reverse the apparent conclusion.

### 7 Coscientist

[Autonomous chemical research with large language models, Nature 2023](https://www.nature.com/articles/s41586-023-06792-0). [Code](https://github.com/gomesgroup/coscientist).

Coscientist combines documentation search, code execution, and laboratory automation to plan and perform experiments. **Useful pattern:** consult the actual tool documentation, execute a plan, and inspect the response before continuing. **Limit:** capabilities demonstrated with real experimental feedback cannot be assumed for clinical counterfactuals with no observations. This entry emphasizes the paper's system overview rather than a detailed audit of every experiment. Coscientist and Google's later co-scientist are separate systems.

### 8 LABBench2

[LABBench2, 2026 preprint, v2](https://arxiv.org/html/2604.09554v2). [Code](https://github.com/EdisonScientific/labbench2).

LABBench2 separates scientific abilities such as literature localization, database access, exact sequence handling, troubleshooting, and experiment planning. It compares models with and without tools and discusses limitations of exact-input handling and rubric-based evaluation. **Useful pattern:** test individual operations in addition to the final answer. **Limit:** biology research tasks do not validate medical forecasting, and not all task families have equally objective grading. For us, auxiliary tests should isolate source retrieval, temporal filtering, calculations, output parsing, and evidence preservation.

### 9 SciCode

[SciCode, 2024](https://arxiv.org/abs/2407.13168). [Code](https://github.com/scicode-bench/SciCode).

SciCode breaks scientific coding problems into subproblems and evaluates executable solutions against tests, with optional scientific background. **Useful pattern:** localize failures rather than reporting only a whole-workflow score. **Limit:** test passage depends on the correctness of the specification, reference implementation, and numerical tolerances. The next entry is an important companion. This entry was assessed from the paper overview and benchmark description, not from executing its suite.

### 10 SciCode-Verified

[SciCode-Verified, August 2026 preprint](https://arxiv.org/html/2608.04975v1). [Code and audit trail](https://github.com/flyingwagner/scicode-verified).

This audit reports defects in SciCode specifications, reference answers, and grading, with substantial score changes after repairs. Corrections were checked by domain experts. **Useful pattern:** version specifications and graders, retain the reason for every repair, and distinguish rescoring fixed outputs from rerunning a changed question. **Limit:** these are the audit authors' reported results, not an independent replication here. Its expert review cannot be replaced by a claim that our LLM audits establish equivalent validity. Determinism and correctness are separate properties.

## General harness methods and failure analysis

### 1 CodeAct

[Executable Code Actions Elicit Better LLM Agents, ICML 2024](https://arxiv.org/html/2402.01030v1). [Code](https://github.com/xingyaoww/code-act).

CodeAct represents actions as executable Python, allowing composition, loops, reuse of libraries, and revision after execution feedback. The work includes both action-interface comparisons and trained agent models. **Useful pattern:** a programmatic interface can express several related operations more naturally than many separate tool messages. **Limit:** distinguish benefits of the interface from benefits of training. Clinical Orchestra should test code orchestration over the same tools available to a simpler baseline, with the same information and budget.

### 2 Recursive Language Models

[Recursive Language Models, 2025 preprint](https://arxiv.org/html/2512.24601v1). [Code](https://github.com/alexzhang13/rlm). [Original explanatory blog](https://alexzhang13.github.io/blog/2025/rlm/).

RLMs place input in an external environment that the model can inspect programmatically and query through subsidiary model calls. The original experiments use a limited recursion depth and concern long-context tasks, not clinical forecasting. **Useful pattern:** keep large evidence collections outside the active prompt and process selected portions. **Limit:** this is not direct evidence that recursive calls improve short clinical cases. All subcalls, retries, and tool use need a shared host-enforced budget; the execution environment must not expose withheld outcomes or provider credentials.

### 3 Context Language Models

[Context Language Models, September 2026 preprint](https://arxiv.org/html/2609.37725v1). [Code](https://github.com/facebookresearch/context-language-models).

CLMs let a model edit its active context; the work also explores learning to use that ability and serving-side efficiency. This differs from reading an external document through an RLM. **Useful pattern:** retain compact working notes and inspect their revisions. **Limit:** inference FLOP savings or specialized cache behavior do not automatically translate into lower hosted-API bills. Our initial experiment should restrict edits to working notes, preserve original evidence, and log full snapshots. Full context editing remains a separate experiment. The repository's root license is CC BY-NC 4.0; paper access and code reuse have separate terms.

### 4 AI Agents That Matter

[AI Agents That Matter, 2024](https://arxiv.org/html/2407.01502v1).

This study argues for evaluating accuracy and inference cost together, demonstrates the strength of repeated-sampling baselines, and identifies problems with overfitting and reproducibility in agent evaluation. **Useful pattern:** compare strategies over spending levels and retain complete run accounting. **Limit:** its empirical examples are not clinical. Our transfer is methodological: include development expenditure, failed attempts, retries, and latency where measurable, and never represent missing provider usage as zero.

### 5 Multi-agent failure taxonomy

[Why Do Multi-Agent LLM Systems Fail, 2025](https://arxiv.org/abs/2503.13657). [Repository](https://github.com/multi-agent-systems-failure-taxonomy/MAST).

The paper groups failures around system specification, coordination, and verification or termination. **Useful pattern:** log why a run failed, including lost information, contradictory work, invalid assumptions, and stopping errors. **Limit:** an automatic failure annotator is another model-assisted measurement, not the outcome scorer. Earlier versions use different taxonomy naming and sample counts; this review uses the broad categories without combining version-specific statistics.

### 6 Intrinsic self-correction

[Large Language Models Cannot Self-Correct Reasoning Yet, ICLR 2024](https://arxiv.org/html/2310.01798v1).

The experiments distinguish revision based only on a model's own response from correction supported by external feedback. They find limited or negative effects for intrinsic correction in the evaluated settings and recommend comparable sampling baselines. **Useful pattern:** require a stated reason and evidence for revisiting an answer; test revision rather than assuming it helps. **Limit:** the title is not a timeless impossibility result for future models, other tasks, or tool-supported correction.

## Repositories to use as references or foundations

These are recommendations for our workload. A paper's score is not evidence that its repository is maintained, secure, or compatible with our current dependencies. Before importing code, pin a version and inspect the relevant dependency and license files.

| Repository | Proposed use | Why not adopt the entire system immediately |
| --- | --- | --- |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | First candidate for outer evaluation: model runs, solvers, scorers, limits, logs | It needs a Clinical Orchestra adapter and explicit separation of solver inputs from hidden targets |
| [Aviary](https://github.com/Future-House/aviary) and [LDP](https://github.com/Future-House/ldp) | Alternative if interactive environments or learned policies become central | The current fixed-prefix task does not need a scientific environment framework |
| [MedRAG](https://github.com/gzxiong/MedRAG) | Compare retrieval configurations using a fixed medical corpus | Corpus size and a good retriever do not establish relevance to the prediction |
| [PaperQA](https://github.com/Future-House/paper-qa) | Source tracking and bounded adaptive literature search | Its full literature-answering workflow is broader than one clinical evidence query |
| [Biomni](https://github.com/snap-stanford/Biomni) | Programmatic tool interface and selection of relevant tools | Its large environment and validated resources are substantial separate assets |
| [EHRAgent](https://github.com/wshi83/EhrAgent) | Structured record queries and execution-error feedback | Its task and memory assumptions need modification for independent cutoffs |
| [MedAgentBench](https://github.com/stanfordmlgroup/MedAgentBench) | Tool schemas, action validation, and explicit failure states | It is a different benchmark, not our scoring foundation |
| [DeepRare](https://github.com/MAGIC-AI4Med/DeepRare) and [AgentMD](https://github.com/ncbi-nlp/Clinical-Tool-Learning) | Examples of useful specialized clinical tools | Their domains and validation procedures do not cover our whole task |
| [RLM](https://github.com/alexzhang13/rlm) | Optional programmatic inference strategy | Benchmark data isolation and shared budgets need enforcement outside model code |
| [Context Language Models](https://github.com/facebookresearch/context-language-models) | Context-editing experiment after a simpler notes baseline | Active-context mutation changes both evidence exposure and cache behavior |
| [Anabasis](https://github.com/s-smits/anabasis) | Experiment freezing, provenance, negative controls, and accounting patterns | Its autonomous build-and-revise workflow, TypeScript/Bun stack, and correctness machinery exceed the initial Python forecasting loop |

Two details matter if Inspect becomes the outer runner. Its [TaskState](https://inspect.aisi.org.uk/solvers.html) includes the target, so using the framework alone is not a security boundary between solver and answer. Pass an input-only object into an isolated solver worker. Its [logging documentation](https://inspect.aisi.org.uk/eval-logs.html) also distinguishes ordinary logs from comprehensive raw API logging. Preserve our existing requirement to retain every raw response, including failed calls. These are integration requirements, not reasons to discard the framework.

Anabasis's [experiment freeze implementation](https://github.com/s-smits/anabasis/blob/main/src/run/experiment-freeze.ts) is a useful reference for freezing tasks, scoring, and harness code separately. Its [execution isolation configuration](https://github.com/s-smits/anabasis/blob/main/src/verify/solve-command-isolation.ts) should not be assumed to prohibit network access. Code-level observations are references for a future audit, not a completed sandbox certification.

The public [Claude Science compliance documentation](https://platform.claude.com/docs/en/manage-claude/compliance-sessions) describes connector calls through a REPL host bridge. This supports the architectural idea in the quoted discussion: data and tool orchestration can live in a programmatic workspace. It does not establish direct descent from the RLM or CLM papers, nor a clinical performance benefit.

## Proposed initial design

The following is a proposed implementation direction. It does not amend D-18 or mark the evaluation runner as built.

Use an outer controller that owns the frozen task, budget, provider adapters, ledger, and scorer. The solver receives only a compiled prefix and its frozen answer options. Hidden outcomes, full articles, construction responses, and source-aware audit records remain outside its environment.

Give the solver four distinct stores:

| Store | Contents | Edit rule |
| --- | --- | --- |
| Available case evidence | Facts and source identifiers allowed by the knowledge cutoff | Read only |
| External evidence | Retrieved passages, source dates, query, and retrieval metadata | Append only; corrections get new records |
| Working notes | Hypotheses, unresolved questions, tentative interpretations | Editable, with snapshots |
| Run history | Predictions, requests, outputs, failures, expenditure, and revisions | Append only |

The physical chronology helps the constructor reconstruct the case. It must not leak physical events into a solver input before those events became known to the care team. Unknown, not mentioned, negative, and normal need distinct representations.

The first inference pass should return probabilities over the frozen options, unresolved uncertainties, and any requested tool action. Keep that prediction immutable. A tool may add evidence or flag a problem; it cannot overwrite the baseline. A later model prediction is a separate recorded candidate. A frozen selection rule determines the reported output. This preserves the current rule in [AGENTS.md](../AGENTS.md) and allows measurement of both corrected errors and newly introduced errors.

Initially expose only tools with a clear purpose: read permitted evidence, perform validated arithmetic, retrieve an approved medical passage, record notes, and finish. If a REPL is tested, expose the same capabilities through a narrow host bridge in an isolated worker. Check cumulative budget before every model or tool call, including nested calls. Bound tool output sizes, recursion, and total runtime outside model control.

Start each benchmark cutoff with fresh solver state. Schedule items case by case to benefit from shared prompt prefixes, but do not carry generated notes or earlier hidden outcomes into the next item. A genuinely longitudinal agent with memory would be a separately specified evaluation track.

External retrieval needs special handling. Exclude the originating article and identifiable reproductions using source identifiers and matching content where possible, and retain exclusion logs. A snapshot of general medical references makes comparisons more reproducible than unrestricted changing web results. If the claim concerns historical clinical practice, enforce source-date eligibility; otherwise clearly describe the task as present-day forecasting of a historical narrative. These controls reduce leakage risk but cannot prove absence of memorization.

## Proposed experiment sequence

Run these on development cases only while choosing prompts and configuration. Keep the existing post-cutoff items untouched for testing. Do not select a replacement reference set because current models find particular cases difficult.

| Stage | Comparison | Question answered |
| --- | --- | --- |
| 1 | Direct prediction at several allowed budgets; independent samples with frozen aggregation | How much is gained by additional inference alone? |
| 2 | Direct prediction versus a fixed structured-evidence-and-notes workflow | Does explicit organization help without external evidence? |
| 3 | No retrieval versus fixed retrieval versus bounded adaptive retrieval | Does retrieval help, and does adaptive query selection add value? |
| 4 | Fixed tool sequence versus model-directed tool choice over identical tools | Is planning useful for this task? |
| 5 | Ordinary tool loop versus programmatic or RLM-style orchestration | Does executable control improve accuracy, expenditure, or latency? |
| 6 | Existing best development configuration with and without an independent critic | Does critique fix more answers than it damages? |
| 7 | Immutable history versus editable notes, then optional broader context editing | What information is lost or preserved when context changes? |

This is an ordered shortlist, not a requirement to run every combination. Promote a component only after a repeatable development benefit justifies its complexity. Recheck useful components across more than one provider family before freezing the final comparison. Use the requested construction models only when the corresponding endpoints and accounts are verified; this review does not rank those untested models or resolve the GLM naming ambiguity.

Respect the current temperature-zero rule where supported, and record provider exceptions. Repeated requests can still vary, but the stochastic sampling procedures used in some papers are not automatically equivalent to our runs. If we test higher-temperature sampling, record it as a separate proposed protocol change. Likewise, keep repeated identical prompts distinct from ensembles using predefined prompt or option-order variants.

For each comparison, retain a common spending cap and also report actual spending. Equal call counts alone are inadequate because calls differ in context length, output length, hidden reasoning, and price. Include every subsidiary request and retry, record unknown usage as unknown, and separate cold-cache from cache-assisted costs where possible. Infrastructure retries must not become unreported extra chances to answer correctly.

For the new fixed-option forecasts, propose top-choice accuracy and proper probability scores such as Brier score and log loss, alongside format validity and completion rate. Keep the older ranking metric separate where the ranking task is used. Specify clipping and failure handling before evaluation. Report task types separately, give case-level uncertainty intervals, and include an aggregate that does not let cases with many items dominate silently. Selective prediction can have a risk-versus-coverage plot, but should not replace performance on the full assigned set.

Track paired changes from the immutable baseline: wrong-to-right, right-to-wrong, unchanged, and failed. These transitions can be counted mechanically after scoring without an LLM judge. Evidence-use and failure-category annotations can supplement them, but must be labelled model-assisted when they are.

Before interpreting gains, use controls aimed at our actual risks: attempted reads of withheld data; future facts hidden behind tools; nonexistent tool inputs; missing calculator fields; irrelevant retrieval; deliberately conflicting evidence; truncated API responses; and saved-output replay through the scorer. Case content and retrieved documents are data, never instructions that can change the run protocol. These checks establish bounded software properties, not clinical truth.

## What remains unproven

No reviewed study directly validates this exact combination of automatic case construction, dual chronologies, fixed candidate options, and probabilistic next-event forecasting. The absence of human reviewers is therefore a substantive limit on what we can claim, not an obstacle that consensus voting removes.

The first real pilot needs to establish whether our items and scores are usable. The first harness experiment then needs to establish whether the wrapper improves on a strong no-tool baseline. This search supplies candidate mechanisms, implementation references, and failure tests; it does not establish a winning harness in advance.
