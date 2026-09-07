#!/usr/bin/env python3.11
"""Fetch open-access case reports from PMC and cache their full text.

Selection is by objective criteria only — publication window, article type, licence, and length.
No model sees a case before it is cached, so case selection cannot be conditioned on any model's
behaviour. (v1 built its hard set from one model's failures, which made scoring that model on it
circular.)

Usage:
  export SSL_CERT_FILE=$(python3.11 -c "import certifi;print(certifi.where())")
  PYTHONPATH=src python3.11 scripts/fetch_cases.py --from 2026/06/01 --limit 20 \\
      --query "neurology" --out data/cases
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clinical_orchestra.licensing import classify, is_allowed
from clinical_orchestra.ncbi import NcbiClient, NcbiConfig
from clinical_orchestra.pmc import fetch_pmc_articles, search_pmcids

# Sections that describe the workup. The reference list and author declarations are dropped: they
# add nothing and they cost tokens on every extraction call.
SKIP_SECTION_TITLES = (
    "references",
    "acknowledg",
    "conflict",
    "competing interest",
    "funding",
    "author contribution",
    "supplementary",
    "consent",
    "abbreviation",
)


def case_text(article) -> str:
    parts = []
    for section in article.sections:
        title = (section.title or "").strip()
        if any(skip in title.lower() for skip in SKIP_SECTION_TITLES):
            continue
        if title:
            parts.append(f"## {title}")
        parts.append(section.text.strip())
    return "\n\n".join(part for part in parts if part).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="", help="extra search terms, e.g. a specialty")
    parser.add_argument(
        "--from", dest="date_from", required=True, help="earliest publication date, YYYY/MM/DD"
    )
    parser.add_argument("--to", dest="date_to", default="3000", help="latest publication date")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--min-chars", type=int, default=3000, help="skip cases shorter than this")
    parser.add_argument("--max-chars", type=int, default=60000)
    parser.add_argument("--out", default="data/cases")
    parser.add_argument("--email", default=None, help="contact email for NCBI, as they request")
    parser.add_argument(
        "--allow-noncommercial",
        action="store_true",
        help="also keep CC BY-NC cases (only if the dataset itself is released non-commercially)",
    )
    args = parser.parse_args()

    # "open access[filter]" restricts to the OA subset; the licence check below is still applied,
    # because the OA subset includes non-commercial licences too.
    terms = [
        '"case reports"[Publication Type]',
        "open access[filter]",
        f'("{args.date_from}"[Publication Date] : "{args.date_to}"[Publication Date])',
    ]
    if args.query:
        terms.append(f"({args.query})")
    query = " AND ".join(terms)

    client = NcbiClient(NcbiConfig(email=args.email))
    print(f"query: {query}")
    # Sorted by date so the corpus grows forward in time as new cases are published, which is what
    # keeps the post-cutoff test split replenishable.
    pmcids, total, _ = search_pmcids(client, query, limit=args.limit, sort="pub_date")
    print(f"{total} matches, fetching {len(pmcids)}")
    if not pmcids:
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    kept = 0
    rejected: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejected[reason] = rejected.get(reason, 0) + 1

    for article in fetch_pmc_articles(client, pmcids):
        licence_code = classify(article.license_type)
        if not is_allowed(article.license_type, allow_noncommercial=args.allow_noncommercial):
            reject(f"licence:{licence_code}")
            continue
        text = case_text(article)
        if len(text) < args.min_chars:
            reject("too_short")
            continue
        if len(text) > args.max_chars:
            reject("too_long")
            continue
        record = {
            "case_id": article.pmcid,
            "source": {
                "pmcid": article.pmcid,
                "doi": article.doi,
                "title": article.title,
                "license": article.license_type,
                "license_code": licence_code,
                "publication_year": article.publication_year,
                "url": article.url,
            },
            "case_text": text,
            "n_chars": len(text),
        }
        (out_dir / f"{article.pmcid}.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        kept += 1

    print(f"kept {kept} cases in {out_dir}")
    if rejected:
        print("rejected:")
        for reason, count in sorted(rejected.items(), key=lambda item: -item[1]):
            print(f"  {count:3d}  {reason}")
    return 0 if kept else 1


if __name__ == "__main__":
    sys.exit(main())
