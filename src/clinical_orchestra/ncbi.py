"""Small stdlib client for NCBI E-Utilities."""

from __future__ import annotations

import gzip
import http.client
import json
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError

# Transient network faults worth retrying. RemoteDisconnected (server closed the connection without
# a response) is an http.client.HTTPException AND a ConnectionResetError(OSError); ConnectionError
# and other OSErrors cover dropped/reset sockets. urllib does not wrap these in URLError.
_TRANSIENT_NETWORK_ERRORS = (HTTPError, URLError, TimeoutError, http.client.HTTPException, OSError)
from urllib.parse import urlencode
from urllib.request import Request, urlopen


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass(frozen=True)
class NcbiConfig:
    tool: str = "ClinicalOrchestra2"
    email: str | None = None
    api_key: str | None = None
    verify_tls: bool = True
    min_interval_seconds: float = 0.34
    retries: int = 3


class NcbiClient:
    """Rate-limited E-Utilities client.

    NCBI asks automated tools to identify themselves with a tool name and email.
    API keys can raise rate limits, but this client stays conservative by default.
    """

    def __init__(self, config: NcbiConfig) -> None:
        self.config = config
        self._last_request_at = 0.0
        # NCBI rate limits are enforced per-account, not per-connection. Under concurrent case
        # evaluation many threads share one client, so the spacing must be serialized with a lock
        # or we would burst past NCBI's ~3/s (no key) / ~10/s (key) ceiling and earn 429s/bans.
        self._rate_lock = threading.Lock()
        self._ssl_context = None if config.verify_tls else ssl._create_unverified_context()

    def get_json(self, endpoint: str, params: dict[str, str | int]) -> dict[str, Any]:
        data = self.get_bytes(endpoint, params, accept_compression=False)
        return json.loads(data.decode("utf-8"))

    def get_text(self, endpoint: str, params: dict[str, str | int]) -> str:
        data = self.get_bytes(endpoint, params, accept_compression=True)
        return data.decode("utf-8")

    def get_bytes(
        self,
        endpoint: str,
        params: dict[str, str | int],
        *,
        accept_compression: bool = True,
    ) -> bytes:
        query = dict(params)
        query.setdefault("tool", self.config.tool)
        if self.config.email:
            query.setdefault("email", self.config.email)
        if self.config.api_key:
            query.setdefault("api_key", self.config.api_key)

        url = f"{EUTILS_BASE}/{endpoint}?" + urlencode(query)
        headers = {"User-Agent": self._user_agent()}
        if accept_compression:
            headers["Accept-Encoding"] = "gzip, deflate"

        last_error: Exception | None = None
        for attempt in range(self.config.retries):
            self._respect_rate_limit()
            try:
                request = Request(url, headers=headers)
                with urlopen(request, timeout=60, context=self._ssl_context) as response:
                    data = response.read()
                    encoding = response.headers.get("Content-Encoding", "")
                return _decompress_if_needed(data, encoding)
            except _TRANSIENT_NETWORK_ERRORS as exc:
                last_error = exc
                if attempt + 1 == self.config.retries:
                    break
                time.sleep(2**attempt)

        assert last_error is not None
        raise last_error

    def _respect_rate_limit(self) -> None:
        # Hold the lock across the sleep so concurrent workers serialize their request spacing and
        # the global NCBI rate stays within min_interval_seconds regardless of worker count.
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            wait = self.config.min_interval_seconds - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()

    def _user_agent(self) -> str:
        if self.config.email:
            return f"{self.config.tool}/0.1 (mailto:{self.config.email})"
        return f"{self.config.tool}/0.1"


def _decompress_if_needed(data: bytes, encoding: str) -> bytes:
    if encoding.lower() == "gzip" or data.startswith(b"\x1f\x8b"):
        return gzip.decompress(data)
    return data
