#!/usr/bin/env python3.11
"""Extract validated timelines from cached cases.

Every event the model produces must quote the source, and every quote is checked against the source
text before the case is accepted. Rejected cases are written out with the reason, so the failure
modes are visible rather than being silently absent from the dataset.

Usage:
  export SSL_CERT_FILE=$(python3.11 -c "import certifi;print(certifi.where())")
  source <env file with the XM_* keys>
  PYTHONPATH=src python3.11 scripts/build_timelines.py --model gemini-3.5-flash --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from clinical_orchestra.extract import EXTRACTION_SYSTEM_PROMPT, extract_timeline
from clinical_orchestra.ledger import RunLedger
from clinical_orchestra.registry import build_client, load_registry, select


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="registry key of the extraction model")
    parser.add_argument("--cases", default="data/cases")
    parser.add_argument("--out", default="data/timelines")
    parser.add_argument("--runs", default="runs/extraction")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    specs = select(load_registry(), keys=[args.model], require_key=False)
    if not specs:
        print(f"unknown model {args.model!r}", file=sys.stderr)
        return 1
    spec = specs[0]
    client = build_client(spec, system_prompt=EXTRACTION_SYSTEM_PROMPT, timeout_seconds=300.0)

    case_paths = sorted(Path(args.cases).glob("*.json"))
    if args.limit:
        case_paths = case_paths[: args.limit]
    if not case_paths:
        print(f"no cases in {args.cases}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ledger = RunLedger.create(
        out_dir=args.runs,
        mode="extraction",
        config={
            "extraction_model": spec.key,
            "model_id": spec.model_id,
            "temperature": 0.0,
            "n_cases": len(case_paths),
            "cases_dir": str(args.cases),
        },
    )

    accepted = 0
    for path in case_paths:
        record = json.loads(path.read_text())
        case_id = record["case_id"]
        print(f"  {case_id} ({record['n_chars']} chars) ...", end=" ", flush=True)
        try:
            outcome = extract_timeline(
                client=client,
                case_id=case_id,
                case_text=record["case_text"],
                source=record["source"],
            )
        except Exception as exc:  # noqa: BLE001 - record the failure, keep going
            print(f"ERROR {type(exc).__name__}: {exc}")
            ledger.append(
                "rejected", {"case_id": case_id, "reason": f"{type(exc).__name__}: {exc}"}
            )
            continue

        n_events = len(outcome.timeline.events) if outcome.timeline else 0
        if outcome.accepted and outcome.timeline:
            (out_dir / f"{case_id}.json").write_text(
                json.dumps(outcome.timeline.to_dict(), indent=2) + "\n", encoding="utf-8"
            )
            accepted += 1
            print(f"ok {n_events} events, {len(outcome.dropped_events)} dropped")
            ledger.append(
                "accepted",
                {
                    "case_id": case_id,
                    "n_events": n_events,
                    "n_dropped": len(outcome.dropped_events),
                },
            )
        else:
            print(f"REJECTED ({outcome.reason})")
            ledger.append(
                "rejected",
                {
                    "case_id": case_id,
                    "reason": outcome.reason,
                    "n_events": n_events,
                    "dropped": outcome.dropped_events,
                    "violations": [
                        {"index": v.event_index, "code": v.code, "message": v.message}
                        for v in outcome.violations
                    ],
                },
            )

    ledger.finish(accepted=accepted, rejected=len(case_paths) - accepted)
    print(f"\naccepted {accepted}/{len(case_paths)} -> {out_dir}")
    print(f"run log: {ledger.run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
