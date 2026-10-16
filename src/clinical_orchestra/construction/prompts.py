"""Versioned, editable prompts with content hashes in every request."""

from importlib.resources import files

from . import VERSION
from .evidence import canonical, digest
from .schemas import SCHEMAS


def prompt_text(name):
    if name not in {"system", "extract", "blind", "audit", "specialty"}:
        raise ValueError(f"unknown prompt {name}")
    return files("clinical_orchestra.construction").joinpath("prompts", f"{name}.txt").read_text(encoding="utf-8")


def render(stage, payload):
    schema = SCHEMAS[stage]
    # Stable instruction/schema prefix; source or visible-state data comes last.
    prompt = prompt_text(stage) + "\nOUTPUT JSON SCHEMA:\n" + canonical(schema) + "\nINPUT DATA:\n" + canonical(payload)
    return {"version": VERSION, "stage": stage, "system": prompt_text("system"),
            "prompt": prompt, "schema_hash": digest(schema),
            "prompt_hash": digest([prompt_text("system"), prompt_text(stage), schema])}
