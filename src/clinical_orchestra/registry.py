"""Load the model registry and build clients from it.

The registry lives in `models.toml` so that adding a newly released model is a data change, not a
code change. Nothing else in the codebase should hardcode a model ID or a base URL.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .model_client import OpenAICompatibleChatClient, OpenAIResponsesClient

DEFAULT_REGISTRY = Path(__file__).resolve().parents[2] / "models.toml"


@dataclass(frozen=True)
class ModelSpec:
    key: str
    provider: str
    model_id: str
    base_url: str
    api_key_env: str
    api: str  # "chat" or "responses"
    tier: str  # "cheap" or "expensive"
    enabled: bool
    notes: str = ""

    @property
    def has_key(self) -> bool:
        return bool(os.getenv(self.api_key_env))


def load_registry(path: str | Path | None = None) -> list[ModelSpec]:
    registry_path = Path(path) if path else DEFAULT_REGISTRY
    data = tomllib.loads(registry_path.read_text(encoding="utf-8"))
    specs = [
        ModelSpec(
            key=entry["key"],
            provider=entry["provider"],
            model_id=entry["model_id"],
            base_url=entry["base_url"],
            api_key_env=entry["api_key_env"],
            api=entry["api"],
            tier=entry["tier"],
            enabled=bool(entry.get("enabled", False)),
            notes=entry.get("notes", ""),
        )
        for entry in data.get("model", [])
    ]
    keys = [spec.key for spec in specs]
    duplicates = {key for key in keys if keys.count(key) > 1}
    if duplicates:
        raise ValueError(f"duplicate model keys in {registry_path}: {sorted(duplicates)}")
    return specs


def select(
    specs: list[ModelSpec],
    *,
    tier: str | None = None,
    keys: list[str] | None = None,
    require_key: bool = True,
) -> list[ModelSpec]:
    """Pick models to run. Skips disabled entries, and by default those with no API key set."""
    chosen = [spec for spec in specs if spec.enabled]
    if tier:
        chosen = [spec for spec in chosen if spec.tier == tier]
    if keys:
        wanted = set(keys)
        unknown = wanted - {spec.key for spec in specs}
        if unknown:
            raise ValueError(f"unknown model keys: {sorted(unknown)}")
        chosen = [spec for spec in specs if spec.key in wanted]
    if require_key:
        chosen = [spec for spec in chosen if spec.has_key]
    return chosen


def build_client(spec: ModelSpec, *, system_prompt: str, timeout_seconds: float = 300.0):
    """Return a client for this model. Raises if the key is missing rather than failing later."""
    api_key = os.getenv(spec.api_key_env)
    if not api_key:
        raise ValueError(f"{spec.key}: {spec.api_key_env} is not set")
    if spec.api == "responses":
        return OpenAIResponsesClient(
            api_key=api_key,
            base_url=spec.base_url,
            model=spec.model_id,
            timeout_seconds=timeout_seconds,
            system_prompt=system_prompt,
        )
    return OpenAICompatibleChatClient(
        api_key=api_key,
        base_url=spec.base_url,
        model=spec.model_id,
        timeout_seconds=timeout_seconds,
        system_prompt=system_prompt,
    )
