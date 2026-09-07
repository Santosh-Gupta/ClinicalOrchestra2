#!/usr/bin/env python3.11
"""List the model IDs each configured provider actually exposes.

Model IDs change faster than any file in this repo, and a guessed ID fails as a 404 that looks like
an outage. This asks each provider what it has, so `models.toml` can be pinned to real IDs.

Usage:
  source <env file with the XM_* keys>
  python3.11 scripts/discover_models.py [--filter flash]

Providers with no key set are skipped and reported as such, not treated as failures.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

# (provider, env var holding the key, list-models URL, extra headers, how to read the response)
PROVIDERS = [
    ("openai", "XM_OPENAI_KEY", "https://api.openai.com/v1/models", "bearer"),
    ("anthropic", "XM_ANTHROPIC_KEY", "https://api.anthropic.com/v1/models?limit=100", "anthropic"),
    (
        "gemini",
        "XM_GEMINI_KEY",
        "https://generativelanguage.googleapis.com/v1beta/openai/models",
        "bearer",
    ),
    # No keys configured yet for these two; listed so the gap is visible rather than forgotten.
    ("zhipu", "XM_ZHIPU_KEY", "https://api.z.ai/api/paas/v4/models", "bearer"),
    ("moonshot", "XM_MOONSHOT_KEY", "https://api.moonshot.ai/v1/models", "bearer"),
]


def _ssl_context() -> ssl.SSLContext | None:
    cert_file = os.getenv("SSL_CERT_FILE")
    if cert_file and os.path.exists(cert_file):
        return ssl.create_default_context(cafile=cert_file)
    return None


def fetch(url: str, key: str, auth: str) -> dict:
    headers = {"Accept": "application/json"}
    if auth == "anthropic":
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def model_ids(payload: dict) -> list[str]:
    """Both the OpenAI-style ({'data': [{'id': ...}]}) and Anthropic-style shapes land here."""
    items = payload.get("data") or payload.get("models") or []
    ids = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("id") or item.get("name")
            if isinstance(value, str):
                ids.append(value.removeprefix("models/"))
    return sorted(ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", default=None, help="only print IDs containing this substring")
    args = parser.parse_args()

    missing_keys = []
    for provider, env_var, url, auth in PROVIDERS:
        key = os.getenv(env_var)
        if not key:
            missing_keys.append((provider, env_var))
            continue
        print(f"\n=== {provider} ===")
        try:
            ids = model_ids(fetch(url, key, auth))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            print(f"  HTTP {exc.code}: {body}")
            continue
        except Exception as exc:  # noqa: BLE001 - discovery should report, not crash
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            continue
        shown = [i for i in ids if args.filter in i] if args.filter else ids
        print(f"  {len(ids)} models" + (f", {len(shown)} matching {args.filter!r}" if args.filter else ""))
        for model_id in shown:
            print(f"    {model_id}")

    if missing_keys:
        print("\n=== no key set (skipped) ===")
        for provider, env_var in missing_keys:
            print(f"  {provider}: set {env_var}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
