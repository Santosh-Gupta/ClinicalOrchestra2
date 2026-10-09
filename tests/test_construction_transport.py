"""Mocked provider requests, off-peak boundaries and audit-log failure handling."""

from datetime import UTC, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from clinical_orchestra.construction.api import DeferredRequest, StageSession, models_from_file, require_off_peak
from clinical_orchestra.construction.demo import demo_responder
from clinical_orchestra.ledger import RunLedger
from clinical_orchestra.model_client import OpenAICompatibleChatClient

ROOT = Path(__file__).resolve().parents[1]


def response(content="{}", finish_reason="stop"):
    return io.BytesIO(json.dumps({"choices": [{"message": {"content": content}, "finish_reason": finish_reason}], "usage": {"prompt_tokens": 10, "completion_tokens": 2}}).encode())


class TransportTests(unittest.TestCase):
    def client(self, **kwargs):
        return OpenAICompatibleChatClient(api_key="secret-test-key", base_url="https://example.test/v1", model="test", backoff_base_seconds=0, **kwargs)

    def test_registry_routes_each_requested_slot_with_json_mode(self):
        for model in models_from_file(ROOT / "construction_models.toml"):
            captured = []
            def send(req, **kwargs):
                captured.append(req)
                return response()
            with self.subTest(model=model.key), patch("urllib.request.urlopen", side_effect=send):
                client = OpenAICompatibleChatClient(api_key="secret-test-key", base_url=model.spec.base_url, model=model.spec.model_id)
                client.chat(prompt="test", max_tokens=100)
            self.assertEqual(captured[0].full_url, model.spec.base_url + "/chat/completions")
            payload = json.loads(captured[0].data)
            self.assertEqual(payload["model"], model.spec.model_id)
            self.assertEqual(payload["response_format"], {"type": "json_object"})
            self.assertEqual(payload["temperature"], 0.0)

    def test_guard_rechecks_schedule_before_every_retry(self):
        guards = []
        def guard():
            guards.append(True)
            if len(guards) == 2:
                raise DeferredRequest("peak began")
        error = HTTPError("https://example.test", 429, "rate limit", {}, io.BytesIO(b"retry"))
        with patch("urllib.request.urlopen", side_effect=error) as send:
            with self.assertRaises(DeferredRequest):
                self.client(before_request=guard).chat(prompt="test")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(len(guards), 2)

    def test_truncation_and_invalid_envelope_are_saved_without_retry(self):
        for raw in (response('{"partial":', "length"), io.BytesIO(b"not-json")):
            events = []
            with patch("urllib.request.urlopen", return_value=raw) as send:
                with self.assertRaises((RuntimeError, ValueError)):
                    self.client(observer=events.append).chat(prompt="test")
            self.assertEqual(send.call_count, 1)
            self.assertEqual(events[-1]["event"], "response")

    def test_failed_response_log_write_is_fatal_without_resending(self):
        def observer(event):
            if event["event"] == "response":
                raise OSError("disk full")
        with patch("urllib.request.urlopen", return_value=response()) as send:
            with self.assertRaisesRegex(OSError, "disk full"):
                self.client(observer=observer).chat(prompt="test")
        self.assertEqual(send.call_count, 1)

    def test_http_error_body_is_redacted_in_log_and_exception(self):
        events = []
        error = HTTPError("https://example.test", 401, "denied", {}, io.BytesIO(b"invalid secret-test-key"))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(RuntimeError) as raised:
                self.client(observer=events.append).chat(prompt="test")
        self.assertNotIn("secret-test-key", str(raised.exception))
        self.assertNotIn("secret-test-key", json.dumps(events))
        self.assertIn("[REDACTED]", json.dumps(events))

    def test_provider_extras_cannot_replace_model_messages_or_budget(self):
        for key in ("model", "messages", "max_tokens", "temperature"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.client(extra_body={key: "override"})

    def test_off_peak_gate_obeys_utc_weekends_and_timeout_margin(self):
        require_off_peak(when=datetime(2026, 9, 17, 10, 0, tzinfo=UTC))
        require_off_peak(when=datetime(2026, 9, 19, 2, 0, tzinfo=UTC))
        for when in (datetime(2026, 9, 17, 1, 0, tzinfo=UTC),
                     datetime(2026, 9, 17, 5, 59, tzinfo=UTC),
                     datetime(2026, 9, 16, 18, 0, tzinfo=timezone(timedelta(hours=-7)))):
            with self.subTest(when=when), self.assertRaises(DeferredRequest):
                require_off_peak(when=when)
        with self.assertRaises(ValueError):
            require_off_peak(when=datetime(2026, 9, 17, 10))

    def test_http_budget_counts_attempts_and_stops_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger.create(out_dir=tmp, mode="test")
            model = models_from_file(ROOT / "construction_models.toml")[2]
            session = StageSession(ledger, cache_dir=Path(tmp) / "cache", max_requests=1, responder=demo_responder, namespace="synthetic")
            session.call(model, "extract", {})
            with self.assertRaises(DeferredRequest):
                session.call(model, "extract", {"different": True})
            self.assertEqual(session.synthetic_requests, 1)
            self.assertEqual(session.http_requests, 0)


if __name__ == "__main__":
    unittest.main()
