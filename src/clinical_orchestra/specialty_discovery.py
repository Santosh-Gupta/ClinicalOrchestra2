"""Prespecified PMC discovery routes for the psychiatry/neurology benchmark tracks.

These queries find candidates. They do not assign a clinical specialty or certify a case report.
PMC currently translates ``case reports[Publication Type]`` to an all-fields search, so every
retrieved article needs a separate article-type and clinical-content audit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .licensing import is_allowed


JOURNALS = (
    "BMC Neurology",
    "BMC Psychiatry",
    "BJPsych Open",
    "Frontiers in Neurology",
    "Frontiers in Psychiatry",
    "Journal of Medical Case Reports",
    "BMJ Case Reports",
    "Clinical Case Reports",
    "Oxford Medical Case Reports",
)

PSYCHIATRY_JOURNALS = ("BMC Psychiatry", "BJPsych Open", "Frontiers in Psychiatry")
NEUROLOGY_JOURNALS = ("BMC Neurology", "Frontiers in Neurology")

PSYCHIATRY_TERMS = (
    "psychiatr*", "psychosis", "psychotic", "depression", "mania", "catatonia",
    "hallucination*", "delusion*", "schizophrenia", "suicid*", "anxiety",
)
NEUROLOGY_TERMS = (
    "neurolog*", "seizure*", "epilepsy", "encephalitis", "dementia",
    "Parkinson*", "stroke", "brain", "neuropath*", "movement disorder*",
)
BRIDGE_TERMS = (
    "neuropsychiatr*", "functional neurological", "anti-NMDA",
    "psychogenic nonepileptic", "psychogenic non-epileptic", "autoimmune psychosis",
    "postictal psychosis", "ictal psychosis", "neurobehavioral",
)
EXCLUDED_JATS_TYPES = frozenset({
    "abstract", "correction", "editorial", "letter", "methods-article", "retraction",
    "review-article", "systematic-review", "protocol", "commentary",
})


@dataclass(frozen=True)
class DiscoveryWindow:
    name: str
    date_from: str
    date_to: str


WINDOWS = (
    DiscoveryWindow("development_candidate", "2024/01/01", "2025/12/31"),
    DiscoveryWindow("temporal_test_candidate", "2026/07/01", "2026/10/16"),
)


def _journal_clause(journals: tuple[str, ...]) -> str:
    return "(" + " OR ".join(f'"{name}"[ta]' for name in journals) + ")"


def _terms_clause(terms: tuple[str, ...]) -> str:
    return "(" + " OR ".join(f'"{term}"[tiab]' for term in terms) + ")"


def discovery_queries(window: DiscoveryWindow) -> dict[str, str]:
    """Build routes before seeing any model output or article-level clinical labels."""
    base = " AND ".join((
        '"case reports"[Publication Type]',
        "open access[filter]",
        f'("{window.date_from}"[Publication Date] : "{window.date_to}"[Publication Date])',
        _journal_clause(JOURNALS),
    ))
    return {
        "frame_reference": base,
        "mixed_dual_facet": base + " AND " + _terms_clause(PSYCHIATRY_TERMS)
        + " AND " + _terms_clause(NEUROLOGY_TERMS),
        "mixed_bridge": base + " AND " + _terms_clause(BRIDGE_TERMS),
        "psychiatry_reference": base + " AND " + _journal_clause(PSYCHIATRY_JOURNALS),
        "neurology_reference": base + " AND " + _journal_clause(NEUROLOGY_JOURNALS),
    }


def stable_sample(pmcids: list[str], limit: int, seed: str) -> list[str]:
    if limit < 0:
        raise ValueError("sample limit must be non-negative")
    unique = set(pmcids)
    ranked = sorted(
        unique,
        key=lambda pmcid: (hashlib.sha256(f"{seed}:{pmcid}".encode()).hexdigest(), pmcid),
    )
    return ranked[:limit]


def case_report_signal(article_type: str | None, title: str | None) -> bool:
    """A recall aid only: neither JATS type nor title proves single-patient suitability."""
    if (article_type or "").lower() in {"case-report", "case-study"}:
        return True
    normalized_title = (title or "").casefold()
    return "case report" in normalized_title or "case study" in normalized_title


def preliminary_status(
    *, journal: str | None, license_text: str | None, article_type: str | None,
    title: str | None,
) -> str:
    """Conservative metadata gate; surviving records still need article and clinical audits."""
    if (journal or "").casefold() not in {name.casefold() for name in JOURNALS}:
        return "journal_mismatch"
    if not is_allowed(license_text):
        return "license_excluded"
    if (article_type or "").lower() in EXCLUDED_JATS_TYPES:
        return "non_case_article_type"
    if not case_report_signal(article_type, title):
        return "case_type_unverified"
    return "pending_article_and_clinical_audit"
