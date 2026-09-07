#!/usr/bin/env python3.11
"""Estimate what a run costs, using the real sizes measured from the cached corpus.

Prices come from pricing.toml and go stale quickly; the report prints the date each was checked.
Token counts are estimated at ~4 characters per token, which is close enough for budgeting and is
labelled as an estimate everywhere it appears. Reasoning tokens are billed at the output rate and
are not visible in advance, so a multiplier is applied and stated.

Usage:
  PYTHONPATH=src python3.11 scripts/estimate_cost.py --cases 200
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
import tomllib
from pathlib import Path

CHARS_PER_TOKEN = 4.0


def tokens(chars: float) -> float:
    return chars / CHARS_PER_TOKEN


def measure() -> dict:
    """Real sizes from the corpus on disk, so the estimate is not made up."""
    cases = [json.load(open(path)) for path in glob.glob("data/cases/*.json")]
    timelines = [json.load(open(path)) for path in glob.glob("data/timelines/*.json")]
    items = [json.loads(line) for line in open("data/items.jsonl")]
    return {
        "case_chars": statistics.mean(c["n_chars"] for c in cases),
        "extract_out_chars": statistics.mean(len(json.dumps(t)) for t in timelines),
        "item_prompt_chars": statistics.mean(len(i["state"]) + len(i["question"]) for i in items),
        "items_per_case": len(items) / len(timelines),
        "shared_prefix_chars": statistics.mean(len(t["presentation"]) for t in timelines),
    }


def cost(price: dict, in_tok: float, out_tok: float, cached_tok: float = 0.0) -> float:
    cached_rate = price.get("cached_in", price["input"])
    return (
        (in_tok - cached_tok) * price["input"] / 1e6
        + cached_tok * cached_rate / 1e6
        + out_tok * price["output"] / 1e6
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=200, help="corpus size to price")
    parser.add_argument("--samples", type=int, default=1, help="samples per item (self-consistency)")
    parser.add_argument(
        "--answer-chars", type=int, default=400, help="expected answer length per item"
    )
    parser.add_argument(
        "--reasoning-multiplier",
        type=float,
        default=3.0,
        help="output tokens billed per visible output token, for models that think",
    )
    parser.add_argument("--extraction-prompt-chars", type=int, default=2800)
    args = parser.parse_args()

    m = measure()
    prices = tomllib.loads(Path("pricing.toml").read_text())

    n_items = args.cases * m["items_per_case"]

    print(f"measured from the corpus on disk (~{CHARS_PER_TOKEN:.0f} chars/token):")
    print(f"  case text            {m['case_chars']:>8.0f} chars  ~{tokens(m['case_chars']):>6.0f} tok")
    print(f"  extraction output    {m['extract_out_chars']:>8.0f} chars  ~{tokens(m['extract_out_chars']):>6.0f} tok")
    print(f"  eval prompt per item {m['item_prompt_chars']:>8.0f} chars  ~{tokens(m['item_prompt_chars']):>6.0f} tok")
    print(f"  items per case       {m['items_per_case']:>8.1f}")
    print()
    print(f"pricing a corpus of {args.cases} cases = {n_items:,.0f} items, "
          f"{args.samples} sample(s) per item")
    print(f"reasoning multiplier {args.reasoning_multiplier}x on output tokens\n")

    ex_in = tokens(m["case_chars"] + args.extraction_prompt_chars)
    ex_out = tokens(m["extract_out_chars"])
    ev_in = tokens(m["item_prompt_chars"])
    ev_out = tokens(args.answer_chars) * args.reasoning_multiplier
    cached = tokens(m["shared_prefix_chars"])

    header = f"{'model':<28}{'extract':>10}{'eval':>12}{'total':>12}   note"
    print(header)
    print("-" * len(header))
    rows = []
    for key, price in prices.items():
        extract = cost(price, ex_in * args.cases, ex_out * args.cases)
        evaluate = cost(
            price, ev_in * n_items * args.samples, ev_out * n_items * args.samples,
            cached_tok=cached * n_items * args.samples,
        )
        rows.append((extract + evaluate, key, extract, evaluate, price))
    for total, key, extract, evaluate, price in sorted(rows):
        flag = "  <-- see note" if "DO NOT USE" in price.get("note", "") else ""
        print(f"{key:<28}{'$'+format(extract,'.2f'):>10}{'$'+format(evaluate,'.2f'):>12}"
              f"{'$'+format(total,'.2f'):>12}   checked {price['checked']}{flag}")

    print("\nnotes:")
    for key, price in prices.items():
        if price.get("note"):
            print(f"  {key}: {price['note']}")
    print("\nEstimates only. Character-based token counts, and one eval pass per item with no "
          "retries. Extraction is a one-time cost per case; evaluation repeats for every model "
          "and every harness condition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
