"""Case timelines: the event schema, and the validation that keeps golds grounded in the source.

A case report is turned into an ordered list of typed events. Everything downstream — the items, the
states, the golds, the partial credit — is derived from that list.

The rule that makes this different from v1: **every event must quote the source text that supports
it, and that quote must actually appear in the source.** An event whose quote cannot be found is
dropped, not trusted. That check is mechanical, so the extraction model cannot invent a gold no
matter how confidently it writes one.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

# --- event types -------------------------------------------------------------------------------
#
# These are deliberately kept few and clinically meaningful. Scores are always reported per type;
# they measure different skills against golds of different quality, and pooling them produces a
# number that means nothing.

ACTION = "action"  # a test, image, procedure, referral, or treatment was ordered or performed
RESULT = "result"  # what an action showed
DIAGNOSIS = "diagnosis"  # a diagnosis was reached or revised
PROGRESSION = "progression"  # the patient's course changed on its own
RESPONSE = "response"  # the patient's course changed after a treatment

EVENT_TYPES = frozenset({ACTION, RESULT, DIAGNOSIS, PROGRESSION, RESPONSE})

# --- yield tiers --------------------------------------------------------------------------------
#
# Graded credit comes from what an event's result DID, not from where it sits in the sequence.
# Position decay rewards mimicking the order a team happened to work in; case reports are published
# partly because that order was circuitous, so mimicking it is the wrong target.

YIELD_ESTABLISHED = 3  # its result established the diagnosis
YIELD_CHANGED = 2  # its result meaningfully changed the differential
YIELD_NEUTRAL = 1  # normal, non-contributory, or merely confirmatory
YIELD_NONE = 0  # not part of this case

YIELD_TIERS = frozenset({YIELD_ESTABLISHED, YIELD_CHANGED, YIELD_NEUTRAL, YIELD_NONE})


@dataclass(frozen=True)
class Event:
    """One thing that happened, in order, with the source text that proves it happened."""

    index: int
    type: str
    summary: str  # short canonical phrasing, e.g. "lumbar puncture"
    detail: str = ""  # the specific content: what was ordered, or what the result was
    source_span: str = ""  # verbatim quote from the case text supporting this event
    yield_tier: int = YIELD_NEUTRAL
    action_index: int | None = None  # for a RESULT, the index of the ACTION it belongs to

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseTimeline:
    case_id: str
    source: dict[str, Any]  # pmcid, doi, title, license, publication date
    presentation: str  # the opening state, before any event
    events: list[Event] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "source": self.source,
            "presentation": self.presentation,
            "events": [event.to_dict() for event in self.events],
        }


# --- grounding ------------------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Fold the differences that don't matter, so a real quote isn't rejected over a curly apostrophe.

    Unicode-normalizes, lowercases, converts dash and quote variants to ASCII, and collapses runs of
    whitespace. Deliberately does NOT strip words: a quote must still match the source's wording.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―−]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def is_grounded(span: str, source_text: str, *, min_chars: int = 12) -> bool:
    """True when `span` appears verbatim in `source_text` after normalization.

    Very short spans are rejected: a five-character quote will match something by accident and proves
    nothing about whether the event is real.
    """
    if not span or len(span.strip()) < min_chars:
        return False
    return normalize(span) in normalize(source_text)


@dataclass(frozen=True)
class Violation:
    event_index: int | None
    code: str
    message: str


def validate_timeline(timeline: CaseTimeline, source_text: str) -> list[Violation]:
    """Return every reason this timeline is not safe to turn into benchmark items.

    An empty list means the timeline is internally consistent and every event is quoted from the
    source. A non-empty list means the case is dropped or repaired — never silently used.
    """
    violations: list[Violation] = []

    if not timeline.presentation.strip():
        violations.append(Violation(None, "empty_presentation", "presentation is empty"))

    indices = [event.index for event in timeline.events]
    if indices != sorted(indices):
        violations.append(Violation(None, "unordered", "event indices are not in ascending order"))
    if len(set(indices)) != len(indices):
        violations.append(Violation(None, "duplicate_index", "event indices are not unique"))

    for event in timeline.events:
        if event.type not in EVENT_TYPES:
            violations.append(
                Violation(event.index, "bad_type", f"unknown event type {event.type!r}")
            )
        if event.yield_tier not in YIELD_TIERS:
            violations.append(
                Violation(event.index, "bad_yield", f"unknown yield tier {event.yield_tier!r}")
            )
        if not event.summary.strip():
            violations.append(Violation(event.index, "empty_summary", "summary is empty"))
        if not is_grounded(event.source_span, source_text):
            violations.append(
                Violation(
                    event.index,
                    "ungrounded",
                    f"source_span not found verbatim in the case text: {event.source_span[:80]!r}",
                )
            )
        if event.type == RESULT:
            if event.action_index is None:
                violations.append(
                    Violation(event.index, "orphan_result", "result has no action_index")
                )
            elif event.action_index >= event.index:
                violations.append(
                    Violation(
                        event.index,
                        "result_before_action",
                        f"result at {event.index} points at action {event.action_index}",
                    )
                )
            elif event.action_index not in {
                e.index for e in timeline.events if e.type == ACTION
            }:
                violations.append(
                    Violation(
                        event.index,
                        "orphan_result",
                        f"action_index {event.action_index} is not an action",
                    )
                )

    established = [e for e in timeline.events if e.yield_tier == YIELD_ESTABLISHED]
    if len(established) > 2:
        # More than a couple of "this established the diagnosis" events means the extractor is
        # inflating importance, which would flatten the grading that the whole metric rests on.
        violations.append(
            Violation(
                None,
                "too_many_established",
                f"{len(established)} events marked as establishing the diagnosis",
            )
        )
    return violations
