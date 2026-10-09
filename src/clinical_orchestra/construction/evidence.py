"""Source indexing and mechanical provenance/chronology checks, not semantic certification."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from .schemas import ContractError, EXTRACT, validate


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def indexed_source(record):
    required = {"case_id", "case_group", "split", "case_text", "source"}
    if not required <= set(record):
        raise ContractError(f"case record requires {sorted(required)}; explicitly assign splits before construction")
    if record["split"] not in {"development", "test", "synthetic"}:
        raise ContractError("split must be development, test or synthetic")
    for field in ("case_id", "case_group", "case_text"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise ContractError(f"invalid {field}")
    if not isinstance(record["source"], dict):
        raise ContractError("source must be an object")
    text = record["case_text"]
    spans = []
    for match in re.finditer(r"\S.*?(?=\n\s*\n|\Z)", text, re.S):
        end = match.end()
        while end > match.start() and text[end-1].isspace():
            end -= 1
        spans.append({"id": f"p{len(spans):04d}", "start": match.start(), "end": end,
                      "text": text[match.start():end]})
    if not spans:
        raise ContractError("empty source")
    return {**record, "source_hash": digest(text), "spans": spans}


def check_evidence(refs, source, *, required=True):
    if required and not refs:
        raise ContractError("missing supporting evidence")
    spans = {span["id"]: span for span in source["spans"]}
    resolved = []
    for ref in refs:
        span = spans.get(ref["span_id"])
        if span is None or ref["quote"] not in span["text"]:
            raise ContractError(f"quote absent from source span {ref['span_id']}")
        offset = span["text"].index(ref["quote"])
        resolved.append({**ref, "start": span["start"] + offset,
                         "end": span["start"] + offset + len(ref["quote"])})
    return resolved


def unique_index(rows, key, expected=None):
    counts = Counter(row[key] for row in rows)
    if any(count != 1 for count in counts.values()):
        raise ContractError(f"duplicate {key}")
    if expected is not None and set(counts) != set(expected):
        raise ContractError(f"{key} coverage mismatch: missing={sorted(set(expected)-set(counts))}, extra={sorted(set(counts)-set(expected))}")
    return {row[key]: row for row in rows}


def check_graph(graph, source):
    validate(graph, EXTRACT)
    facts = unique_index(graph["facts"], "id")
    phases = unique_index(graph["phases"], "id")
    ranks = [phase["rank"] for phase in phases.values()]
    if sorted(ranks) != list(range(len(phases))):
        raise ContractError("knowledge phase ranks must be unique and contiguous from zero")
    for phase in phases.values():
        check_evidence(phase["evidence"], source)
    for fact in facts.values():
        check_evidence(fact["evidence"], source)
        check_evidence(fact["clinical_time"]["evidence"], source,
                       required=fact["clinical_time"]["description"] != "unknown")
        if fact["known_phase"] is not None:
            if fact["known_phase"] not in phases:
                raise ContractError("unknown knowledge phase")
            check_evidence(fact["known_evidence"], source)
        elif fact["known_evidence"]:
            check_evidence(fact["known_evidence"], source)
        if fact["endpoint"] is not None:
            check_evidence(fact["endpoint_evidence"], source)
        for earlier in fact["clinical_after"]:
            if earlier not in facts or earlier == fact["id"]:
                raise ContractError("invalid clinical ordering reference")
        link = fact["linked_action_id"]
        if link is not None and (link not in facts or facts[link]["kind"] != "action"):
            raise ContractError("result/response link does not identify an action")
    visited, visiting = set(), set()
    def visit(fact_id):
        if fact_id in visiting:
            raise ContractError("cycle in clinical chronology")
        if fact_id in visited:
            return
        visiting.add(fact_id)
        for earlier in facts[fact_id]["clinical_after"]:
            visit(earlier)
        visiting.remove(fact_id)
        visited.add(fact_id)
    for fact_id in facts:
        visit(fact_id)
    coverage = unique_index(graph["coverage"], "span_id", [s["id"] for s in source["spans"]])
    for span_id, row in coverage.items():
        if any(f not in facts for f in row["fact_ids"]):
            raise ContractError("coverage points at nonexistent fact")
        if row["disposition"] == "represented" and not row["fact_ids"]:
            raise ContractError("represented source span has no facts")
        if row["disposition"] != "represented" and row["fact_ids"]:
            raise ContractError("excluded source span has contradictory coverage")
        for fact_id in row["fact_ids"]:
            if span_id not in {r["span_id"] for r in facts[fact_id]["evidence"]}:
                raise ContractError("coverage mapping lacks the referenced source support")
    for thesis in graph["thesis"]:
        check_evidence(thesis["evidence"], source)
        if not set(thesis["fact_ids"]) <= set(facts):
            raise ContractError("thesis references unknown fact")
    return graph
