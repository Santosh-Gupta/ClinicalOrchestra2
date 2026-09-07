"""Whether a DeepSeek request falls in the peak-price window.

DeepSeek moved to time-of-day pricing on 2026-08-16. Peak hours cost exactly double, and the
schedule is a fixed UTC clock — not a load signal and not something the API reports back — so it can
be computed locally and does not need a network call.

Peak: 01:00-04:00 and 06:00-10:00 UTC, Monday to Friday (UTC days).
Off-peak: every other hour, including all of Saturday and Sunday.

That is 35 of the 168 hours in a week, so roughly 79% of the clock is already off-peak. The point of
this module is not to chase the discount but to avoid paying double by accident, and to record which
regime each run actually billed under so a cost figure can be checked later.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Hour-of-day (UTC) ranges, as [start, end) in whole hours.
PEAK_WINDOWS = ((1, 4), (6, 10))
PEAK_WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # Monday..Friday, in UTC
PEAK_MULTIPLIER = 2.0


def is_peak(when: datetime | None = None) -> bool:
    """True when `when` (defaults to now) falls in a DeepSeek peak window."""
    moment = (when or datetime.now(UTC)).astimezone(UTC)
    if moment.weekday() not in PEAK_WEEKDAYS:
        return False
    return any(start <= moment.hour < end for start, end in PEAK_WINDOWS)


def next_change(when: datetime | None = None) -> datetime:
    """When the current peak/off-peak regime next flips, to the hour."""
    moment = (when or datetime.now(UTC)).astimezone(UTC).replace(
        minute=0, second=0, microsecond=0
    )
    current = is_peak(moment)
    for step in range(1, 24 * 8):
        candidate = moment + timedelta(hours=step)
        if is_peak(candidate) != current:
            return candidate
    raise RuntimeError("peak schedule never changes; the windows are misconfigured")


def price_multiplier(when: datetime | None = None) -> float:
    return PEAK_MULTIPLIER if is_peak(when) else 1.0


def describe(when: datetime | None = None) -> str:
    moment = (when or datetime.now(UTC)).astimezone(UTC)
    regime = "PEAK (double price)" if is_peak(moment) else "off-peak"
    change = next_change(moment)
    hours = (change - moment).total_seconds() / 3600
    return (
        f"{moment:%Y-%m-%d %H:%M UTC} ({moment:%A}) is {regime}; "
        f"changes at {change:%Y-%m-%d %H:%M UTC}, in {hours:.1f}h"
    )
