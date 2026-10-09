#!/usr/bin/env python3.11
"""List IDs from the selected construction providers; does not issue inference requests."""

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error

from clinical_orchestra.construction.api import models_from_file
from discover_models import fetch, model_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(Path(__file__).resolve().parents[1] / "construction_models.toml"))
    parser.add_argument("--models", nargs="+")
    parser.add_argument("--filter")
    args = parser.parse_args()
    specs = models_from_file(args.registry)
    if args.models:
        if set(args.models) - {m.key for m in specs}:
            parser.error("unknown construction model key")
        specs = [m for m in specs if m.key in args.models]
    failed = False
    seen = set()
    for model in specs:
        spec = model.spec
        key = os.getenv(spec.api_key_env)
        if not key:
            print(json.dumps({"provider": spec.provider, "status": "missing_key", "env": spec.api_key_env}))
            continue
        endpoint = spec.base_url.rstrip("/") + "/models"
        if (endpoint, spec.api_key_env) in seen:
            continue
        seen.add((endpoint, spec.api_key_env))
        try:
            ids = model_ids(fetch(endpoint, key, "bearer"))
            print(json.dumps({"provider": spec.provider, "status": "ok", "endpoint": endpoint,
                              "ids": [i for i in ids if not args.filter or args.filter in i]}))
        except urllib.error.HTTPError as exc:
            failed = True
            print(json.dumps({"provider": spec.provider, "status": "http_error", "code": exc.code}))
        except Exception as exc:
            failed = True
            print(json.dumps({"provider": spec.provider, "status": "error", "type": type(exc).__name__}))
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
