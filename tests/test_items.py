"""Tests for item construction and the grading rules.

These run with no model in the loop. The grading rules are the part of the benchmark most likely to
be quietly wrong, and the two failure modes they guard against — crediting something already in the
prompt, and letting one answer collect credit across a whole case — are both easy to reintroduce.
"""

import unittest

from clinical_orchestra.events import ACTION, DIAGNOSIS, RESULT, CaseTimeline, Event
from clinical_orchestra.items import (
    CORRECT,
    LATER_MAX,
    answer_field,
    build_items,
    credit_for,
    later_credit,
    ndcg,
)


def timeline() -> CaseTimeline:
    events = [
        Event(0, ACTION, "complete blood count", "CBC", "span0" * 4),
        Event(1, RESULT, "CBC result", "leukocytosis", "span1" * 4, action_index=0),
        Event(2, ACTION, "brain MRI", "MRI with contrast", "span2" * 4),
        Event(3, RESULT, "MRI result", "temporal hyperintensity", "span3" * 4, action_index=2),
        Event(4, ACTION, "lumbar puncture", "LP", "span4" * 4),
        Event(5, ACTION, "anti-NMDAR antibody testing", "serum and CSF", "span5" * 4),
        Event(6, DIAGNOSIS, "anti-NMDAR encephalitis", "confirmed", "span6" * 4),
    ]
    return CaseTimeline(case_id="CASE1", source={}, presentation="A 24-year-old woman.", events=events)


class TestItemConstruction(unittest.TestCase):
    def setUp(self):
        self.items = build_items(timeline(), min_warmup=2)

    def test_warmup_events_produce_no_items(self):
        self.assertTrue(all(item.cut_index >= 2 for item in self.items))

    def test_state_stops_at_the_cut(self):
        item = next(i for i in self.items if i.cut_index == 4)
        self.assertIn("brain MRI", item.state)
        # Nothing at or after the cut may appear in the state.
        self.assertNotIn("lumbar puncture", item.state)
        self.assertNotIn("anti-NMDAR", item.state)

    def test_result_items_are_graded_on_the_finding_not_the_label(self):
        item = next(i for i in self.items if i.type == RESULT)
        self.assertEqual(item.gold.answer, "temporal hyperintensity")
        self.assertNotEqual(item.gold.answer, item.gold.summary)

    def test_action_items_are_graded_on_the_name(self):
        item = next(i for i in self.items if i.type == ACTION)
        self.assertEqual(item.gold.answer, item.gold.summary)

    def test_bundled_actions_are_flagged(self):
        events = list(timeline().events)
        events[4] = Event(4, ACTION, "lumbar puncture and EEG", "", "span4" * 4)
        flagged = build_items(
            CaseTimeline(case_id="C", source={}, presentation="p", events=events), min_warmup=2
        )
        item = next(i for i in flagged if i.cut_index == 4)
        self.assertIn("bundled_action", item.flags)


class TestGrading(unittest.TestCase):
    def setUp(self):
        self.items = build_items(timeline(), min_warmup=2)
        self.lp_item = next(i for i in self.items if i.cut_index == 4)

    def test_the_immediate_next_event_scores_full_credit(self):
        self.assertEqual(credit_for(self.lp_item, 4), CORRECT)

    def test_a_later_same_type_event_earns_partial_credit(self):
        credit = credit_for(self.lp_item, 5)  # the next action after the gold
        self.assertGreater(credit, 0.0)
        self.assertLessEqual(credit, LATER_MAX)

    def test_partial_credit_is_capped_well_below_correct(self):
        self.assertLess(LATER_MAX, CORRECT / 2)
        self.assertLess(later_credit(1), CORRECT)
        self.assertLess(later_credit(5), later_credit(1))

    def test_an_event_already_visible_in_the_state_scores_zero(self):
        # Naming the MRI at cut 4 is repeating the prompt, not predicting.
        self.assertEqual(credit_for(self.lp_item, 2), 0.0)
        self.assertEqual(credit_for(self.lp_item, 0), 0.0)

    def test_a_different_type_earns_nothing_on_an_action_item(self):
        # The anti-gaming rule: answering with the case's final diagnosis at every decision point
        # must not collect partial credit on action items.
        self.assertEqual(credit_for(self.lp_item, 6), 0.0)

    def test_an_answer_outside_the_case_scores_zero(self):
        self.assertEqual(credit_for(self.lp_item, None), 0.0)
        self.assertEqual(credit_for(self.lp_item, 999), 0.0)

    def test_naming_the_final_diagnosis_everywhere_scores_near_nothing(self):
        action_items = [i for i in self.items if i.type == ACTION]
        total = sum(credit_for(item, 6) for item in action_items)
        self.assertEqual(total, 0.0)


class TestNdcg(unittest.TestCase):
    def test_perfect_ranking_scores_one(self):
        self.assertAlmostEqual(ndcg([1.0, 0.3, 0.0]), 1.0)

    def test_reversed_ranking_scores_less(self):
        self.assertLess(ndcg([0.0, 0.3, 1.0]), 1.0)

    def test_all_zero_gains_score_zero(self):
        self.assertEqual(ndcg([0.0, 0.0]), 0.0)


if __name__ == "__main__":
    unittest.main()
