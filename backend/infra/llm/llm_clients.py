"""LLM clients: one entry point (`get_chat_model`) for every chat model used by the agents.

Builds the LangChain client of a model profile (HTTP client, TLS, proxy, retries...).
Profiles are loaded by `backend.config.models`.
"""

from __future__ import annotations

import os
from functools import lru_cache

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from backend.config import ModelProfile, get_profile


def _resolve_api_key(profile: ModelProfile) -> str | None:
    if profile.api_key:
        return profile.api_key
    if profile.api_key_env:
        return os.environ.get(profile.api_key_env)
    return None


def _httpx_kwargs(profile: ModelProfile) -> dict:
    verify: bool | str = profile.ca_bundle if profile.ca_bundle else profile.verify_ssl
    kwargs: dict = {"verify": verify, "timeout": profile.timeout}
    if profile.proxy:
        kwargs["proxy"] = profile.proxy
    return kwargs


def _build_openai(profile: ModelProfile) -> BaseChatModel:

    httpx_kwargs = _httpx_kwargs(profile)
    kwargs = dict(
        model=profile.model,
        api_key=_resolve_api_key(profile) or "not-needed",
        base_url=profile.base_url or None,
        timeout=profile.timeout,
        max_retries=profile.max_retries,
        default_headers={k: v for k, v in profile.default_headers.items() if v} or None,
        http_client=httpx.Client(**httpx_kwargs),
        http_async_client=httpx.AsyncClient(**httpx_kwargs),
        stream_usage=True,
    )
    if profile.temperature is not None:
        kwargs["temperature"] = profile.temperature
    if profile.max_tokens is not None:
        kwargs["max_tokens"] = profile.max_tokens
    return ChatOpenAI(**kwargs, **profile.extra)


def _build_ollama(profile: ModelProfile) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    client_kwargs: dict = {"timeout": profile.timeout}
    if profile.default_headers:
        client_kwargs["headers"] = {k: v for k, v in profile.default_headers.items() if v}
    kwargs = dict(
        model=profile.model,
        base_url=profile.base_url or "http://localhost:11434",
        client_kwargs=client_kwargs,
    )
    if profile.temperature is not None:
        kwargs["temperature"] = profile.temperature
    if profile.max_tokens is not None:
        kwargs["num_predict"] = profile.max_tokens
    return ChatOllama(**kwargs, **profile.extra)


def _build_fake(profile: ModelProfile) -> BaseChatModel:
    from backend.infra.llm.fake import FakeToolCallingChatModel

    return FakeToolCallingChatModel(model_name=profile.model)


_BUILDERS = {"openai": _build_openai, "ollama": _build_ollama, "fake": _build_fake}


@lru_cache(maxsize=32)
def get_chat_model(profile_name: str | None = None) -> BaseChatModel:
    """Return a (cached) LangChain chat model for a profile of models.yaml."""
    profile = get_profile(profile_name)
    return _BUILDERS[profile.provider](profile)
