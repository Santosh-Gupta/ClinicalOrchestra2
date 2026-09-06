"""Minimal OpenAI-compatible chat client for benchmark runs."""

from __future__ import annotations

import http.client
import json
import os
import random
import ssl
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .ratelimit import NoOpRateLimiter, RateLimiter, SlidingWindowRateLimiter

# Transient HTTP statuses worth retrying: 429 (concurrency limit exceeded) and common gateway
# errors. DeepSeek returns 429 when the account-level concurrency cap (500 pro / 2500 flash) is hit.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# The task prompt is set by the caller, not baked into the client. v1 hardcoded a
# diagnosis-specific system prompt here, which made the client hard to reuse.
DEFAULT_SYSTEM_PROMPT = (
    "You are a benchmark clinical reasoning model. Return only valid JSON. "
    "Do not include hidden chain-of-thought."
)


def _estimate_tokens(prompt: str, max_tokens: int) -> int:
    """Rough upper bound for TPM budgeting: prompt tokens (~4 chars/token) + reserved completion."""
    return len(prompt) // 4 + max_tokens


_shared_rate_limiter: RateLimiter | None = None
_shared_rate_limiter_lock = threading.Lock()


def _env_rate_limiter() -> RateLimiter | None:
    """Build one process-wide limiter from MODEL_MAX_RPM / MODEL_MAX_TPM, shared across clients.

    Rate caps are account-level, so the answer client, judge client, and every worker thread must
    share a single limiter instance. Returns None (no throttle) when neither env var is set, which
    is the DeepSeek default.
    """
    global _shared_rate_limiter
    rpm = os.getenv("MODEL_MAX_RPM")
    tpm = os.getenv("MODEL_MAX_TPM")
    if not rpm and not tpm:
        return None
    with _shared_rate_limiter_lock:
        if _shared_rate_limiter is None:
            _shared_rate_limiter = SlidingWindowRateLimiter(
                max_requests=int(rpm) if rpm else None,
                max_tokens=int(tpm) if tpm else None,
            )
    return _shared_rate_limiter


@dataclass(frozen=True)
class ChatCompletionResult:
    model: str
    content: str
    raw: dict[str, Any]
    latency_ms: int


class OpenAICompatibleChatClient:
    """Small standard-library client for /chat/completions APIs."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        backoff_cap_seconds: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        verify_tls: bool | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_cap_seconds = backoff_cap_seconds
        self.system_prompt = system_prompt
        # No-op by default (DeepSeek is concurrency-limited, not rate-limited). Providers with
        # RPM/TPM caps pass a shared SlidingWindowRateLimiter so requests are throttled proactively.
        self.rate_limiter: RateLimiter = rate_limiter or NoOpRateLimiter()
        if verify_tls is None:
            verify_tls = os.getenv("MODEL_VERIFY_TLS", "1").lower() not in {"0", "false", "no"}
        self._ssl_context = None if verify_tls else ssl._create_unverified_context()

    @classmethod
    def from_env(
        cls, *, model: str | None = None, system_prompt: str = DEFAULT_SYSTEM_PROMPT
    ) -> "OpenAICompatibleChatClient":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"
        resolved_model = model or os.getenv("DEEPSEEK_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-v4-flash"
        timeout_seconds = float(os.getenv("MODEL_TIMEOUT_SECONDS", "120"))
        max_retries = int(os.getenv("MODEL_MAX_RETRIES", "5"))
        if not api_key:
            raise ValueError(
                "No model API key found. Set DEEPSEEK_API_KEY for DeepSeek or OPENAI_API_KEY for another "
                "OpenAI-compatible endpoint."
            )
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=resolved_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            rate_limiter=_env_rate_limiter(),
            system_prompt=system_prompt,
        )

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_cap_seconds)
            except ValueError:
                pass
        # Exponential backoff with full jitter so concurrent workers don't retry in lockstep.
        ceiling = min(self.backoff_base_seconds * (2**attempt), self.backoff_cap_seconds)
        return random.uniform(0.0, ceiling)

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        url = f"{self.base_url}/chat/completions"
        # Provider quirks (default path = DeepSeek/OpenAI-classic, unchanged). Detected from base_url/model
        # so the same OpenAI-compatible client can drive OpenAI gpt-5.x, Anthropic, and Gemini for
        # cross-model benchmarking without a separate client per provider.
        _base = self.base_url.lower()
        # gpt-5.x needs max_completion_tokens on this path. Temperature support varies by model/API
        # surface; the HTTP-400 fallback below drops it once if the provider rejects it. Final paper
        # runs should use a provider-native path that records explicit reasoning/temperature settings.
        # o-series needs max_completion_tokens and rejects custom temperature.
        _is_gpt5 = "openai.com" in _base and self.model.startswith("gpt-5")
        _is_o_series = "openai.com" in _base and self.model.startswith(("o1", "o3", "o4"))
        _is_anthropic = "anthropic.com" in _base
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if _is_gpt5 or _is_o_series:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
        if _is_o_series:
            payload.pop("temperature", None)  # o-series rejects a custom temperature
        if _is_anthropic:
            # Anthropic's OpenAI-compat layer rejects response_format=json_object (wants json_schema);
            # the system prompt already constrains to JSON, so drop it. Newer Anthropic models also
            # deprecate the temperature parameter.
            payload.pop("response_format", None)
            payload.pop("temperature", None)
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        token_estimate = _estimate_tokens(prompt, max_tokens)
        started = time.monotonic()
        raw: dict[str, Any] | None = None
        for attempt in range(self.max_retries + 1):
            # Proactively wait for RPM/TPM headroom before sending. Each retry is a real request to
            # the provider, so it must re-acquire (no-op under the DeepSeek default).
            self.rate_limiter.acquire(tokens=token_estimate)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds, context=self._ssl_context) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in _RETRYABLE_STATUS and attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt, exc.headers.get("Retry-After")))
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 400 and "temperature" in body.lower() and "temperature" in payload:
                    # Some models reject a custom temperature (e.g. certain GPT reasoning-model chat
                    # surfaces, Opus "deprecated", o-series). Drop it and retry once — the model then
                    # runs at its default temperature
                    # (so it is NOT reproducible at 0.0; use multi-seed for those). Self-limiting: once
                    # popped, a subsequent 400 won't re-enter this branch.
                    payload.pop("temperature", None)
                    data = json.dumps(payload).encode("utf-8")
                    request = urllib.request.Request(
                        url, data=data, method="POST",
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    )
                    continue
                raise RuntimeError(f"model API HTTP {exc.code}: {body[:1000]}") from exc
            except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as exc:
                # Transient connection faults (incl. RemoteDisconnected / reset sockets) are common
                # under concurrency; retry with backoff before giving up.
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt, None))
                    continue
                raise RuntimeError(f"model API request failed after {attempt + 1} attempts: {exc}") from exc
        assert raw is not None
        latency_ms = int((time.monotonic() - started) * 1000)
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("model API response did not contain choices")
        # LOUD truncation detection: a response cut off at the token limit yields invalid/partial JSON
        # that would otherwise be silently swallowed downstream (empty floor, dropped paper, etc.).
        # Raise so the retry loop re-issues, and if it persists the case fails visibly instead of degrading.
        finish_reason = choices[0].get("finish_reason")
        if finish_reason == "length":
            budget = payload.get("max_tokens") or payload.get("max_completion_tokens")
            raise RuntimeError(
                f"model API response TRUNCATED (finish_reason=length, max_tokens={budget}) for model "
                f"{self.model}: output hit the token limit and is incomplete. Increase max_tokens."
            )
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("model API response did not contain message.content")
        raw.setdefault(
            "_request",
            {
                "endpoint": url,
                "model": self.model,
                "temperature": payload.get("temperature"),
                "max_tokens": payload.get("max_tokens"),
                "max_completion_tokens": payload.get("max_completion_tokens"),
                "response_format": payload.get("response_format"),
            },
        )
        return ChatCompletionResult(model=self.model, content=message["content"], raw=raw, latency_ms=latency_ms)


class OpenAIResponsesClient:
    """Small standard-library client for OpenAI's native /responses API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 300.0,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
        backoff_cap_seconds: float = 30.0,
        rate_limiter: RateLimiter | None = None,
        reasoning_effort: str = "medium",
        text_verbosity: str | None = None,
        verify_tls: bool | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_cap_seconds = backoff_cap_seconds
        self.rate_limiter: RateLimiter = rate_limiter or NoOpRateLimiter()
        self.reasoning_effort = reasoning_effort
        self.text_verbosity = text_verbosity
        self.system_prompt = system_prompt
        if verify_tls is None:
            verify_tls = os.getenv("MODEL_VERIFY_TLS", "1").lower() not in {"0", "false", "no"}
        self._ssl_context = None if verify_tls else ssl._create_unverified_context()

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), self.backoff_cap_seconds)
            except ValueError:
                pass
        ceiling = min(self.backoff_base_seconds * (2**attempt), self.backoff_cap_seconds)
        return random.uniform(0.0, ceiling)

    def chat(self, *, prompt: str, temperature: float = 0.0, max_tokens: int = 4096) -> ChatCompletionResult:
        url = f"{self.base_url}/responses"
        text_config: dict[str, Any] = {"format": {"type": "json_object"}}
        if self.text_verbosity:
            text_config["verbosity"] = self.text_verbosity
        requested_temperature: float | None = temperature
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "reasoning": {"effort": self.reasoning_effort},
            "text": text_config,
            "store": False,
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        token_estimate = _estimate_tokens(prompt, max_tokens)
        started = time.monotonic()
        raw: dict[str, Any] | None = None
        for attempt in range(self.max_retries + 1):
            self.rate_limiter.acquire(tokens=token_estimate)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds, context=self._ssl_context) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in _RETRYABLE_STATUS and attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt, exc.headers.get("Retry-After")))
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 400 and "temperature" in body.lower() and "temperature" in payload:
                    payload.pop("temperature", None)
                    data = json.dumps(payload).encode("utf-8")
                    request = urllib.request.Request(
                        url,
                        data=data,
                        method="POST",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    continue
                raise RuntimeError(f"responses API HTTP {exc.code}: {body[:1000]}") from exc
            except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as exc:
                if attempt < self.max_retries:
                    time.sleep(self._retry_delay(attempt, None))
                    continue
                raise RuntimeError(f"responses API request failed after {attempt + 1} attempts: {exc}") from exc
        assert raw is not None
        latency_ms = int((time.monotonic() - started) * 1000)
        # LOUD truncation detection for the Responses API (gpt-5.x): an incomplete response capped at
        # max_output_tokens is partial/invalid and must not be silently passed downstream.
        if raw.get("status") == "incomplete":
            reason = (raw.get("incomplete_details") or {}).get("reason")
            if reason == "max_output_tokens":
                raise RuntimeError(
                    f"responses API response TRUNCATED (incomplete: max_output_tokens={max_tokens}) for "
                    f"model {self.model}: output is incomplete. Increase max_tokens."
                )
        content = _responses_text(raw)
        if not content:
            raise RuntimeError("responses API response did not contain output text")
        raw.setdefault(
            "_request",
            {
                "endpoint": url,
                "model": self.model,
                "temperature": payload.get("temperature"),
                "requested_temperature": requested_temperature,
                "temperature_omitted_after_rejection": "temperature" not in payload,
                "max_output_tokens": max_tokens,
                "reasoning": payload["reasoning"],
                "text": text_config,
                "store": False,
            },
        )
        return ChatCompletionResult(model=self.model, content=content, raw=raw, latency_ms=latency_ms)


def _responses_text(raw: dict[str, Any]) -> str:
    output_text = raw.get("output_text")
    if isinstance(output_text, str):
        return output_text
    chunks: list[str] = []
    output = raw.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if isinstance(part.get("text"), str):
                    chunks.append(part["text"])
                elif isinstance(part.get("refusal"), str):
                    chunks.append(part["refusal"])
    return "".join(chunks)
