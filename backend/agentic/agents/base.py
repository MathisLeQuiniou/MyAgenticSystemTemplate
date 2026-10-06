"""Agent base classes.

An agent is a LangGraph node with a name. `as_node()` returns what you pass to
`StateGraph.add_node(agent.name, agent.as_node())`: a plain async function, or a
compiled subgraph for agents with an internal loop (see `LLMAgent`).
"""

from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from backend.infra.llm import get_chat_model
from backend.config import PROMPTS_DIR


def load_prompt(name_or_text: str) -> str:
    """Return `backend/prompts/<name>.md` if it exists, else the string itself."""
    path = PROMPTS_DIR / f"{name_or_text}.md"
    if len(name_or_text) < 100 and path.exists():
        return path.read_text(encoding="utf-8").strip()
    return name_or_text


_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks produced by reasoning models (qwen3, deepseek-r1...)."""
    return _THINK_RE.sub("", text).strip()


class BaseAgent(ABC):
    """Minimal contract shared by every agent."""

    def __init__(self, name: str, description: str = "", model_profile: str | None = None) -> None:
        self.name = name
        self.description = description
        self.model_profile = model_profile

    # -- to implement --------------------------------------------------------
    @abstractmethod
    async def run(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        """Read the state, do the work, return a *partial* state update."""

    # -- LangGraph integration -------------------------------------------------
    def as_node(self) -> Any:
        async def node(state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
            return await self.run(state, config) or {}

        node.__name__ = self.name
        return node

    # -- helpers -----------------------------------------------------------------
    def get_model(self, config: RunnableConfig | None = None) -> BaseChatModel:
        """Model for this call: run-level override > agent profile > default profile."""
        override = ((config or {}).get("configurable") or {}).get("model_profile")
        return get_chat_model(override or self.model_profile)

    @staticmethod
    async def emit(name: str, data: dict[str, Any], config: RunnableConfig | None = None) -> None:
        """Emit a custom trace event (shown in the run timeline).

        Dispatched as a LangChain custom event, then turned into a `custom` TraceEvent
        by `backend.services.tracing.TraceCollector`, attached to the open node span.
        Pass the node's `config` so the event keeps its LangGraph namespace (node_path).
        """
        await adispatch_custom_event(name, data, config=config)

    @staticmethod
    def today() -> str:
        return dt.date.today().isoformat()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"
