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
