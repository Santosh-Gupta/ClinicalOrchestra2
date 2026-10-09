# Science harness evidence and implications for clinical forecasting

Research date: 8 October 2026. This extends the [broad review](HARNESS_LITERATURE_REVIEW_2026-10-04.md) and informs **D-20** and the [architecture](NEXT_STEP_ARCHITECTURE.md). Design changes are pending implementation.

Claude Science provides useful patterns for programmatic tool use, durable evidence, and verification. The strongest open implementation reference found here is Prime Agent; the most useful complementary engineering description is Edison's Kosmos. None establishes superiority on our five-family, fixed-prefix clinical forecasting task. Product documentation establishes documented behavior, source inspection establishes implementation details, and benchmark papers establish results only under their reported conditions. These are different kinds of evidence.

## What is publicly documented about Claude Science

The [June launch announcement](https://www.anthropic.com/news/claude-science-ai-workbench), [product guide](https://claude.com/resources/guides/claude-science-product-guide/claude-science-product-overview), and detailed application documentation describe an agent-driven scientific workbench. The guide emphasizes composable scientific skills, specialist environments, and inspection of generated figures. The detailed reference is more precise about runtime limits and reviewer behavior. The [changelog](https://claude.com/docs/claude-science/changelog) lists version 0.1.60 on 7 October, including an execution fix; configurations and product versions matter when comparing runs.

| Mechanism | Public evidence | Implication for our design |
| --- | --- | --- |
| Programmatic tools through a host bridge | The [Compliance API documentation](https://platform.claude.com/docs/en/manage-claude/compliance-sessions) explicitly says Science calls MCP connectors inside its `repl` tool, including `host.mcp(...)`. Connector results enter the transcript only where code prints them. | Record each actual broker request and response separately. A transcript containing one code cell is not a complete tool-use ledger. |
| Persistent computational state | [Tools and environments](https://claude.com/docs/claude-science/tools-and-environments) documents Python/R variables surviving between steps. Kernels end on session termination, environment restart, or roughly 30 minutes idle. | Keep tables and intermediate data outside the prompt, but persist required state as artifacts. Kernel memory alone is not durable recovery. |
| Versioned outputs with execution history | [Artifacts](https://claude.com/docs/claude-science/artifacts) records messages, code, execution logs, environment versions, and review findings. Links identify particular versions. The execution log takes precedence if it disagrees with the reconstructed code view. | Store immutable prediction versions, evidence references, executed code and actual outputs. A polished reproduction script cannot replace the execution record. |
| A separate evidence reviewer | [Reviewer documentation](https://claude.com/docs/claude-science/the-reviewer) describes checks against responses, plans, artifacts and execution records. It checks unsupported citations and mismatched values, but does not rerun analyses or decide whether the chosen research method was appropriate. | Test an evidence-integrity reviewer, distinct from a second agent guessing the answer and distinct from the benchmark scorer. |
| Session boundaries and delegation | [Core concepts](https://claude.com/docs/claude-science/core-concepts) gives sessions their own workspaces and describes optional parallel tracks with inspectable transcripts. Cross-session memory is separately configurable. | One isolated session per benchmark cutoff; optional children inherit that cutoff and budget. Disable cross-item memory in the primary evaluation. |
| Skills and connectors are separate | [Connectors and skills](https://claude.com/docs/claude-science/connectors-and-skills) distinguishes instructions loaded when relevant from access to data sources. Featured connectors are read-only; users can add methods and integrations. | Maintain a small frozen capability catalog. Load instructions only when needed; do not equate a skill description with permission to access a resource. |

Two qualifications matter. The detailed reviewer page says automatic review starts off on Pro and on for Max/Team/Enterprise; the broad guide's blanket default claim is too coarse. The guide also suggests persistence across reboots, while the runtime reference specifies when kernels terminate. Use durable saved artifacts as the recovery contract, rather than assuming live variables survive. These distinctions change how we would implement and test the same patterns.

The [2 October changelog](https://claude.com/docs/claude-science/changelog) also describes optional automatic switching to another model after a safeguards flag. Our comparisons must record the actual serving model and disable undeclared substitution: a successful product fallback could otherwise become an incorrectly attributed benchmark result.

The public evidence supports calling Science a **programmatic scientific agent with RLM-like mechanisms**. It does not establish that the complete application implements a particular RLM paper unchanged, or expose its full production prompts, routing policy, recursive-call limits, internal model assignments, and controlled component ablations. The user's engineer quotation is consistent with the documented bridge, but it is not a specification of those missing details. No controlled comparison establishing Claude Science as the best clinical next-step harness was located.

The application itself is a research workbench, explicitly [not intended for clinical or diagnostic use](https://claude.com/docs/claude-science/overview). Borrowing engineering patterns for benchmark research does not validate a patient-facing product. Nor does local execution imply that all information remains local: [core concepts](https://claude.com/docs/claude-science/core-concepts) explains that content read into a conversation is sent to Anthropic.

## Other systems worth learning from

### Prime Agent as an inspectable programmatic runtime

The [Prime Agent repository](https://github.com/PrimeIntellect-ai/prime-agent) combines a Python control environment, child agents, reusable skills, and supplemental harness state. This review inspected commit `afe8d14c4526cf492c4ab17f8eb3e150d329fe8b`, including its README, runtime protocol, and harness-state implementation. Its root license is MIT. The current checkout uses Rust crates and a Python runtime; older descriptions of its TypeScript layout are not a map of this revision.

The [runtime protocol](https://github.com/PrimeIntellect-ai/prime-agent/blob/afe8d14c4526cf492c4ab17f8eb3e150d329fe8b/prime-agent-runtime/src/rlm/repl.md) provides request IDs, host request/reply messages, output events, interruption, and snapshot/restore reporting. Snapshot manifests identify skipped or failed variables; some raw process output cannot be attributed to a particular code cell. These are useful models for explicit incomplete recovery and honest trace attribution.

The [README](https://github.com/PrimeIntellect-ai/prime-agent/blob/afe8d14c4526cf492c4ab17f8eb3e150d329fe8b/README.md) explicitly says worker/kernel processes are **not a security sandbox**. Therefore, adopting its interface would still require our own execution isolation and hidden-data boundary.

The [paper](https://arxiv.org/html/2608.23552v1) describes descendant-inclusive accounting and versioned refinement. It also reports a trace in which an agent exploited an environment shortcut and preserved it as a reusable skill. This is a direct reason to freeze skills and policy during a benchmark run. Its coding, game and long-context evaluations motivate experiments; they do not demonstrate clinical transfer.

**Decision:** use its protocol and accounting as implementation references. Do not replace the current Python project with the full application, or enable continual self-improvement on test cases.

### Edison Kosmos as an execution and evidence architecture

Edison's [May 2026 engineering account](https://advances.edisonscientific.com/research/how-we-built-kosmos/) describes a shift from a lengthy batch workflow toward a persistent code-writing agent around a scientific world model. It describes separate subagent sandboxes, shared files, controlled network traffic, and credentials injected outside sandboxes. Its infrastructure serves substantial scientific computation; that scale is unnecessary for our initial text forecasts.

**Decision:** adapt the separation of orchestration, computation, credentials and durable evidence. A local structured evidence store is enough initially. Do not turn an agent's evolving model of the patient into a replacement for immutable reported observations. Kosmos's hypothesis-testing loop may acquire new experimental results; our fixed-prefix solver cannot.

### PaperQA3 as a retrieval specialist

[PaperQA3's February release](https://advances.edisonscientific.com/research/edison-literature-agent/) adds selective figure/table inspection, source-quality metadata, and more flexible document examination and stopping. Its comparisons also change models, access, and other settings; the claimed improvement cannot be assigned solely to relaxed orchestration.

**Decision:** use provenance-rich retrieval with optional deeper inspection when needed. Store retraction/status metadata where available. For our own case source, figures and captions are hidden unless explicitly compiled as permitted input: an image can disclose the future as readily as a paragraph. Multimodal case inputs remain a separate contract extension. General reference retrieval should not return the source case or identifiable copies.

### Biomni and Aviary as tool and environment references

[Biomni](https://github.com/snap-stanford/Biomni) supplies biomedical tools and software with retrieval-assisted planning and code execution. Its README also notes that agent-level model parameters do not necessarily govern database-query models; shared configuration is needed for consistent routing. Hidden secondary calls are therefore an accounting concern, not just a transport detail.

[Aviary](https://github.com/Future-House/aviary) and [LDP](https://github.com/Future-House/ldp), discussed in the earlier review, separate an agent from its environment. **Decision:** borrow that stable interface and selected tool contracts. Avoid importing a large biomedical software environment for a benchmark whose initial tools are evidence reading, retrieval, and arithmetic. Record the actual model behind every helper call.

### Google AI co-scientist and diagnostic orchestration

[Google's AI co-scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/) uses a supervisor and specialized processes for generating, reviewing, ranking and evolving hypotheses. That is relevant to generating research alternatives, but a promising hypothesis is not an observed patient outcome. Its scientific validation does not make agent ranking a clinical answer key.

The earlier review covers [MAI-DxO](https://arxiv.org/html/2506.22405v1), [AMIE management](https://www.nature.com/articles/s41586-026-10764-5), and [on-premise diagnostic agents](https://www.nature.com/articles/s41591-026-04609-x). They motivate explicit competing hypotheses and model-specific ablations. A simulated finding from a gatekeeper cannot enter our factual inputs. The critic result in the on-premise study and the outcome-prediction comparisons in [AgentRx](https://proceedings.mlr.press/v333/al-jorf26a.html) also argue against assuming a committee improves predictions.

**Decision:** delegate a concrete evidence task if experiments justify it; do not instantiate a standing panel of medical personas. Keep independent semantic construction audits, evidence review during solving, and deterministic scoring as different roles with different data permissions.

### BixBench3 as a particularly useful evaluation precedent

[BixBench3](https://arxiv.org/html/2608.25286v1), August 2026, compares computational outputs with artifacts from published studies. It uses Inspect AI, persistent execution tools, bounded runs, and an external network gateway. Its main artifact grading is programmatic; model-generated process-failure annotations are separate. This supports our proposed separation of outcomes and explanatory audits.

Its expert-calibrated artifact thresholds cannot be reproduced simply by substituting an LLM, and its network adjudicator is not proof that source leakage is impossible. **Decision:** retain exact scoring and an explicit isolation audit. This is also a concrete scientific precedent for Inspect as the outer runner, rather than a reason to build our own scheduling framework immediately.

### Forecasting systems and continual adaptation

[ForecastBench](https://forecastbench.org/leaderboards/) distinguishes standardized baselines from tournament systems with richer tools and context. A leaderboard position belongs to that complete configuration. Our reports should likewise distinguish a controlled harness ablation from the best complete system assembled for a model.

[Milkyway](https://arxiv.org/html/2604.15719v1) is directly relevant conceptually: it records forecast checkpoints, factors, evidence and uncertainty, then updates procedural guidance. However, the inspected v1 retains unfilled cohort-size placeholders in its mechanism-ablation section. Treat this as an exploratory design lead, not decisive quantitative evidence. Its forward-only adaptation across live questions also differs from our frozen retrospective items.

**Decision:** record which evidence changed a forecast. Any sequential learning track must declare a forward-only protocol separately; the primary benchmark cannot carry later information back to earlier cutoffs or improve itself on test outcomes.

## Additional engineering lessons

[Anthropic's Managed Agents account](https://www.anthropic.com/engineering/managed-agents) separates a durable session log, replaceable orchestration, and replaceable execution environments. This is adjacent engineering evidence, not documentation that Science uses the identical implementation. **Our application:** a crashed runtime should not erase the run ledger, and recovery should not silently request a new model sample.

[Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) explains tool discovery on demand and filtering intermediate data before returning it to the model. **Our application:** allow references to stored results and bounded reads, with every underlying action brokered. Reduced prompt tokens must be measured alongside total tool activity; a shorter transcript does not imply a cheaper or more reliable run.

[Anthropic's multi-agent Research account](https://www.anthropic.com/engineering/multi-agent-research-system) emphasizes clear delegated objectives, tools, output contracts, and effort limits; it also describes much higher token use than ordinary chat. That is not a universal multiplier. **Our application:** compare delegation against independent forecast samples and single-agent tool use at declared resource limits, including child calls and review.

## Concrete changes to the plan

The following are our design choices informed by the evidence above, not claims about any vendor's internals.

1. **Keep policy replaceable.** The same input-only worker contract supports direct prediction, repeated-request averaging, one evidence action, and a bounded programmatic strategy. The last policy can choose several allowed operations; the host limits it. A REPL is an optional execution backend, not a mandatory tax on every item.
2. **Make the broker authoritative.** Validate access and reserve budget before dispatching every retrieval, calculation, reviewer or child-model request. Record parent/child IDs and actual responses. Generated code cannot bypass permissions by importing an SDK, spawning a process or using raw network access.
3. **Give evidence an explicit status.** Separate reported facts, external references, calculations, hypotheses, and review findings. Calculations identify their inputs, units and assumptions. Hypotheses may change; patient facts cannot be rewritten. Contradictions remain visible.
4. **Use narrow review contracts.** Deterministic checks cover schemas, units, identifiers and reproducible arithmetic. An independent model can flag unsupported interpretations. Neither sees gold. Review findings remain fallible evidence; the primary score still compares the saved forecast with the hidden label.
5. **Persist actual work.** Store each forecast version, source response, executed operation and review result outside the sandbox. Recover from committed records; report incomplete restoration. Prefer ordinary structured artifacts over treating an opaque live-kernel snapshot as the sole record.
6. **Freeze learning during evaluation.** Prompts, skills, routing, memory policy, capabilities and environments are versioned and fixed. A new item gets a clean workspace. Shared prompt caching must not become shared patient memory.
7. **Test value rather than architectural fashion.** Measure per-family probability quality, completion, cost, latency and regressions against the initial forecast. Do not stop at nicer rationales or more citations. Match evidence access when isolating orchestration effects, and separately report best-system configurations.

## Repositories and reuse priority

| Priority | Reference | Intended use |
| --- | --- | --- |
| First integration candidate | [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | Outer scheduling, model interfaces and reports; retain our input-only worker and independent scorer |
| First programmatic runtime reference | [Prime Agent, pinned revision](https://github.com/PrimeIntellect-ai/prime-agent/tree/afe8d14c4526cf492c4ab17f8eb3e150d329fe8b) | Host protocol, operation traces, recovery and descendant accounting |
| Targeted retrieval reference | [PaperQA](https://github.com/Future-House/paper-qa) | Source-linked evidence and selective document inspection; a hosted corpus is a separate dependency |
| Targeted biomedical tools | [Biomni](https://github.com/snap-stanford/Biomni) | Tool selection and selected adapters, after checking inputs and hidden model calls |
| Optional environment layer | [Aviary](https://github.com/Future-House/aviary) | Reconsider if interactive trajectories become a declared benchmark track |
| Experiment governance reference | [Anabasis](https://github.com/s-smits/anabasis) | Keep the earlier recommendation to study freezing, verification boundaries and accounting; its full autonomous workflow is not the initial base |

Claude Science and Kosmos are architecture references, not verified drop-in open-source bases. Prime's source was inspected without executing its agent or installing dependencies. No paid experiments were run. The immediate build order remains contract fixtures and deterministic scoring, then isolation and baselines, followed by individually measured harness variants. The programmatic interface should be designed now so testing it later does not require rebuilding the runner.
