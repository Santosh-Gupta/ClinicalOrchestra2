#!/usr/bin/env python3.11
"""Plan or run two-family specialty intake review on prepared development case records.

The output is provisional case classification, not benchmark inputs/outputs. Source rights,
article type and first-public-date evidence must be checked upstream; --live is explicit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clinical_orchestra.construction.api import DeferredRequest, StageSession, models_from_file, readiness
from clinical_orchestra.construction.evidence import digest, indexed_source
from clinical_orchestra.construction.prompts import prompt_text
from clinical_orchestra.construction.schemas import ContractError
from clinical_orchestra.construction.specialty import agreed_track, check_specialty_review
from clinical_orchestra.ledger import RunLedger
from clinical_orchestra.licensing import is_allowed

ROOT = Path(__file__).resolve().parents[1]


def prepared_source(record: dict) -> dict:
    source = indexed_source(record)
    if record["split"] != "development":
        raise ValueError("specialty-review pilot accepts development cases only")
    metadata = record["source"]
    required = (
        "license", "license_evidence_url", "article_type_evidence_url",
        "first_public_date", "first_public_date_evidence_url",
    )
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in required):
        raise ValueError("prepared source lacks article-level rights/type/first-public-date evidence")
    if not is_allowed(metadata["license"]):
        raise ValueError("prepared source license is not eligible for public derivative dataset")
    return source


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "construction_models.toml")
    parser.add_argument("--models", nargs=2, metavar=("FIRST", "SECOND"), required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--max-requests", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=7000)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/specialty_review")
    parser.add_argument("--cache", type=Path, default=ROOT / "runs/specialty_review_cache")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if min(args.limit, args.max_requests, args.max_tokens) <= 0:
        parser.error("limits must be positive")
    by_key = {model.key: model for model in models_from_file(args.registry)}
    if any(key not in by_key for key in args.models) or len(set(args.models)) != 2:
        parser.error("select two distinct known model keys")
    models = [by_key[key] for key in args.models]
    if models[0].provider == models[1].provider:
        parser.error("select two different provider families")
    paths = sorted(args.cases.glob("*.json"))
    if not paths:
        parser.error("no prepared JSON cases found")
    try:
        sources = [prepared_source(json.loads(path.read_text())) for path in paths]
    except (ValueError, ContractError, KeyError) as exc:
        parser.error(str(exc))
    groups = {}
    ids = set()
    for source in sources:
        if source["case_id"] in ids:
            parser.error("duplicate case ID")
        ids.add(source["case_id"])
        if source["case_group"] in groups and groups[source["case_group"]] != source["source_hash"]:
            parser.error("multiple reports in one group need a patient-specific source audit")
        groups[source["case_group"]] = source["source_hash"]
    sources = sources[:args.limit]
    report = {
        "mode": "live" if args.live else "plan",
        "cases": len(sources),
        "models": [readiness(model) for model in models],
        "planned_calls": 2 * len(sources),
        "max_http_attempts": args.max_requests,
        "note": "Agreement is provisional and does not verify semantic/temporal correctness.",
    }
    print(json.dumps(report, indent=2))
    if not args.live:
        return 0
    if any(not item["ready"] for item in report["models"]):
        parser.error("selected models are not ready; no fallback")
    config = {**report, "model_config": [model.public_config() for model in models],
              "prompt_hash": digest(prompt_text("specialty")),
              "source_hashes": [source["source_hash"] for source in sources],
              "max_tokens": args.max_tokens}
    ledger = RunLedger.create(out_dir=args.out, mode="specialty_review", config=config)
    session = StageSession(ledger, cache_dir=args.cache, max_requests=args.max_requests,
                           max_tokens=args.max_tokens, namespace="specialty-review-v1")
    provisional = 0
    try:
        for source in sources:
            case_id = source["case_id"]
            ledger.append("cases", {"case_id": case_id, "case_group": source["case_group"],
                                    "source_hash": source["source_hash"], "source": source["source"]})
            reviews = []
            for model in models:
                try:
                    review = check_specialty_review(
                        session.call(model, "specialty", {"spans": source["spans"]}), source
                    )
                except ContractError as exc:
                    ledger.append("invalid_reviews", {"case_id": case_id, "model": model.key,
                                                      "reason": str(exc)})
                    reviews = []
                    break
                ledger.append("reviews", {"case_id": case_id, "model": model.key, "review": review})
                reviews.append(review)
            track = (agreed_track(reviews[0], reviews[1], source,
                                  first_provider=models[0].provider,
                                  second_provider=models[1].provider)
                     if len(reviews) == 2 else None)
            if track:
                provisional += 1
            ledger.append("decisions", {"case_id": case_id, "case_group": source["case_group"],
                                        "status": "provisional_agreement" if track else "unresolved",
                                        "track": track})
    except Exception as exc:
        status = "deferred" if isinstance(exc, DeferredRequest) else "failed"
        ledger.finish(status=status, error_type=type(exc).__name__,
                      http_requests=session.http_requests, cache_hits=session.cache_hits)
        print(f"{status}: {type(exc).__name__}. Inspect {ledger.run_dir}", file=sys.stderr)
        return 75 if status == "deferred" else 1
    ledger.finish(status="completed", provisional_agreements=provisional,
                  cases=len(sources), http_requests=session.http_requests,
                  cache_hits=session.cache_hits)
    print(f"completed: {ledger.run_dir}; provisional agreements {provisional}/{len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
