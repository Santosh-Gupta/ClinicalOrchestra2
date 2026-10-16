#!/usr/bin/env python3.11
"""Build a reproducible *candidate* ledger for three specialty benchmark tracks.

This script does not construct inputs/outputs or label mixed cases. It searches a prespecified
journal frame, oversamples dual-domain signals, samples specialty reference routes by stable hash,
and records every search hit and selected article's preliminary rights/type status.

Usage:
  SSL_CERT_FILE=$(python3.11 -c 'import certifi; print(certifi.where())') \
  PYTHONPATH=src python3.11 scripts/discover_specialty_cases.py \
      --email you@example.com --out data/discovery/specialty_candidates_2026-10-16.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from clinical_orchestra.licensing import classify
from clinical_orchestra.ncbi import NcbiClient, NcbiConfig
from clinical_orchestra.pmc import fetch_pmc_articles, search_pmcids
from clinical_orchestra.specialty_discovery import (
    JOURNALS, WINDOWS, case_report_signal, discovery_queries, preliminary_status, stable_sample,
)


def discover(client: NcbiClient, *, reference_per_window: int, seed: str) -> dict:
    if reference_per_window < 0:
        raise ValueError("reference_per_window must be non-negative")
    query_log: list[dict] = []
    selected_routes: dict[str, set[str]] = defaultdict(set)
    selected_windows: dict[str, set[str]] = defaultdict(set)

    for window in WINDOWS:
        for route, query in discovery_queries(window).items():
            pmcids, total, translation = search_pmcids(
                client, query, limit=10_000, sort="pub_date"
            )
            if total > len(pmcids):
                raise RuntimeError(
                    f"PMC returned {len(pmcids)} of {total} hits for {window.name}/{route}; "
                    "split the date window before building a truncated ledger"
                )
            if route.endswith("_reference"):
                chosen = stable_sample(pmcids, reference_per_window, seed + ":" + window.name + ":" + route)
            else:
                chosen = sorted(set(pmcids))
            query_log.append({
                "window": window.name,
                "date_from": window.date_from,
                "date_to": window.date_to,
                "route": route,
                "query": query,
                "query_translation": translation,
                "hit_count": total,
                "hit_pmcids": pmcids,
                "selected_pmcids": chosen,
            })
            for pmcid in chosen:
                selected_routes[pmcid].add(route)
                selected_windows[pmcid].add(window.name)

    all_ids = sorted(selected_routes)
    articles = {}
    for start in range(0, len(all_ids), 20):
        batch = all_ids[start:start + 20]
        for article in fetch_pmc_articles(client, batch):
            if article.pmcid not in batch:
                raise RuntimeError(f"Unexpected PMCID in EFetch: {article.pmcid}")
            articles[article.pmcid] = article

    candidates: list[dict] = []
    reasons = Counter()
    for pmcid in all_ids:
        article = articles.get(pmcid)
        routes = sorted(selected_routes[pmcid])
        windows = sorted(selected_windows[pmcid])
        if article is None:
            reasons["efetch_missing"] += 1
            candidates.append({
                "pmcid": pmcid, "routes": routes, "windows": windows,
                "status": "efetch_missing",
            })
            continue
        license_code = classify(article.license_type)
        type_signal = case_report_signal(article.article_type, article.title)
        status = preliminary_status(
            journal=article.journal,
            license_text=article.license_type,
            article_type=article.article_type,
            title=article.title,
        )
        reasons[status] += 1
        candidates.append({
            "pmcid": pmcid,
            "pmid": article.pmid,
            "doi": article.doi,
            "title": article.title,
            "journal": article.journal,
            "article_type_jats": article.article_type,
            "case_report_signal": type_signal,
            "license_jats": article.license_type,
            "license_code": license_code,
            "publication_year_jats": article.publication_year,
            "first_public_date_status": "unverified",
            "url": article.url,
            "routes": routes,
            "windows": windows,
            "status": status,
        })

    return {
        "schema_version": "specialty-discovery-v1",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "reference_per_window": reference_per_window,
        "journal_frame": list(JOURNALS),
        "search_caveat": (
            "PMC translates case reports[Publication Type] to an all-fields search; "
            "article type and single-patient content require audit."
        ),
        "queries": query_log,
        "candidates": candidates,
        "summary": {
            "selected_unique": len(all_ids),
            "retrieved_articles": len(articles),
            "status_counts": dict(sorted(reasons.items())),
            "mixed_route_selected": sum(
                any(route.startswith("mixed_") for route in selected_routes[pmcid])
                for pmcid in all_ids
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="contact address NCBI requests for automated access")
    parser.add_argument("--reference-per-window", type=int, default=100)
    parser.add_argument("--seed", default="clinical-orchestra-specialty-v1")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    client = NcbiClient(NcbiConfig(email=args.email))
    result = discover(client, reference_per_window=args.reference_per_window, seed=args.seed)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite discovery ledger: {path}")
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(path), **result["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
