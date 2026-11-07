"""Negative controls for the observed-only interactive case contract."""

import unittest
from dataclasses import replace

from clinical_orchestra.interactive import (
    DOCUMENTED,
    NOT_AVAILABLE,
    NOT_DOCUMENTED,
    CasePack,
    EvidenceCard,
    resolve_request,
    validate_pack,
)


SOURCE = (
    "A patient arrived with a persistent headache and fever. "
    "Lumbar puncture showed clear fluid with no cells. "
    "Two days later, the patient developed a rash."
)
MENU = ("ask_fever", "order_lp", "order_mri", "ask_rash")
CARD = EvidenceCard(
    card_id="lp_result",
    request_id="order_lp",
    status=DOCUMENTED,
    answer="Clear fluid with no cells.",
    source_span="Lumbar puncture showed clear fluid with no cells.",
    source_location="case presentation, paragraph 2",
    clinical_time="at admission",
    known_phase="after lumbar puncture",
    stability_reason="same encounter before intervention",
)
LATER = EvidenceCard(
    card_id="later_rash",
    request_id="ask_rash",
    status=NOT_AVAILABLE,
    answer="",
    source_span="Two days later, the patient developed a rash.",
    source_location="case presentation, paragraph 3",
    clinical_time="two days later",
    known_phase="later encounter",
)
PACK = CasePack(
    case_id="synthetic-1",
    presentation="A patient has headache and fever.",
    presentation_spans=("A patient arrived with a persistent headache and fever.",),
    anchor_phase="admission",
    cards=(CARD, LATER),
    option_ids=("dx_a", "dx_b"),
    gold_option_id="dx_a",
)


class InteractivePackTests(unittest.TestCase):
    def test_documented_absent_and_future_requests_are_distinct(self):
        validate_pack(PACK, SOURCE, MENU)
        observed = resolve_request(PACK, "order_lp", MENU)
        self.assertEqual((observed.status, observed.answer, observed.card_id),
                         (DOCUMENTED, "Clear fluid with no cells.", "lp_result"))
        absent = resolve_request(PACK, "order_mri", MENU)
        self.assertEqual((absent.status, absent.answer, absent.card_id),
                         (NOT_DOCUMENTED, "", None))
        later = resolve_request(PACK, "ask_rash", MENU)
        self.assertEqual((later.status, later.answer), (NOT_AVAILABLE, ""))
        self.assertEqual(resolve_request(PACK, "order_lp", MENU), observed)

    def test_rejects_unlisted_request(self):
        with self.assertRaises(ValueError):
            resolve_request(PACK, "reveal_diagnosis", MENU)

    def test_rejects_ungrounded_card_and_presentation(self):
        with self.assertRaisesRegex(ValueError, "evidence card quote"):
            validate_pack(replace(PACK, cards=(replace(CARD, source_span="Invented MRI lesion"),)), SOURCE, MENU)
        with self.assertRaisesRegex(ValueError, "presentation quote"):
            validate_pack(replace(PACK, presentation_spans=("Invented fever history",)), SOURCE, MENU)

    def test_rejects_answer_on_unavailable_card(self):
        with self.assertRaisesRegex(ValueError, "must not expose"):
            validate_pack(replace(PACK, cards=(replace(LATER, answer="Rash"),)), SOURCE, MENU)

    def test_rejects_duplicate_request_and_bad_gold(self):
        with self.assertRaisesRegex(ValueError, "unique menu request"):
            validate_pack(replace(PACK, cards=(CARD, replace(LATER, request_id="order_lp"))), SOURCE, MENU)
        with self.assertRaisesRegex(ValueError, "terminal gold"):
            validate_pack(replace(PACK, gold_option_id="dx_hidden"), SOURCE, MENU)


if __name__ == "__main__":
    unittest.main()
