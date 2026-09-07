"""Classify an article's licence, so the released dataset only contains redistributable text.

This is stricter than a substring check on purpose. "cc-by" is a substring of "cc-by-nc-nd", so a
naive match would quietly wave through the most restricted licences in the corpus — and a benchmark
that cannot be redistributed is a benchmark nobody can check.
"""

from __future__ import annotations

import re

# Ordered most specific first: "by-nc-nd" must be tested before "by-nc" and "by".
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("cc0", re.compile(r"publicdomain/zero|\bcc0\b|creativecommons\.org/publicdomain")),
    ("cc-by-nc-nd", re.compile(r"by[-_ ]?nc[-_ ]?nd|ccbyncnd")),
    ("cc-by-nc-sa", re.compile(r"by[-_ ]?nc[-_ ]?sa|ccbyncsa")),
    ("cc-by-nc", re.compile(r"by[-_ ]?nc\b|ccbync")),
    ("cc-by-nd", re.compile(r"by[-_ ]?nd\b|ccbynd")),
    ("cc-by-sa", re.compile(r"by[-_ ]?sa\b|ccbysa")),
    ("cc-by", re.compile(r"licenses/by/|\bcc[-_ ]?by\b|ccbylicense|\bccby\b")),
]

# Permit redistribution of the dataset and of text derived from it, with attribution.
REDISTRIBUTABLE = frozenset({"cc0", "cc-by", "cc-by-sa"})

# Redistributable but only for non-commercial use. Usable if the dataset itself is released
# non-commercially; kept separate so that choice is explicit rather than accidental.
NONCOMMERCIAL = frozenset({"cc-by-nc", "cc-by-nc-sa"})

# No-derivatives licences. A derived dataset of extracted spans is a derivative work, so these
# cannot be included at all.
NO_DERIVATIVES = frozenset({"cc-by-nd", "cc-by-nc-nd"})


def classify(license_text: str | None) -> str:
    """Map a licence URL, attribute, or content-type to a short code, or "unknown"."""
    if not license_text:
        return "unknown"
    lowered = license_text.strip().lower()
    for code, pattern in _PATTERNS:
        if pattern.search(lowered):
            return code
    return "unknown"


def is_allowed(license_text: str | None, *, allow_noncommercial: bool = False) -> bool:
    code = classify(license_text)
    if code in NO_DERIVATIVES or code == "unknown":
        return False
    if code in NONCOMMERCIAL:
        return allow_noncommercial
    return code in REDISTRIBUTABLE
