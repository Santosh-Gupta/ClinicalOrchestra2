"""Synthetic negative controls for evidence, temporal leakage, audit gates and resumability."""

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from clinical_orchestra.construction.api import StageSession, models_from_file, strict_json
from clinical_orchestra.construction.cli import main
from clinical_orchestra.construction.compiler import add_options, apply_audit, proposals, visible_state
from clinical_orchestra.construction.demo import demo_graph, demo_record, demo_responder
from clinical_orchestra.construction.evidence import check_graph, indexed_source
from clinical_orchestra.construction.runner import run_comparison
from clinical_orchestra.construction.schemas import ContractError
from clinical_orchestra.ledger import RunLedger

ROOT = Path(__file__).resolve().parents[1]
MODELS = models_from_file(ROOT / "construction_models.toml")[2:]


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class EvidenceAndChronologyTests(unittest.TestCase):
    def setUp(self):
        fixture = ROOT / "tests/fixtures/construction"
        self.source = indexed_source(json.loads((fixture / "case.json").read_text()))
        self.graph = json.loads((fixture / "expected_graph.json").read_text())

    def prepared(self):
        candidates, _ = proposals(self.graph, self.source, "test")
        items = [add_options(i, strict_json(demo_responder(MODELS[0], "blind", i["input"])["content"])) for i in candidates]
        audit = strict_json(demo_responder(MODELS[1], "audit", {"primary": self.graph, "spans": self.source["spans"], "items": items})["content"])
        return items, audit

    def test_late_history_is_physically_early_but_not_early_information(self):
        check_graph(self.graph, self.source)
        self.assertEqual(self.graph["facts"][0]["clinical_after"], ["f5"])
        early, ids = visible_state(self.graph, 3)
        self.assertNotIn("f5", ids)
        self.assertNotIn("two days before admission", early)
        later, ids = visible_state(self.graph, 4)
        self.assertIn("f5", ids)
        self.assertIn("two days before admission", later)

    def test_later_correction_does_not_rewrite_previous_input(self):
        before = visible_state(self.graph, 2)
        correction = deepcopy(self.graph["facts"][2])
        correction.update(id="correction", known_phase="k5", status="corrected", claim="The earlier negative result was corrected to positive.")
        self.graph["facts"].append(correction)
        self.assertEqual(before, visible_state(self.graph, 2))
        self.assertIn("[corrected]", visible_state(self.graph, 5)[0])

    def test_mechanical_checks_reject_damaged_provenance_and_order(self):
        mutations = [
            lambda g: g["facts"][0]["evidence"][0].update(quote="Invented source words."),
            lambda g: g["facts"][5].update(clinical_after=["f0"]),
            lambda g: g["facts"][2].update(linked_action_id="f0"),
            lambda g: g["facts"][0].update(known_phase="missing"),
            lambda g: g["coverage"].pop(),
            lambda g: g["phases"][0].update(rank=True),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                graph = deepcopy(self.graph)
                mutate(graph)
                with self.assertRaises(ContractError):
                    check_graph(graph, self.source)

    def test_ambiguous_phase_link_and_endpoint_are_excluded(self):
        self.graph["facts"][3]["known_phase"] = "k1"
        self.graph["facts"][4]["endpoint"] = None
        _, excluded = proposals(self.graph, self.source, "test")
        reasons = {row["fact_id"]: row["reason"] for row in excluded}
        self.assertEqual(reasons["f1"], "simultaneous_targets_require_bundle_or_narrower_endpoint")
        self.assertEqual(reasons["f3"], reasons["f1"])
        self.assertEqual(reasons["f4"], "no_supported_follow_up_endpoint")
        graph = demo_graph()
        graph["facts"][2]["known_phase"] = "k1"
        _, excluded = proposals(graph, self.source, "test")
        self.assertIn("linked_action_not_known_before_cut", [r["reason"] for r in excluded])

    def test_hidden_ending_and_thesis_do_not_change_compiled_early_input(self):
        original, _ = proposals(self.graph, self.source, "test")
        self.graph["facts"][4]["claim"] = "UNIQUE HIDDEN ENDING"
        self.graph["thesis"] = [{"claim": "UNIQUE HIDDEN THESIS"}]
        source = {**self.source, "source_hash": "different"}
        changed, _ = proposals(self.graph, source, "test")
        self.assertEqual(original[0]["input"], changed[0]["input"])
        self.assertEqual(set(original[0]["input"]), {"item_id", "event_type", "prediction_axis", "context", "question"})
        # This checks the compiler, not whether a full-source LLM changes its extraction.

    def test_true_quote_with_wrong_claim_requires_semantic_rejection(self):
        self.graph["facts"][1]["claim"] = "Appendectomy was performed."
        check_graph(self.graph, self.source)  # Intentionally demonstrates the limit of quote matching.
        items, audit = self.prepared()
        audit["fact_reviews"][1].update(verdict="contradicted", reason="The quote describes an assay order, not surgery.")
        accepted, rejected = apply_audit(self.graph, self.source, items, audit, "test")
        self.assertEqual(accepted, [])
        self.assertEqual(len(rejected), 4)

    def test_audit_must_cover_every_fact_and_every_visible_fact(self):
        for change in (lambda a: a["fact_reviews"].pop(),
                       lambda a: a["item_reviews"][0]["visible_fact_ids_checked"].clear(),
                       lambda a: a["item_reviews"][0].update(answer_id="NONEXISTENT")):
            items, audit = self.prepared()
            change(audit)
            with self.assertRaises(ContractError):
                apply_audit(self.graph, self.source, items, audit, "test")

    def test_unresolved_coverage_blocks_all_items(self):
        items, audit = self.prepared()
        audit["coverage_reviews"][0]["verdict"] = "unknown"
        accepted, rejected = apply_audit(self.graph, self.source, items, audit, "test")
        self.assertFalse(accepted)
        self.assertEqual(len(rejected), len(items))

    def test_alternatives_are_blind_frozen_and_have_residual(self):
        items, _ = self.prepared()
        item = items[0]
        options = item["input"]["options"]
        self.assertIn("OTHER", {o["id"] for o in options})
        original, _ = proposals(self.graph, self.source, "test")
        other, _ = proposals(self.graph, self.source, "other-constructor")
        self.assertEqual(add_options(original[0], item["blind"])["input"]["options"], add_options(other[0], item["blind"])["input"]["options"])
        blind = deepcopy(item["blind"])
        blind["alternatives"][1] = "  " + blind["alternatives"][0].upper()
        with self.assertRaises(ContractError):
            add_options(original[0], blind)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def session(self, responder=demo_responder, **kwargs):
        ledger = RunLedger.create(out_dir=self.root / "runs", mode="test")
        return StageSession(ledger, cache_dir=self.root / "cache", responder=responder, namespace="synthetic-test", **kwargs)

    def test_end_to_end_pairing_is_reproducible_via_cache(self):
        sources = [indexed_source(demo_record())]
        first = self.session()
        metrics = run_comparison(sources, MODELS, first)
        inputs = rows(first.ledger.run_dir / "inputs.jsonl")
        outputs = rows(first.ledger.run_dir / "outputs.jsonl")
        self.assertEqual(len(inputs), 8)
        self.assertEqual([r["item_id"] for r in inputs], [r["item_id"] for r in outputs])
        self.assertEqual(len({r["case_group"] for r in outputs}), 1)
        for row in metrics:
            self.assertEqual(row["candidate_items"], row["accepted_items"] + row["rejected_items"])
        def forbidden(*args):
            self.fail("cached rerun must not call a model")
        second = self.session(forbidden)
        run_comparison(sources, MODELS, second)
        self.assertEqual(second.http_requests, 0)
        self.assertGreater(second.cache_hits, 0)
        self.assertEqual(inputs, rows(second.ledger.run_dir / "inputs.jsonl"))
        self.assertEqual(outputs, rows(second.ledger.run_dir / "outputs.jsonl"))

    def test_malformed_response_is_persisted_before_rejection_and_not_resampled(self):
        def malformed(*args):
            return {"content": '{"truncated":', "raw": {}, "model": "test", "latency_ms": 0}
        first = self.session(malformed)
        for session in (first, self.session(lambda *a: self.fail("unexpected resample"))):
            with self.assertRaises(ContractError):
                session.call(MODELS[0], "extract", {"spans": []})
            self.assertTrue(rows(session.ledger.run_dir / "calls.jsonl"))
        self.assertEqual(len(list((self.root / "cache").glob("*.json"))), 1)

    def test_cache_tampering_is_fatal_and_trial_change_is_explicit(self):
        first = self.session()
        first.call(MODELS[0], "extract", {})
        second = self.session(trial="1")
        second.call(MODELS[0], "extract", {})
        self.assertEqual(second.synthetic_requests, 1)
        for file in (self.root / "cache").glob("*.json"):
            cached = json.loads(file.read_text())
            cached["response"]["content"] = "tampered"
            file.write_text(json.dumps(cached))
        with self.assertRaisesRegex(RuntimeError, "cache hash mismatch"):
            self.session().call(MODELS[0], "extract", {})

    def test_case_audit_schema_failure_preserves_denominator(self):
        def broken(model, stage, payload):
            result = demo_responder(model, stage, payload)
            if stage == "audit":
                result["content"] = "{}"
            return result
        session = self.session(broken)
        metrics = run_comparison([indexed_source(demo_record())], MODELS, session)
        for row in metrics:
            self.assertEqual(row["candidate_items"], 4)
            self.assertEqual(row["rejected_items"], 4)
            self.assertEqual(row["accepted_items"], 0)
        self.assertFalse((session.ledger.run_dir / "outputs.jsonl").exists())

    def test_blind_rejections_remain_in_per_case_denominator(self):
        def reject_blind(model, stage, payload):
            result = demo_responder(model, stage, payload)
            if stage == "blind":
                data = strict_json(result["content"])
                data["defects"] = ["Synthetic structural defect"]
                result["content"] = json.dumps(data)
            return result
        session = self.session(reject_blind)
        run_comparison([indexed_source(demo_record())], MODELS, session)
        for row in rows(session.ledger.run_dir / "case_results.jsonl"):
            self.assertEqual(row["candidate_count"], row["accepted"] + row["rejected"])
            self.assertEqual(row["rejected"], 4)

    def test_cli_plan_and_demo_never_dispatch_http(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")), redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 0)
            self.assertEqual(main(["--demo", "--out", str(self.root / "demo"), "--cache", str(self.root / "demo-cache")]), 0)

    def test_test_cases_cannot_be_used_for_development_comparison(self):
        cases = self.root / "cases"
        cases.mkdir()
        record = demo_record()
        record["split"] = "test"
        (cases / "case.json").write_text(json.dumps(record))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            with self.assertRaises(SystemExit):
                main(["--live", "--cases", str(cases)])
            with self.assertRaises(SystemExit):
                main(["--live", "--cases", str(cases), "--purpose", "test"])

    def test_duplicate_case_ids_cannot_create_colliding_item_ids(self):
        cases = self.root / "cases"
        cases.mkdir()
        record = demo_record()
        record["split"] = "development"
        (cases / "a.json").write_text(json.dumps(record))
        record["case_text"] += " Different text."
        (cases / "b.json").write_text(json.dumps(record))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["--cases", str(cases), "--limit", "1"])

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_fences(self):
        for text in ('{"a": 1, "a": 2}', '{"a": NaN}', '```json\n{}\n```'):
            with self.subTest(text=text), self.assertRaises(ContractError):
                strict_json(text)


if __name__ == "__main__":
    unittest.main()
