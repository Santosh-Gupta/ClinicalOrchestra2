"""Readiness, off-peak dispatch, bounded transport and exact stage-response reuse."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tomllib

from ..ledger import utc_now, write_json
from ..model_client import OpenAICompatibleChatClient, _env_rate_limiter
from ..peak import is_peak, next_change
from ..registry import ModelSpec, load_registry
from .evidence import digest
from .prompts import render
from .schemas import ContractError, SCHEMAS, validate


class DeferredRequest(RuntimeError):
    """No HTTP request was dispatched: outside allowed schedule or run budget."""


@dataclass(frozen=True)
class ConstructionModel:
    spec: ModelSpec
    id_status: str
    off_peak_only: bool = False
    contributor: bool = False
    extra_body: dict | None = None

    @property
    def key(self):
        return self.spec.key

    @property
    def provider(self):
        return self.spec.provider

    def public_config(self):
        return {**asdict(self.spec), "id_status": self.id_status,
                "off_peak_only": self.off_peak_only, "contributor": self.contributor,
                "extra_body": self.extra_body or {}}


def models_from_file(path):
    metadata = {x["key"]: x for x in tomllib.loads(Path(path).read_text())["model"]}
    return [ConstructionModel(s, metadata[s.key].get("id_status", "unresolved"),
                              metadata[s.key].get("off_peak_only", False),
                              metadata[s.key].get("contributor", False),
                              metadata[s.key].get("extra_body", {})) for s in load_registry(path)]


def readiness(model):
    reasons = []
    if not model.spec.enabled:
        reasons.append("disabled")
    if model.id_status != "documented" or model.spec.model_id.startswith("UNVERIFIED"):
        reasons.append("unresolved_model_id")
    if not model.spec.has_key:
        reasons.append(f"missing_key:{model.spec.api_key_env}")
    if model.spec.api != "chat":
        reasons.append("construction_requires_chat_transport")
    return {"key": model.key, "model_id": model.spec.model_id,
            "provider": model.provider, "credential_env": model.spec.api_key_env,
            "ready": not reasons, "reasons": reasons,
            "account_probed": False, "off_peak_only": model.off_peak_only}


def require_off_peak(*, timeout_seconds=300, when=None):
    now = when or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("off-peak checks require a timezone-aware datetime")
    if is_peak(now):
        raise DeferredRequest(f"DeepSeek peak window; next change {next_change(now).isoformat()}")
    remaining = (next_change(now) - now).total_seconds()
    if remaining <= timeout_seconds + 15:
        raise DeferredRequest("DeepSeek off-peak window too short for request timeout plus 15-second margin")


def strict_json(text):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ContractError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ContractError(f"non-finite JSON constant: {value}")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON: {exc.msg}") from exc


class StageSession:
    def __init__(self, ledger, *, cache_dir, max_requests=30, max_tokens=16000,
                 timeout_seconds=300, trial="0", responder=None, namespace="live"):
        self.ledger = ledger
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.trial = trial
        self.responder = responder
        self.namespace = namespace
        self.http_requests = 0
        self.synthetic_requests = 0
        self.cache_hits = 0
        self.rate_limiter = _env_rate_limiter()
        if min(max_requests, max_tokens, timeout_seconds) <= 0:
            raise ValueError("request, token and timeout budgets must be positive")

    def call(self, model, stage, payload):
        request = render(stage, payload)
        identity = {**request, "model": model.public_config(), "temperature": 0.0,
                    "max_tokens": self.max_tokens, "timeout_seconds": self.timeout_seconds,
                    "trial": self.trial, "namespace": self.namespace}
        request_hash = digest(identity)
        cache_path = self.cache_dir / f"{request_hash}.json"
        self.ledger.append("requests", {"request_hash": request_hash, **identity})
        if cache_path.exists():
            cached = strict_json(cache_path.read_text())
            if cached["request_hash"] != request_hash or digest(cached["response"]) != cached["response_hash"]:
                raise RuntimeError("cache hash mismatch; stop and inspect cache integrity")
            response = cached["response"]
            self.cache_hits += 1
            self.ledger.append("calls", {"request_hash": request_hash, "cache_hit": True, "response": response})
        else:
            def guard():
                if model.off_peak_only and self.responder is None:
                    require_off_peak(timeout_seconds=self.timeout_seconds)
                if self.http_requests + self.synthetic_requests >= self.max_requests:
                    raise DeferredRequest(f"HTTP request budget {self.max_requests} exhausted; reuse cache on next run")
                if self.responder is None:
                    self.http_requests += 1
                else:
                    self.synthetic_requests += 1
            def observe(event):
                self.ledger.append("transport", {"request_hash": request_hash, "timestamp": utc_now(), **event})
            if self.responder is not None:
                guard()
                response = self.responder(model, stage, payload)
                observe({"event": "synthetic_response", "body": response["content"]})
            else:
                client = OpenAICompatibleChatClient(
                    api_key=os.environ[model.spec.api_key_env], base_url=model.spec.base_url,
                    model=model.spec.model_id, system_prompt=request["system"],
                    timeout_seconds=self.timeout_seconds, max_retries=2,
                    rate_limiter=self.rate_limiter, extra_body=model.extra_body,
                    before_request=guard, observer=observe,
                )
                result = client.chat(prompt=request["prompt"], temperature=0.0, max_tokens=self.max_tokens)
                response = {"model": result.model, "content": result.content,
                            "raw": result.raw, "latency_ms": result.latency_ms}
            # Raw response is saved before JSON/schema validation, including failures.
            self.ledger.append("calls", {"request_hash": request_hash, "cache_hit": False, "response": response})
            write_json(cache_path, {"request_hash": request_hash, "response": response, "response_hash": digest(response)})
        parsed = strict_json(response["content"])
        validate(parsed, SCHEMAS[stage])
        return parsed
