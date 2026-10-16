"""Mechanical specialty-review controls; clinical relevance still needs independent model audit."""

from .evidence import check_evidence
from .schemas import ContractError, SPECIALTY, validate


def check_specialty_review(review: dict, indexed_source: dict) -> dict:
    validate(review, SPECIALTY)
    for domain in ("psychiatry", "neurology", "interaction"):
        check_evidence(review[domain]["evidence"], indexed_source,
                       required=review[domain]["material"])
    for cutoff in review["integrated_cutoffs"]:
        for key in ("psychiatric_pre_cutoff", "neurological_pre_cutoff", "later_target"):
            check_evidence(cutoff[key], indexed_source)

    track = review["proposed_track"]
    psych = review["psychiatry"]["material"]
    neuro = review["neurology"]["material"]
    interaction = review["interaction"]["material"]
    if review["patient_scope"] != "single" and track in {"psychiatry", "neurology", "mixed"}:
        raise ContractError("accepted track requires a single indexed patient")
    if track == "psychiatry" and (not psych or neuro or interaction or review["integrated_cutoffs"]):
        raise ContractError("pure psychiatry conflicts with material-domain flags")
    if track == "neurology" and (not neuro or psych or interaction or review["integrated_cutoffs"]):
        raise ContractError("pure neurology conflicts with material-domain flags")
    if track == "mixed":
        if not (psych and neuro and interaction and review["integrated_cutoffs"]):
            raise ContractError("mixed track requires both domains, interaction and integrated cutoff")
        if review["interaction"]["mechanism"] in {"none", "unclear"}:
            raise ContractError("mixed interaction mechanism is absent or unclear")
    if not interaction and review["interaction"]["mechanism"] not in {"none", "unclear"}:
        raise ContractError("nonmaterial interaction has a material mechanism")
    return review


def agreed_track(first: dict, second: dict, indexed_source: dict, *,
                 first_provider: str, second_provider: str) -> str | None:
    """Return a two-family agreement; conflicts and non-track verdicts stay unresolved."""
    if first_provider == second_provider:
        raise ValueError("specialty reviews must come from different provider families")
    check_specialty_review(first, indexed_source)
    check_specialty_review(second, indexed_source)
    if first["proposed_track"] == second["proposed_track"] and first["proposed_track"] in {
        "psychiatry", "neurology", "mixed",
    }:
        return first["proposed_track"]
    return None
