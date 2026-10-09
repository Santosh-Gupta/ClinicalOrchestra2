# Journal

Durable things learned about the data and the task. Add entries as you learn them, and cite the case
or the run. Design decisions go in `docs/DESIGN_DECISIONS.md` instead; this file is for observations.

---

## 2026-09-07 — Case reports leak the answer through the presentation

`PMC13544422` is a goat farmer who keeps his own herd, drinks unpasteurized milk, and had probable
contact with abortion material. The presentation alone hands you brucellosis. Every later item in
that case is easier than it looks, and the "Wright agglutination test — what did it show?" item is
close to self-answering, because Wright agglutination *is* the brucellosis test.

This is not an extraction bug. It is how case reports are written: backwards from a known answer,
with the details that turned out to matter placed early. Redacting later events does not remove it.

Consequence: item difficulty cannot be assumed and must be measured. See D-10.

---

## 2026-09-07 — Roughly a quarter of extracted actions are bundles

11 of 41 action items name more than one orderable thing: "blood cultures and Wright agglutination
test", "doxycycline and rifampin", "abdominal ultrasonography and MRCP".

This is faithful to the source — clinicians really do order several things at once — so it is not an
error to fix in extraction. It means the single-answer framing is wrong for a substantial minority of
items, and it is the strongest practical argument for the budgeted-set variant ("name up to three
things"). Flagged as `bundled_action` in the item data.

---

## 2026-09-07 — The answer-bearing field differs by event type

For a `result` event, the summary is a label that restates the question ("Wright agglutination test
result") while the answer sits in the detail ("positive at a titer of 1/160"). Grading the summary
would have made every result item trivially correct, and the bug was invisible until a real item was
read end to end.

General lesson: inspect real generated items by eye before trusting any scoring code. The unit tests
all passed while this was wrong, because they tested the grading rules rather than which field the
rules were applied to.

---

## 2026-09-07 — A validator that never fires is not evidence of clean data

The source-grounding check dropped 0 of ~110 events on the first real run. That looked like success
and could equally have been a broken check.

Negative controls settled it: changing one word in a real quote, and gluing two distant fragments
together, are both rejected; the unmodified quote and a case/whitespace-folded version both pass. The
extraction model was genuinely copying faithfully.

Do this for any validator whose pass rate is suspiciously high.

---

## 2026-09-07 — Only about 40% of PMC open-access case reports are usable

Of the first 40 candidates matching the fetch query, 17 were CC BY-NC-ND, 5 CC BY-NC, 1 CC BY-NC-SA,
and 1 was over the length cap. 16 remained.

Budget roughly 2.5 articles fetched per usable case. The underlying pool is large — the query matched
4,719 — so this is a throughput cost, not a ceiling.

---

## 2026-09-16 — A real quote does not validate its attached claim

A no-network synthetic control, case ID `synthetic-validation-control`, used the source
`MRI showed no mass. The patient improved.` An `ACTION` event had summary `Appendectomy`, detail
`An operation occurred.`, and the real `source_span` `MRI showed no mass.` Its presentation was
`An unsupported diagnosis was known on admission.`

`validate_timeline` returned `[]`: no violations. This is expected from the current implementation,
which checks quote occurrence and structural links, not whether the quote entails the event or
supports the presentation. The earlier quote-mutation controls still establish that string
grounding works; they do not establish semantic or temporal validity.

This synthetic failure does not establish an error rate in the existing case corpus. It establishes
a missing check to address in the next design. See Open D-16 and `docs/BRAINSTORM_ROUND3.md`.


---

## 2026-09-17 — Synthetic construction controls and cache reuse

Case `synthetic-dual-timeline` is an invented software fixture, not a published patient case.
Its family-disclosed history physically predates admission but is learned on day 4. The new
compiler keeps it out of earlier inputs and includes it after disclosure. Facts within each
information phase are explicitly unordered. Exact-source quote checks reject corrupted spans;
a separate negative control attaches a real assay-order quote to an appendectomy claim. The
mechanical checker accepts the quote, while a scripted contradicted audit blocks dependent items.
This verifies the audit gate, not whether a real model reliably catches that error.

The two-role scripted demo exports eight pairs (four per constructor role: two action, one result,
one response) from one case cluster. Run `runs/construction/20260917T155431Z-0b3a72ff` and its
rerun `runs/construction/20260917T155431Z-43065792` have byte-identical inputs and outputs.
The rerun makes zero HTTP requests and uses only cached scripted responses. Model labels in these
runs identify configuration slots, not models that actually answered. All 52 no-network tests pass.

Additional controls cover audit omissions, per-case rejection denominators, duplicate case IDs,
malformed response retention, cache tampering, source/test split gates, request budgets, peak-window
boundaries and retry guards. A response-log write failure stops without sending the request again.
The compiler ending-invariance test does not establish full-source LLM extraction invariance.
No paid inference, real label quality estimate or constructor ranking was obtained.
