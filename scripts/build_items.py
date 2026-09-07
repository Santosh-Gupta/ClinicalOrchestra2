#!/usr/bin/env python3.11
"""Turn validated timelines into benchmark items.

Usage:
  PYTHONPATH=src python3.11 scripts/build_items.py --timelines data/timelines --out data/items.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from clinical_orchestra.events import CaseTimeline, Event
from clinical_orchestra.items import build_items


def load_timeline(path: Path) -> CaseTimeline:
    payload = json.loads(path.read_text())
    return CaseTimeline(
        case_id=payload["case_id"],
        source=payload["source"],
        presentation=payload["presentation"],
        events=[Event(**event) for event in payload["events"]],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timelines", default="data/timelines")
    parser.add_argument("--out", default="data/items.jsonl")
    args = parser.parse_args()

    paths = sorted(Path(args.timelines).glob("*.json"))
    if not paths:
        print(f"no timelines in {args.timelines}", file=sys.stderr)
        return 1

    items = []
    for path in paths:
        items.extend(build_items(load_timeline(path)))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")

    flagged = Counter(flag for item in items for flag in item.flags)
    by_type = Counter(item.type for item in items)
    by_case = Counter(item.case_id for item in items)
    print(f"{len(items)} items from {len(paths)} cases -> {out_path}")
    print("\nby type:")
    for item_type, count in by_type.most_common():
        print(f"  {count:4d}  {item_type}")
    if flagged:
        print("\nflagged (not errors, but not gradable as a single answer):")
        for flag, count in flagged.most_common():
            print(f"  {count:4d}  {flag}")
    print(f"\nitems per case: min {min(by_case.values())}, max {max(by_case.values())}, "
          f"mean {sum(by_case.values())/len(by_case):.1f}")
    print("\nNOTE: items within a case are not independent. Cluster by case for any interval "
          "or significance test — the effective sample size is closer to the case count.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
