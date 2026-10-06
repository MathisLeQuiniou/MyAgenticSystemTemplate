"""Load the model profiles (backend/config/models.yaml).

Shared by the LLM clients (`backend/infra/llm/llm_clients.py`), the run service
(profile validation) and the API (`GET /models`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.config.settings import get_settings
from backend.utils import load_yaml


class ModelProfile(BaseModel):
    """How to reach one model. Loaded from `backend/config/models.yaml`."""

    name: str
    provider: Literal["openai", "ollama", "fake"]
    model: str
    base_url: str | None = None
    api_key: str | None = None  # inline key (avoid; prefer api_key_env)
    api_key_env: str | None = None  # name of the env var holding the key
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: float | None = 60
    max_retries: int = 2
    default_headers: dict[str, str] = Field(default_factory=dict)
    ca_bundle: str | None = None  # custom CA (.pem) for corporate TLS
    verify_ssl: bool = True
    proxy: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)  # passed as-is to the LangChain class


class ModelsConfig(BaseModel):
    default: str
    profiles: dict[str, ModelProfile]


@lru_cache
def load_models_config() -> ModelsConfig:
    settings = get_settings()
    raw = load_yaml(settings.models_config_path)
    profiles = {name: ModelProfile(name=name, **(cfg or {})) for name, cfg in raw.get("profiles", {}).items()}
    default = settings.default_model_profile or raw.get("default") or next(iter(profiles))
    if default not in profiles:
        raise ValueError(f"Default model profile '{default}' is not defined in {settings.models_config_path}")
    return ModelsConfig(default=default, profiles=profiles)


def get_profile(name: str | None = None) -> ModelProfile:
    cfg = load_models_config()
    name = name or cfg.default
    try:
        return cfg.profiles[name]
    except KeyError:
        raise KeyError(f"Unknown model profile '{name}'. Available: {', '.join(cfg.profiles)}") from None
