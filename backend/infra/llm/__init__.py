"""LLM clients: build the LangChain chat model of a profile from config/models.yaml.

- llm_clients: one builder per provider (openai, ollama, fake), cached per profile
- fake:        deterministic offline chat model (provider "fake")
"""

from backend.infra.llm.llm_clients import get_chat_model

__all__ = ["get_chat_model"]
