"""CLI defaults to a no-network readiness/plan report; --live is required to dispatch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from ..ledger import RunLedger
from . import VERSION
from .api import DeferredRequest, StageSession, models_from_file, readiness
from .evidence import digest, indexed_source
from .prompts import prompt_text
from .runner import roles_for, run_comparison

ROOT = Path(__file__).resolve().parents[3]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", default=str(ROOT / "construction_models.toml"))
    p.add_argument("--models", nargs="+", help="exact construction registry keys; none are silently skipped")
    p.add_argument("--cases", type=Path, help="directory of JSON records with explicit development/test/synthetic split")
    p.add_argument("--purpose", choices=["development", "test"], default="development")
    p.add_argument("--single", action="store_true", help="first model constructs; other models witness/audit")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true")
    mode.add_argument("--demo", action="store_true", help="synthetic offline end-to-end fixture; never clinical evidence")
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--max-items", type=int, default=6)
    p.add_argument("--max-requests", type=int, default=30, help="HTTP attempts, including retries")
    p.add_argument("--max-tokens", type=int, default=16000)
    p.add_argument("--timeout", type=float, default=300)
    p.add_argument("--trial", default="0", help="change deliberately to request a new stochastic sample")
    p.add_argument("--out", type=Path, default=ROOT / "runs/construction")
    p.add_argument("--cache", type=Path, default=ROOT / "runs/construction_cache")
    args = p.parse_args(argv)
    if min(args.limit, args.max_items, args.max_requests, args.max_tokens, args.timeout) <= 0:
        p.error("limits must be positive")
    all_models = models_from_file(args.registry)
    by_key = {m.key: m for m in all_models}
    if args.models and (len(set(args.models)) != len(args.models) or set(args.models)-set(by_key)):
        p.error("models must be distinct known registry keys")
    models = [by_key[k] for k in args.models] if args.models else all_models
    records, responder = [], None
    if args.demo:
        if args.cases or args.live or args.purpose == "test":
            p.error("demo uses only its built-in synthetic case")
        from .demo import demo_record, demo_responder
        records, responder = [demo_record()], demo_responder
        if not args.models:
            models = [by_key["gemini-3.8-flash"], by_key["muse-spark-1.3"]]
    elif args.cases:
        paths = sorted(args.cases.glob("*.json"))
        if not paths:
            p.error("no JSON case records")
        # Validate all split/group declarations before limit; never repartition by item.
        all_records = [json.loads(path.read_text()) for path in paths]
        groups = {}
        hashes = set()
        case_ids = set()
        for record in all_records:
            source = indexed_source(record)
            if source["case_id"] in case_ids:
                p.error("duplicate case_id in batch")
            case_ids.add(source["case_id"])
            if source["case_group"] in groups and groups[source["case_group"]] != source["split"]:
                p.error("same patient/article group appears in different splits")
            groups[source["case_group"]] = source["split"]
            if source["source_hash"] in hashes:
                p.error("duplicate source text in batch")
            hashes.add(source["source_hash"])
        if any(r["split"] != args.purpose for r in all_records):
            p.error("batch split must match --purpose; separate development and test directories")
        records = all_records[:args.limit]
    sources = [indexed_source(r) for r in records]
    report = {"version": VERSION, "mode": "live" if args.live else "demo" if args.demo else "plan",
              "purpose": args.purpose, "models": [readiness(m) for m in models],
              "case_count": len(sources), "max_items_per_case": args.max_items,
              "planned_base_calls_upper_bound": len(sources) * (1 if args.single else len(models)) * (3 + args.max_items),
              "max_http_attempts": args.max_requests,
              "notes": "No model quality or account availability has been tested by this readiness report."}
    print(json.dumps(report, indent=2))
    if not (args.live or args.demo):
        return 0
    if not sources:
        p.error("--live requires --cases with explicit split declarations")
    if args.purpose == "test" and not args.single:
        p.error("test construction requires --single with preselected roles; model comparison is development-only")
    if args.live:
        unready = [r for r in report["models"] if not r["ready"]]
        if unready:
            p.error("selected models are not ready; see reasons above (no fallback)")
        if args.purpose == "test" and any(m.contributor or "contributor" in m.spec.model_id for m in models):
            p.error("contributor endpoints may not receive unpublished test splits")
    try:
        for index in range(len(models) if not args.single else 1):
            roles_for(models, index)
    except ValueError as exc:
        p.error(str(exc))
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_commit = None
    implementation_files = sorted((ROOT / "src/clinical_orchestra").rglob("*.py"))
    implementation_hash = digest({str(f.relative_to(ROOT)): f.read_text() for f in implementation_files})
    config = {**report, "model_config": [m.public_config() for m in models],
              "implementation_hash": implementation_hash, "compare": not args.single,
              "source_hashes": [s["source_hash"] for s in sources],
              "prompt_hashes": {name: digest(prompt_text(name)) for name in ("system", "extract", "blind", "audit")},
              "max_tokens": args.max_tokens, "timeout_seconds": args.timeout, "trial": args.trial,
              "synthetic": args.demo}
    ledger = RunLedger.create(out_dir=args.out, mode="construction", config=config, git_commit=git_commit)
    for stream in ("inputs", "outputs", "rejected"):
        (ledger.run_dir / f"{stream}.jsonl").touch()
    session = StageSession(ledger, cache_dir=args.cache, max_requests=args.max_requests,
                           max_tokens=args.max_tokens, timeout_seconds=args.timeout, trial=args.trial,
                           responder=responder, namespace="synthetic-demo-" + digest(Path(__file__).with_name("demo.py").read_text()) if args.demo else "live")
    try:
        metrics = run_comparison(sources, models, session, max_items=args.max_items, compare=not args.single)
    except Exception as exc:
        status = "deferred" if isinstance(exc, DeferredRequest) else "failed"
        # Do not print provider error text; transport log already stores redacted response bodies.
        ledger.finish(status=status, error_type=type(exc).__name__, http_requests=session.http_requests,
                      synthetic_requests=session.synthetic_requests, cache_hits=session.cache_hits)
        print(f"{status}: {type(exc).__name__}. Inspect {ledger.run_dir}", file=sys.stderr)
        return 75 if status == "deferred" else 1
    accepted_count = sum(x["accepted_items"] for x in metrics)
    status = "completed" if accepted_count else "completed_no_accepted_items"
    ledger.finish(status=status, http_requests=session.http_requests, cache_hits=session.cache_hits,
                  synthetic_requests=session.synthetic_requests,
                  accepted_items=accepted_count,
                  case_clusters=len({s["case_group"] for s in sources}))
    print(f"{status}: {ledger.run_dir}")
    return 0 if accepted_count else 2
