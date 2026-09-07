"""Tests for the DeepSeek peak-window schedule.

The windows are a fixed UTC clock, so they are fully testable without a network call. Getting the
boundaries wrong would silently double the cost of a run, which is exactly the kind of error that
only shows up on an invoice.
"""

import unittest
from datetime import UTC, datetime

from clinical_orchestra.peak import is_peak, next_change, price_multiplier


def utc(year, month, day, hour):
    return datetime(year, month, day, hour, tzinfo=UTC)


class TestPeakWindows(unittest.TestCase):
    def test_weekday_peak_windows(self):
        # 2026-09-08 is a Tuesday.
        self.assertTrue(is_peak(utc(2026, 9, 8, 1)))
        self.assertTrue(is_peak(utc(2026, 9, 8, 3)))
        self.assertTrue(is_peak(utc(2026, 9, 8, 6)))
        self.assertTrue(is_peak(utc(2026, 9, 8, 9)))

    def test_boundaries_are_half_open(self):
        self.assertFalse(is_peak(utc(2026, 9, 8, 0)))  # just before the first window
        self.assertTrue(is_peak(utc(2026, 9, 8, 1)))  # first peak hour
        self.assertFalse(is_peak(utc(2026, 9, 8, 4)))  # 04:00 is off-peak again
        self.assertFalse(is_peak(utc(2026, 9, 8, 5)))  # gap between the windows
        self.assertFalse(is_peak(utc(2026, 9, 8, 10)))  # 10:00 is off-peak again

    def test_weekends_are_never_peak(self):
        for hour in range(24):
            self.assertFalse(is_peak(utc(2026, 9, 12, hour)), f"Saturday {hour}:00")
            self.assertFalse(is_peak(utc(2026, 9, 13, hour)), f"Sunday {hour}:00")

    def test_multiplier_matches_regime(self):
        self.assertEqual(price_multiplier(utc(2026, 9, 8, 2)), 2.0)
        self.assertEqual(price_multiplier(utc(2026, 9, 12, 2)), 1.0)

    def test_next_change_finds_the_flip(self):
        self.assertEqual(next_change(utc(2026, 9, 8, 0)), utc(2026, 9, 8, 1))
        self.assertEqual(next_change(utc(2026, 9, 8, 1)), utc(2026, 9, 8, 4))
        # From Friday's last peak hour the next flip is the end of that window, not the weekend.
        self.assertEqual(next_change(utc(2026, 9, 11, 9)), utc(2026, 9, 11, 10))

    def test_a_full_week_is_35_peak_hours(self):
        peak_hours = sum(
            is_peak(utc(2026, 9, 7, 0).replace(day=7 + day, hour=hour))
            for day in range(7)
            for hour in range(24)
        )
        self.assertEqual(peak_hours, 35)


if __name__ == "__main__":
    unittest.main()
