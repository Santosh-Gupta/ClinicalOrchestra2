#!/usr/bin/env python3.11
"""Send one small real request to each model and report what the API actually does.

Run this before any dataset work and again whenever a model is added. It answers the questions that
otherwise surface halfway through an expensive run: does the key work, does the model accept
temperature 0, does it honour a JSON response format, how slow is it, and how many tokens does a
short request cost.

Usage:
  export SSL_CERT_FILE=$(python3.11 -c "import certifi;print(certifi.where())")
  source <env file with the XM_* keys>
  PYTHONPATH=src python3.11 scripts/probe_models.py --tier cheap
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from clinical_orchestra.registry import build_client, load_registry, select

SYSTEM_PROMPT = (
    "You are a benchmark clinical reasoning model. Return only valid JSON. "
    "Do not include hidden chain-of-thought."
)

# Deliberately tiny and unambiguous: this probes the transport, not the model's ability.
PROBE_PROMPT = (
    "A patient presents with fever, headache, and neck stiffness. Name the single most appropriate "
    'next diagnostic test. Respond with JSON of exactly this shape: {"next_test": "<test name>"}'
)


def probe(spec) -> dict:
    result: dict = {
        "key": spec.key,
        "provider": spec.provider,
        "model_id": spec.model_id,
        "api": spec.api,
        "tier": spec.tier,
    }
    try:
        client = build_client(spec, system_prompt=SYSTEM_PROMPT, timeout_seconds=120.0)
    except Exception as exc:  # noqa: BLE001 - a probe reports failures, it does not raise
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    started = time.monotonic()
    try:
        response = client.chat(prompt=PROBE_PROMPT, temperature=0.0, max_tokens=2048)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["latency_ms"] = int((time.monotonic() - started) * 1000)
        return result

    result["status"] = "ok"
    result["latency_ms"] = response.latency_ms

    # Did the provider actually run at temperature 0, or did the client drop it after a 400?
    request_echo = response.raw.get("_request", {})
    result["temperature_sent"] = request_echo.get("temperature")
    result["temperature_dropped"] = request_echo.get("temperature") is None

    usage = response.raw.get("usage") or {}
    result["usage"] = {
        "prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
        "completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }

    content = response.content.strip()
    result["raw_content"] = content[:300]
    try:
        parsed = json.loads(content)
        result["valid_json"] = True
        result["answer"] = parsed.get("next_test") if isinstance(parsed, dict) else None
        result["schema_ok"] = isinstance(parsed, dict) and "next_test" in parsed
    except json.JSONDecodeError:
        # Not fatal, but it means this model needs lenient parsing in the eval runner.
        result["valid_json"] = False
        result["schema_ok"] = False
        result["answer"] = None
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default=None, help="cheap | expensive")
    parser.add_argument("--models", nargs="*", default=None, help="specific registry keys")
    parser.add_argument("--out", default="runs/probes", help="directory for the probe report")
    args = parser.parse_args()

    specs = load_registry()
    selected = select(specs, tier=args.tier, keys=args.models, require_key=False)
    if not selected:
        print("no models selected", file=sys.stderr)
        return 1

    results = []
    for spec in selected:
        if not spec.has_key:
            print(f"  SKIP {spec.key}: {spec.api_key_env} not set")
            results.append(
                {"key": spec.key, "status": "skipped", "reason": f"{spec.api_key_env} not set"}
            )
            continue
        print(f"  probing {spec.key} ...", end=" ", flush=True)
        result = probe(spec)
        results.append(result)
        if result["status"] == "ok":
            flags = []
            if not result["valid_json"]:
                flags.append("NOT-JSON")
            if result["temperature_dropped"]:
                flags.append("TEMP-DROPPED")
            suffix = (" [" + ", ".join(flags) + "]") if flags else ""
            print(f"ok {result['latency_ms']}ms -> {result['answer']!r}{suffix}")
        else:
            print(f"FAILED: {result['error'][:160]}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_path = out_dir / f"probe-{stamp}.json"
    out_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nwrote {out_path}")

    failed = [r for r in results if r.get("status") == "error"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
