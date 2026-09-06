# Lessons from v1

The previous project is [ClinicalOrchestra](https://github.com/Santosh-Gupta/ClinicalOrchestra). The
public write-up is
[here](https://santoshguptaml.substack.com/p/my-failed-attempt-at-making-a-medical). This file is the
short internal version: what went wrong, and what each mistake means for this project.

## The two problems that ended v1

**1. The benchmark was built circularly.**

Turning a published case report into a test question assumes the report contains everything a doctor
would need to reach the diagnosis. It usually doesn't. Case reports are written backwards from a known
answer — they explain a diagnosis rather than pose a puzzle, and they leave out the details that
turned out not to matter. Filling those gaps was done by an LLM, which means the quality of the test
was limited by the model writing it. That is a problem when the thing being measured is LLM
diagnostic reasoning.

Reaching a per-case standard that could be defended without expert review turned out to be the hard
part, and expert review was out of budget.

*What this means for v2:* the correct answer must come from the source document, not from a model's
opinion. The model's job shrinks to splitting a real timeline into steps, which is a smaller job and
one that can be checked against the text.

**2. Scoring couldn't be trusted.**

Comparing a predicted free-text diagnosis to a gold diagnosis needed an LLM judge. The judge was
noisy even at temperature 0, and the noise was large enough to produce apparent differences between
runs that were not real. Judge disagreement, not model behavior, was moving the numbers.

*What this means for v2:* score against a coded vocabulary wherever possible, so matching is exact.
Use a judge only for predictions that don't map to a code, flag every one of those, and report how
much of the score came from each path.

## Findings that did survive

**Models differ in where they rank the answer, not only in whether they get it.** The ranking of
models by top-1 accuracy is not the same as the ranking by top-5. Gemini 3.5 Flash was the clearest
example: mediocre at top-1, near the top at top-5. One reading is that its diagnostic ability is more
latent than other models' — that producing five ranked guesses gives it the reasoning room to surface
an answer it wouldn't have led with. This came from a benchmark that isn't airtight, so it's a
direction worth testing, not a conclusion.

*Implication:* score the whole ranked list, not just the first answer. This carried directly into v2's
graded scoring.

**Replacing the model's answers with retrieved ones makes things worse; adding to them helps.**
Naive substitution pushed the model's own correct answer out of the list. Keeping the model's top four
untouched and using retrieval only to fill the fifth slot improved top-5 accuracy across all three
models tested. Small effect, but it was the one consistently positive harness result.

*Implication:* a tool adds or flags. It does not overwrite.

**A checker that shares the model's mistakes can't catch them.** The v2-era verifier-gated editor was
supposed to only accept edits a verifier approved. The verifier was the same model, so it approved
plausible-sounding but wrong edits — for example, ratifying that a lab value ruled out a diagnosis
that was in fact the correct answer.

The deeper reason: prover-verifier pipelines work in formal math because the proof checker is a sound
oracle. Clinical diagnosis is defeasible — a conclusion can be reasonable given the evidence and still
be wrong — so there is no sound oracle, and a gated editor just inherits the model's reasoning errors.

*Implication:* the checker must be independent of the proposer, and it needs something real to check
against. v2 has a partial answer to this that v1 never had: the case's actual trajectory can serve as
an oracle during development, so we can measure whether an edit moved the answer closer to what
actually happened.

## Process mistakes worth not repeating

- **The hard case set was built from one model's failures.** That makes any score for that model on
  that set circular. It was excluded from the published comparison chart for this reason.
- **Identical outputs were judged twice** in early development metrics, and the judge's disagreement
  with itself appeared as a real difference between conditions.
- **Silent degradation.** Truncated responses, empty query plans, and quietly changed denominators
  each corrupted runs before being caught. Observability isn't overhead here; it is part of the
  experiment.
- **API cost accumulated faster than expected**, and by the time results were assembled, newer models
  had already made the numbers dated.
