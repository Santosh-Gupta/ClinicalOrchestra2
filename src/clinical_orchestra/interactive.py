"""Offline case-pack checks and an observed-only request resolver.

The resolver belongs in a host process. It is not a security boundary if a solver can import or
inspect its CasePack; the evaluation worker must keep packs and source text out of solver mounts.
Clinical timing and answer entailment require an independent construction audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from .events import is_grounded

DOCUMENTED = "documented"
NOT_DOCUMENTED = "not_documented"
NOT_AVAILABLE = "not_available_at_cutoff"
_CARD_STATUSES = frozenset({DOCUMENTED, NOT_AVAILABLE})


@dataclass(frozen=True)
class EvidenceCard:
    card_id: str
    request_id: str
    status: str
    answer: str
    source_span: str
    source_location: str
    clinical_time: str
    known_phase: str
    prerequisites: tuple[str, ...] = ()
    stability_reason: str = ""


@dataclass(frozen=True)
class CasePack:
    case_id: str
    presentation: str
    presentation_spans: tuple[str, ...]
    anchor_phase: str
    cards: tuple[EvidenceCard, ...]
    option_ids: tuple[str, ...]
    gold_option_id: str


@dataclass(frozen=True)
class RequestResult:
    request_id: str
    status: str
    answer: str = ""
    card_id: str | None = None


def validate_pack(pack: CasePack, source_text: str, menu_ids: tuple[str, ...]) -> None:
    """Reject mechanically invalid packs before any interactive run.

    This proves quote presence, not clinical meaning, timing or completeness. An independent
    chronology and evidence audit must approve those before a pack becomes a benchmark case.
    """
    if not pack.case_id.strip() or not pack.anchor_phase.strip():
        raise ValueError("case_id and anchor_phase are required")
    if not pack.presentation.strip() or not pack.presentation_spans:
        raise ValueError("presentation and its source quotes are required")
    if any(not is_grounded(span, source_text) for span in pack.presentation_spans):
        raise ValueError("presentation quote not found in source")
    if not menu_ids or len(menu_ids) != len(set(menu_ids)) or any(not x.strip() for x in menu_ids):
        raise ValueError("menu IDs must be nonempty and unique")
    if not pack.option_ids or len(pack.option_ids) != len(set(pack.option_ids)):
        raise ValueError("terminal option IDs must be nonempty and unique")
    if any(not x.strip() for x in pack.option_ids) or pack.gold_option_id not in pack.option_ids:
        raise ValueError("invalid terminal gold option")
    card_ids: set[str] = set()
    request_ids: set[str] = set()
    for card in pack.cards:
        if not card.card_id.strip() or card.card_id in card_ids:
            raise ValueError("evidence card IDs must be nonempty and unique")
        card_ids.add(card.card_id)
        if card.request_id not in menu_ids or card.request_id in request_ids:
            raise ValueError("each evidence card must use one unique menu request ID")
        request_ids.add(card.request_id)
        if card.status not in _CARD_STATUSES:
            raise ValueError("invalid evidence card status")
        if not is_grounded(card.source_span, source_text):
            raise ValueError("evidence card quote not found in source")
        if not card.source_location.strip() or not card.clinical_time.strip() or not card.known_phase.strip():
            raise ValueError("evidence card chronology and location are required")
        if card.status == DOCUMENTED and (not card.answer.strip() or not card.stability_reason.strip()):
            raise ValueError("documented card needs answer and stability reason")
        if card.status == NOT_AVAILABLE and card.answer.strip():
            raise ValueError("unavailable card must not expose an answer")
        if len(card.prerequisites) != len(set(card.prerequisites)):
            raise ValueError("duplicate prerequisites")


def resolve_request(pack: CasePack, request_id: str, menu_ids: tuple[str, ...]) -> RequestResult:
    """Return a frozen documented answer or explicit absence; never synthesize a result.

    The caller must validate the pack and common menu before assignment, enforce request budgets,
    and persist each request/result in the attempt journal.
    """
    if request_id not in menu_ids:
        raise ValueError("request ID is outside the frozen menu")
    for card in pack.cards:
        if card.request_id == request_id:
            if card.status == DOCUMENTED:
                return RequestResult(request_id, DOCUMENTED, card.answer, card.card_id)
            return RequestResult(request_id, NOT_AVAILABLE, "", card.card_id)
    return RequestResult(request_id, NOT_DOCUMENTED)
