#!/usr/bin/env python3.11
"""Say whether DeepSeek is currently billing at peak rates, and show the day's schedule.

Usage:
  PYTHONPATH=src python3.11 scripts/peak_check.py [--tz America/Los_Angeles]
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from clinical_orchestra.peak import describe, is_peak


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tz", default="America/Los_Angeles", help="local zone for the schedule")
    args = parser.parse_args()
    local = ZoneInfo(args.tz)

    print(describe())
    print(f"\nnext 24h, in UTC and {args.tz}:")
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    runs: list[tuple[datetime, datetime, bool]] = []
    for step in range(24):
        hour = now + timedelta(hours=step)
        peak = is_peak(hour)
        if runs and runs[-1][2] == peak:
            runs[-1] = (runs[-1][0], hour + timedelta(hours=1), peak)
        else:
            runs.append((hour, hour + timedelta(hours=1), peak))
    for start, end, peak in runs:
        label = "PEAK  x2" if peak else "off-peak"
        print(
            f"  {label}  {start:%a %H:%M}-{end:%H:%M} UTC   "
            f"({start.astimezone(local):%a %H:%M}-{end.astimezone(local):%H:%M} local)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
