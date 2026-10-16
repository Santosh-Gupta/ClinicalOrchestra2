"""Controls for prespecified specialty candidate discovery."""

import unittest

from clinical_orchestra.construction.evidence import indexed_source
from clinical_orchestra.construction.prompts import render
from clinical_orchestra.construction.schemas import ContractError
from clinical_orchestra.construction.specialty import agreed_track, check_specialty_review
from clinical_orchestra.pmc import parse_pmc_xml
from clinical_orchestra.specialty_discovery import (
    DiscoveryWindow, case_report_signal, discovery_queries, preliminary_status, stable_sample,
)
from scripts.review_specialty_cases import prepared_source


class SpecialtyDiscoveryTests(unittest.TestCase):
    def test_queries_include_objective_reference_and_two_mixed_routes(self):
        queries = discovery_queries(DiscoveryWindow("dev", "2024/01/01", "2025/12/31"))
        self.assertEqual(
            set(queries),
            {"frame_reference", "psychiatry_reference", "neurology_reference",
             "mixed_dual_facet", "mixed_bridge"},
        )
        self.assertIn('"2024/01/01"[Publication Date]', queries["frame_reference"])
        self.assertIn('"2025/12/31"[Publication Date]', queries["frame_reference"])
        self.assertIn("[tiab]", queries["mixed_dual_facet"])
        self.assertIn("anti-NMDA", queries["mixed_bridge"])
        self.assertNotIn("psychosis", queries["frame_reference"])

    def test_hash_sample_is_order_independent_and_unique(self):
        ids = ["PMC3", "PMC1", "PMC2", "PMC3"]
        self.assertEqual(stable_sample(ids, 2, "seed"), stable_sample(list(reversed(ids)), 2, "seed"))
        self.assertEqual(len(stable_sample(ids, 3, "seed")), 3)

    def test_jats_type_and_license_gate_do_not_certify_clinical_relevance(self):
        self.assertEqual(
            preliminary_status(
                journal="Frontiers in Psychiatry",
                license_text="https://creativecommons.org/licenses/by/4.0/",
                article_type="systematic-review", title="Case reports in depression",
            ),
            "non_case_article_type",
        )
        self.assertEqual(
            preliminary_status(
                journal="BMC Neurology",
                license_text="https://creativecommons.org/licenses/by-nc-nd/4.0/",
                article_type="case-report", title="A case report",
            ),
            "license_excluded",
        )
        self.assertEqual(
            preliminary_status(
                journal="Frontiers in Psychiatry",
                license_text="https://creativecommons.org/licenses/by/4.0/",
                article_type="case-report", title="A case report",
            ),
            "pending_article_and_clinical_audit",
        )
        self.assertFalse(case_report_signal("research-article", "Psychosis and epilepsy"))

    def test_pmc_parser_preserves_jats_article_type(self):
        xml = """<article article-type="case-report"><front><article-meta>
        <article-id pub-id-type="pmc">123</article-id>
        <title-group><article-title>Case report</article-title></title-group>
        </article-meta></front><body><sec><p>Clinical course.</p></sec></body></article>"""
        article, = parse_pmc_xml(xml)
        self.assertEqual(article.pmcid, "PMC123")
        self.assertEqual(article.article_type, "case-report")

    def test_mixed_review_requires_source_quotes_and_both_pre_cutoff_domains(self):
        source = indexed_source({
            "case_id": "synthetic", "case_group": "synthetic", "split": "synthetic",
            "source": {},
            "case_text": "The team documented delusions.\n\nThe EEG showed seizures.\n\nTreatment was revised.",
        })
        quote = lambda span_id, value: [{"span_id": span_id, "quote": value}]
        review = {
            "patient_scope": "single",
            "psychiatry": {"material": True, "evidence": quote("p0000", "delusions"), "reason": "Documented symptom"},
            "neurology": {"material": True, "evidence": quote("p0001", "seizures"), "reason": "Documented finding"},
            "interaction": {"material": True, "mechanism": "management",
                            "evidence": quote("p0002", "Treatment was revised"), "reason": "Claimed interaction"},
            "integrated_cutoffs": [{"psychiatric_pre_cutoff": quote("p0000", "delusions"),
                                    "neurological_pre_cutoff": quote("p0001", "seizures"),
                                    "later_target": quote("p0002", "Treatment was revised"),
                                    "reason": "Both clues before target"}],
            "proposed_track": "mixed", "unresolved": [],
        }
        self.assertEqual(agreed_track(review, review, source,
                                      first_provider="one", second_provider="two"), "mixed")
        with self.assertRaises(ValueError):
            agreed_track(review, review, source, first_provider="one", second_provider="one")
        broken = {**review, "integrated_cutoffs": []}
        with self.assertRaises(ContractError):
            check_specialty_review(broken, source)
        broken = {**review, "neurology": {**review["neurology"],
                                         "evidence": quote("p0001", "psychosis")}}
        with self.assertRaises(ContractError):
            check_specialty_review(broken, source)

    def test_specialty_prompt_and_prepared_source_gate(self):
        record = {
            "case_id": "synthetic", "case_group": "synthetic", "split": "development",
            "source": {
                "license": "https://creativecommons.org/licenses/by/4.0/",
                "license_evidence_url": "https://example.invalid/license",
                "article_type_evidence_url": "https://example.invalid/type",
                "first_public_date": "2024-01-01",
                "first_public_date_evidence_url": "https://example.invalid/date",
            },
            "case_text": "The patient was evaluated.",
        }
        source = prepared_source(record)
        rendered = render("specialty", {"spans": source["spans"]})
        self.assertIn("psychiatric_pre_cutoff", rendered["prompt"])
        record["source"]["license"] = "https://creativecommons.org/licenses/by-nc-nd/4.0/"
        with self.assertRaises(ValueError):
            prepared_source(record)


if __name__ == "__main__":
    unittest.main()
