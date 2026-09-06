"""Smoke tests for the carried-over infrastructure."""

import json
import tempfile
import unittest
from pathlib import Path

from clinical_orchestra.ledger import RunLedger
from clinical_orchestra.model_client import DEFAULT_SYSTEM_PROMPT, OpenAICompatibleChatClient
from clinical_orchestra.ncbi import NcbiConfig


class TestLedger(unittest.TestCase):
    def test_run_writes_manifest_events_and_streams(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger.create(
                out_dir=tmp,
                mode="smoke",
                config={"temperature": 0.0},
                source_exclusion={"pmcids": ["PMC123"]},
            )
            ledger.append("results", {"item_id": "a", "score": 1})
            ledger.finish()

            manifest = json.loads((ledger.run_dir / "manifest.json").read_text())
            self.assertEqual(manifest["mode"], "smoke")
            self.assertEqual(manifest["status"], "completed")
            self.assertEqual(manifest["config"]["temperature"], 0.0)
            self.assertEqual(manifest["source_exclusion"]["pmcids"], ["PMC123"])

            events = (ledger.run_dir / "events.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(events), 2)  # run_created, run_finished

            results = (ledger.run_dir / "results.jsonl").read_text().strip().splitlines()
            self.assertEqual(json.loads(results[0])["item_id"], "a")

    def test_will_not_write_into_an_existing_run_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            RunLedger.create(out_dir=tmp, mode="smoke", run_id="fixed")
            with self.assertRaises(FileExistsError):
                RunLedger.create(out_dir=tmp, mode="smoke", run_id="fixed")


class TestModelClient(unittest.TestCase):
    def test_system_prompt_is_configurable(self):
        client = OpenAICompatibleChatClient(
            api_key="test-key", base_url="https://example.invalid", model="m"
        )
        self.assertEqual(client.system_prompt, DEFAULT_SYSTEM_PROMPT)

        custom = OpenAICompatibleChatClient(
            api_key="test-key",
            base_url="https://example.invalid",
            model="m",
            system_prompt="custom",
        )
        self.assertEqual(custom.system_prompt, "custom")

    def test_api_key_is_required(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleChatClient(api_key="", base_url="https://example.invalid", model="m")


class TestNcbi(unittest.TestCase):
    def test_tool_name_identifies_this_project(self):
        self.assertEqual(NcbiConfig().tool, "ClinicalOrchestra2")


if __name__ == "__main__":
    unittest.main()
