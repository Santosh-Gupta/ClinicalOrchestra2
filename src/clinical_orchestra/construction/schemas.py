"""Small explicit JSON contracts; validation uses only the subset defined here."""

from __future__ import annotations

import math


def obj(**fields):
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def arr(items, minimum=0, maximum=1000):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


def enum(*values):
    return {"type": "string", "enum": list(values)}


TEXT = {"type": "string", "minLength": 1}
NULL_TEXT = {"type": ["string", "null"], "minLength": 1}
STRINGS = arr(TEXT)
EVIDENCE = arr(obj(span_id=TEXT, quote=TEXT), maximum=30)
KINDS = enum("context", "action", "result", "diagnosis", "progression", "response")
FACT = obj(
    id=TEXT, patient_id=enum("patient"), kind=KINDS, claim=TEXT, evidence=EVIDENCE,
    clinical_time=obj(description=TEXT, evidence=EVIDENCE), clinical_after=STRINGS,
    known_phase=NULL_TEXT, known_evidence=EVIDENCE,
    status=enum("observed", "ordered", "performed", "pending", "considered", "confirmed", "corrected", "canceled"),
    linked_action_id=NULL_TEXT, endpoint=NULL_TEXT, endpoint_evidence=EVIDENCE,
)
EXTRACT = obj(
    phases=arr(obj(id=TEXT, rank={"type": "integer", "minimum": 0}, evidence=EVIDENCE), 1, 100),
    facts=arr(FACT, 1, 150),
    coverage=arr(obj(span_id=TEXT, fact_ids=STRINGS,
                     disposition=enum("represented", "not_patient_information", "unresolved"), reason=TEXT)),
    thesis=arr(obj(claim=TEXT, evidence=EVIDENCE, fact_ids=STRINGS), maximum=3),
    unresolved=STRINGS,
)
BLIND = obj(defects=STRINGS, missing_variables=STRINGS, alternatives=arr(TEXT, 3, 7))
VERDICT = enum("supported", "contradicted", "unknown")
AUDIT = obj(
    fact_reviews=arr(obj(fact_id=TEXT, verdict=VERDICT, evidence=EVIDENCE, reason=TEXT)),
    phase_reviews=arr(obj(phase_id=TEXT, verdict=VERDICT, evidence=EVIDENCE, reason=TEXT)),
    coverage_reviews=arr(obj(span_id=TEXT, verdict=VERDICT, reason=TEXT)),
    item_reviews=arr(obj(item_id=TEXT, verdict=VERDICT, answer_id=NULL_TEXT,
                         evidence=EVIDENCE, visible_fact_ids_checked=STRINGS,
                         defects=STRINGS, reason=TEXT)),
    hard_defects=STRINGS, unresolved=STRINGS,
)
SCHEMAS = {"extract": EXTRACT, "blind": BLIND, "audit": AUDIT}


class ContractError(ValueError):
    """An output is unusable; no coercion or silent field dropping is allowed."""


def validate(value, schema, path="$"):
    types = schema["type"]
    types = [types] if isinstance(types, str) else types
    def matches(kind):
        return {"object": isinstance(value, dict), "array": isinstance(value, list),
                "string": isinstance(value, str), "null": value is None,
                "integer": type(value) is int, "number": type(value) in (int, float),
                "boolean": type(value) is bool}[kind]
    if not any(matches(kind) for kind in types):
        raise ContractError(f"{path}: expected {types}")
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: invalid enum {value!r}")
    if isinstance(value, dict):
        fields = schema["properties"]
        if set(value) != set(fields):
            raise ContractError(f"{path}: missing={sorted(set(fields)-set(value))}, extra={sorted(set(value)-set(fields))}")
        for key, child in fields.items():
            validate(value[key], child, f"{path}.{key}")
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 1000):
            raise ContractError(f"{path}: invalid array length {len(value)}")
        for index, child in enumerate(value):
            validate(child, schema["items"], f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            raise ContractError(f"{path}: empty text")
    elif type(value) in (int, float):
        if not math.isfinite(value) or value < schema.get("minimum", -math.inf):
            raise ContractError(f"{path}: invalid number")
