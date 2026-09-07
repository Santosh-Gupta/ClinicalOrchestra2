"""Turn a validated timeline into benchmark items, and score answers against them.

One case yields many items — one per event past a short warm-up. Items are typed, and scores are
always reported per type: predicting what a test showed and predicting what to order next are
different skills measured against golds of different quality, so pooling them produces a number that
means nothing.

Partial credit follows two rules that are easy to get wrong:

1. Only events AFTER the cut earn partial credit. Naming something already in the visible state is
   repeating the prompt, not predicting, so it scores zero.
2. Partial credit is capped well below a correct answer and requires a type match. Otherwise the
   best strategy is to name the case's final diagnosis at every decision point and collect partial
   credit across the whole case.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from .events import ACTION, DIAGNOSIS, PROGRESSION, RESPONSE, RESULT, CaseTimeline, Event

# Scoring constants. Kept here, named, and referenced everywhere rather than being written inline
# at each call site, so a change to the grading scheme is one edit and shows up in a diff.
CORRECT = 1.0
LATER_MAX = 0.3  # the most a not-yet-taken future event can earn
LATER_DECAY = 0.6  # per step of distance beyond the immediate next event
SEEN = 0.0  # anything already visible in the state

# How many events must precede an item, so the model has a real state to reason from.
MIN_WARMUP_EVENTS = 2

QUESTIONS = {
    ACTION: "What should be done next for this patient? Name the single most appropriate next step.",
    RESULT: "{action_phrase} What did it show?",
    DIAGNOSIS: "What is the diagnosis?",
    PROGRESSION: "What happened to this patient next?",
    RESPONSE: "{action_phrase} How did the patient respond?",
}


@dataclass(frozen=True)
class GoldOption:
    """One acceptable answer, with the credit it earns.

    `answer` is the field a response is graded against, and which field that is depends on the item
    type. For an action, the answer is the action's name ("lumbar puncture"). For a result, the name
    is the giveaway — "Wright agglutination test result" restates the question — so the answer is
    the finding itself ("positive at a titer of 1/160"). Grading `summary` for every type would make
    every result item trivially correct.
    """

    summary: str
    detail: str
    answer: str
    event_index: int
    event_type: str
    yield_tier: int
    distance: int  # 0 for the immediate next event
    credit: float


@dataclass
class Item:
    item_id: str
    case_id: str
    cut_index: int
    type: str
    state: str
    question: str
    gold: GoldOption
    partial: list[GoldOption] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)  # already-seen summaries; must score zero
    flags: list[str] = field(default_factory=list)  # known quality problems with this item
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gold"] = asdict(self.gold)
        payload["partial"] = [asdict(option) for option in self.partial]
        return payload


# Types whose answer is the finding, not the name of the thing that produced it.
_ANSWER_IS_DETAIL = frozenset({RESULT, RESPONSE, PROGRESSION})


def answer_field(event: Event) -> str:
    """The text an answer to this event is graded against."""
    if event.type in _ANSWER_IS_DETAIL and event.detail.strip():
        return event.detail.strip()
    return event.summary.strip()


def _gold_option(event: Event, distance: int, credit: float) -> "GoldOption":
    return GoldOption(
        summary=event.summary,
        detail=event.detail,
        answer=answer_field(event),
        event_index=event.index,
        event_type=event.type,
        yield_tier=event.yield_tier,
        distance=distance,
        credit=credit,
    )


_BUNDLE_MARKERS = (" and ", " plus ", " + ", " with ", ", ", " & ")


def item_flags(event: Event) -> list[str]:
    """Known quality problems, attached to the item rather than silently tolerated.

    "bundled_action" marks an event naming more than one orderable thing ("blood cultures and Wright
    agglutination test", "doxycycline and rifampin"). Real clinicians do order several things at
    once, so these are not errors in the source — but they cannot be graded as a single answer.
    They belong in the budgeted-set variant of the task, not the single-answer one.
    """
    flags: list[str] = []
    if event.type == ACTION and any(marker in event.summary.lower() for marker in _BUNDLE_MARKERS):
        flags.append("bundled_action")
    if event.type in _ANSWER_IS_DETAIL and not event.detail.strip():
        flags.append("no_detail")
    return flags


def later_credit(distance: int) -> float:
    """Credit for an event `distance` steps beyond the immediate next one."""
    if distance <= 0:
        return CORRECT
    return round(LATER_MAX * (LATER_DECAY ** (distance - 1)), 4)


def render_state(timeline: CaseTimeline, cut_index: int) -> str:
    """Everything known up to (not including) the event at `cut_index`."""
    lines = ["PRESENTATION:", timeline.presentation.strip(), ""]
    prior = [event for event in timeline.events if event.index < cut_index]
    if prior:
        lines.append("COURSE SO FAR:")
        for event in prior:
            label = {
                ACTION: "Ordered",
                RESULT: "Result",
                DIAGNOSIS: "Considered",
                PROGRESSION: "Course",
                RESPONSE: "Response",
            }.get(event.type, event.type.title())
            detail = f" — {event.detail}" if event.detail else ""
            lines.append(f"- {label}: {event.summary}{detail}")
    return "\n".join(lines).strip()


def _action_phrase(timeline: CaseTimeline, event: Event) -> str:
    """Name the action a result or response belongs to, so the question is unambiguous."""
    if event.action_index is None:
        return "A test was performed."
    for candidate in timeline.events:
        if candidate.index == event.action_index:
            return f"{candidate.summary.capitalize()} was performed."
    return "A test was performed."


def build_items(timeline: CaseTimeline, *, min_warmup: int = MIN_WARMUP_EVENTS) -> list[Item]:
    """One item per event past the warm-up."""
    items: list[Item] = []
    events = sorted(timeline.events, key=lambda event: event.index)

    for position, event in enumerate(events):
        if position < min_warmup:
            continue

        question_template = QUESTIONS.get(event.type)
        if question_template is None:
            continue
        question = question_template.format(action_phrase=_action_phrase(timeline, event))

        gold = _gold_option(event, 0, CORRECT)

        # Partial credit: same-type events still in the future. Type match is required, so naming
        # the final diagnosis cannot earn credit on a "what test next" item.
        partial = [
            _gold_option(later, distance, later_credit(distance))
            for distance, later in (
                (index - position, events[index]) for index in range(position + 1, len(events))
            )
            if later.type == event.type
        ]

        items.append(
            Item(
                item_id=f"{timeline.case_id}:{event.index:03d}",
                case_id=timeline.case_id,
                cut_index=event.index,
                type=event.type,
                state=render_state(timeline, event.index),
                question=question,
                gold=gold,
                partial=partial,
                excluded=[prior.summary for prior in events[:position]],
                flags=item_flags(event),
                source=timeline.source,
            )
        )
    return items


# --- scoring -------------------------------------------------------------------------------------


def credit_for(item: Item, matched_event_index: int | None) -> float:
    """Credit for an answer that matched the event at `matched_event_index`.

    `matched_event_index` is decided by the matcher (exact vocabulary match for the ranking task, or
    a recorded and audited mapping for the generation task). This function only applies the grading
    rules, so the rules stay in one place and are testable without any model in the loop.
    """
    if matched_event_index is None:
        return 0.0
    if matched_event_index == item.gold.event_index:
        return CORRECT
    for option in item.partial:
        if option.event_index == matched_event_index:
            return option.credit
    # Anything else is either already visible in the state or not part of this case.
    return SEEN


def dcg(gains: list[float]) -> float:
    return sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))


def ndcg(ranked_gains: list[float], *, k: int | None = None) -> float:
    """Normalized discounted cumulative gain for a ranked answer list.

    Used for the ranking task, where the model orders a fixed candidate slate. Fully deterministic:
    no judge, no text matching, no threshold.
    """
    gains = ranked_gains[:k] if k else ranked_gains
    ideal = sorted(ranked_gains, reverse=True)[: len(gains)]
    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0:
        return 0.0
    return dcg(gains) / ideal_dcg
