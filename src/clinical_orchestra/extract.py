"""Turn a case report into a validated, ordered timeline.

The extraction model's job is deliberately small: split a narrative that already exists into ordered
events and quote the sentence that supports each one. It is not asked to judge, infer, or fill gaps.
Everything it produces is then checked against the source text, and anything it cannot support with
a real quote is discarded.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .events import (
    ACTION,
    RESULT,
    YIELD_TIERS,
    CaseTimeline,
    Event,
    Violation,
    is_grounded,
    validate_timeline,
)

EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured clinical timelines from published case reports. "
    "You never infer, never add clinical knowledge, and never write anything not stated in the text. "
    "Return only valid JSON."
)

EXTRACTION_PROMPT = """Below is the text of a published case report. Split it into an ordered timeline of events.

An event is one of:
- "action": a test, imaging study, procedure, referral, or treatment that was ordered or performed.
- "result": what an action showed. Every result must reference the action it belongs to.
- "diagnosis": a diagnosis that was reached, considered as leading, or revised.
- "progression": the patient's condition changed on its own (new symptom, deterioration, recovery).
- "response": the patient's condition changed after a treatment was given.

Rules you must follow exactly:
1. Order events as they happened to the patient, not as they are mentioned in the text. If the text
   is written out of order, put the events in real chronological order.
2. For every event, "source_span" must be a VERBATIM span copied character-for-character from the
   case text. Do not paraphrase it, do not fix its grammar, do not join two distant sentences.
   Copy at least one full clause, roughly 12 to 300 characters.
3. "summary" is a short canonical name for the event, as a clinician would say it
   (for example "lumbar puncture", "brain MRI with contrast", "anti-NMDAR antibody testing").
4. "detail" holds the specifics: for an action, what exactly was ordered; for a result, what it
   showed; for a diagnosis, the diagnosis.
5. "yield_tier" says what the event's result DID, using only what the text says:
   3 = its result established the final diagnosis (at most one or two events in a case)
   2 = its result meaningfully changed what was being considered
   1 = normal, non-contributory, or only confirmed what was already known
   Use 1 when the text does not say. Do not guess importance from your own medical knowledge.
6. "presentation" is the patient's initial state before any of these events: demographics,
   presenting complaint, and the initial history and exam as given. Copy it faithfully and do not
   include anything that was learned later.
7. If the text does not support an event, leave it out. A short accurate timeline is correct; a long
   invented one is not.

Return JSON of exactly this shape:
{{
  "presentation": "<the initial state, in the report's own words>",
  "events": [
    {{
      "index": 0,
      "type": "action" | "result" | "diagnosis" | "progression" | "response",
      "summary": "<short canonical name>",
      "detail": "<specifics>",
      "source_span": "<verbatim quote from the case text>",
      "yield_tier": 1,
      "action_index": null
    }}
  ]
}}

For a "result" event, "action_index" must be the index of the action it reports on. For every other
type it must be null.

CASE REPORT TEXT:
---
{case_text}
---
"""


@dataclass
class ExtractionOutcome:
    timeline: CaseTimeline | None
    violations: list[Violation]
    dropped_events: list[dict]
    accepted: bool
    reason: str = ""


def _parse_json(content: str) -> dict:
    """Parse the model's JSON, tolerating a ```json fence when a provider adds one."""
    text = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def _coerce_events(raw_events: list) -> list[Event]:
    events: list[Event] = []
    for position, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            continue
        try:
            yield_tier = int(raw.get("yield_tier", 1))
        except (TypeError, ValueError):
            yield_tier = 1
        if yield_tier not in YIELD_TIERS:
            yield_tier = 1
        action_index = raw.get("action_index")
        if action_index is not None:
            try:
                action_index = int(action_index)
            except (TypeError, ValueError):
                action_index = None
        events.append(
            Event(
                index=int(raw.get("index", position)),
                type=str(raw.get("type", "")).strip().lower(),
                summary=str(raw.get("summary", "")).strip(),
                detail=str(raw.get("detail", "")).strip(),
                source_span=str(raw.get("source_span", "")),
                yield_tier=yield_tier,
                action_index=action_index,
            )
        )
    return events


def extract_timeline(
    *,
    client,
    case_id: str,
    case_text: str,
    source: dict,
    min_events: int = 4,
    max_ungrounded_fraction: float = 0.25,
    max_tokens: int = 16000,
) -> ExtractionOutcome:
    """Extract a timeline, drop what isn't grounded, and decide whether the case is usable.

    Ungrounded events are removed rather than repaired: a quote the model could not produce is a
    quote that probably was not there. A case that loses too many events is rejected outright, since
    heavy dropping means the extraction did not track the text.
    """
    response = client.chat(
        prompt=EXTRACTION_PROMPT.format(case_text=case_text),
        temperature=0.0,
        max_tokens=max_tokens,
    )
    try:
        payload = _parse_json(response.content)
    except json.JSONDecodeError as exc:
        return ExtractionOutcome(None, [], [], False, f"model did not return valid JSON: {exc}")

    events = _coerce_events(payload.get("events", []))

    kept: list[Event] = []
    dropped: list[dict] = []
    for event in events:
        if is_grounded(event.source_span, case_text):
            kept.append(event)
        else:
            dropped.append({"index": event.index, "summary": event.summary, "reason": "ungrounded"})

    if events and len(dropped) / len(events) > max_ungrounded_fraction:
        return ExtractionOutcome(
            None,
            [],
            dropped,
            False,
            f"{len(dropped)}/{len(events)} events were not grounded in the source text",
        )

    # Renumber after dropping so indices stay contiguous, and repair the result->action links.
    remap = {event.index: position for position, event in enumerate(kept)}
    renumbered = [
        Event(
            index=remap[event.index],
            type=event.type,
            summary=event.summary,
            detail=event.detail,
            source_span=event.source_span,
            yield_tier=event.yield_tier,
            action_index=(
                remap.get(event.action_index)
                if event.type == RESULT and event.action_index is not None
                else None
            ),
        )
        for event in kept
    ]

    timeline = CaseTimeline(
        case_id=case_id,
        source=source,
        presentation=str(payload.get("presentation", "")).strip(),
        events=renumbered,
    )
    violations = validate_timeline(timeline, case_text)

    if len(renumbered) < min_events:
        return ExtractionOutcome(
            timeline, violations, dropped, False, f"only {len(renumbered)} usable events"
        )
    if not any(event.type == ACTION for event in renumbered):
        return ExtractionOutcome(timeline, violations, dropped, False, "no actions in the timeline")
    if violations:
        codes = sorted({violation.code for violation in violations})
        return ExtractionOutcome(timeline, violations, dropped, False, f"violations: {codes}")

    return ExtractionOutcome(timeline, [], dropped, True)
