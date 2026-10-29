"""Deep agent: a `deepagents.create_deep_agent()` graph used as a node of a template graph.

A deep agent is a full LangGraph agent (planning with `write_todos`, a virtual
filesystem, `task` subagents, skills...). `DeepAgent` builds it with the
template's building blocks (prompts, tools, `SkillRegistry` skills, model
profiles) and `as_node()` returns the compiled graph, so it is added to a
`StateGraph` like any other agent and shows up as a subgraph:

    builder.add_node(agent.name, agent.as_node())   # nodes "<name>:model", "<name>:tools"...

The parent graph shares `messages` with it. To keep the planning and the
virtual files in the parent state (visible in `/state`, kept from one turn of
a thread to the next), use `DeepAgentHostState` (or add its keys to your state).

Differences with `LLMAgent`:
- The system prompt is fixed when the agent is built (no `{today}`, no `format_prompt`).
- The model of the run (`model_profile` chosen in the UI / API) is applied
  by a middleware on every model call of the agent and of its subagents
  (the summarization middleware keeps the model the agent was built with).
- Skills are read from disk (read-only) through the deep agent's own
  filesystem: the agent opens `/skills/<name>/SKILL.md` with `read_file`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
import re

from deepagents import FilesystemPermission, SubAgent, create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import LsResult
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse, TodoListMiddleware
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import BaseTool
from langgraph.config import get_config
from langgraph.graph.state import CompiledStateGraph

from backend.agentic.agents.base import BaseAgent, load_prompt
from backend.agentic.skills import Skill
from backend.infra.llm import get_chat_model

SKILLS_ROUTE = "/skills/"
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]\w*)\}")


class RunModelMiddleware(AgentMiddleware):
    """Use the run's `model_profile` (config["configurable"]) instead of the build-time model."""

    def __init__(self, default_profile: str | None = None) -> None:
        super().__init__()
        self.default_profile = default_profile

    def _resolve(self, request: ModelRequest) -> ModelRequest:
        try:
            profile = (get_config().get("configurable") or {}).get("model_profile")
        except RuntimeError:  # called outside of a runnable context
            return request
        if not profile or profile == self.default_profile:
            return request
        return request.override(model=get_chat_model(profile))

    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
        return handler(self._resolve(request))

    async def awrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]
    ) -> ModelResponse:
        return await handler(self._resolve(request))


class _SkillsBackend(FilesystemBackend):
    """Skills folder on disk, listing only the skills given to the agent."""

    def __init__(self, root: Path, allowed: set[str]) -> None:
        super().__init__(root_dir=root, virtual_mode=True)
        self.allowed = allowed

    def ls(self, path: str) -> LsResult:
        result = super().ls(path)
        if result.entries is not None and path.strip("/") == "":
            return LsResult(entries=[e for e in result.entries if PurePosixPath(e["path"]).name in self.allowed])
        return result


class DeepAgent(BaseAgent):
    """A deep agent (`deepagents`) built from the template's prompts, tools, skills and model profiles.

    Args:
        name: node name in the parent graph.
        prompt: system prompt, `prompts/<name>.md` or plain text.
        tools: extra tools (local / MCP), added to the deep agent's built-in ones.
        skills: skills of the graph's `SkillRegistry` (e.g. `self.skills.get_many("my-skill")`).
        subagents: `deepagents.SubAgent` specs, called through the `task` tool.
        middleware: extra LangChain agent middleware.
        planning: add `TodoListMiddleware` (the `write_todos` tool). Not a
            default of `create_deep_agent` anymore.
        **deep_agent_kwargs: any other `create_deep_agent()` argument
            (`interrupt_on`, `memory`, `response_format`...).
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        tools: Sequence[BaseTool] = (),
        *,
        skills: Sequence[Skill] = (),
        subagents: Sequence[SubAgent] = (),
        middleware: Sequence[AgentMiddleware] = (),
        planning: bool = True,
        description: str = "",
        model_profile: str | None = None,
        **deep_agent_kwargs: Any,
    ) -> None:
        super().__init__(name, description, model_profile)
        self.prompt_template = load_prompt(prompt)
        self.tools = list(tools)
        self.skills = list(skills)
        self.subagents = list(subagents)
        self.middleware = [*([TodoListMiddleware()] if planning else []), *middleware]
        self.deep_agent_kwargs = deep_agent_kwargs
        self._agent: CompiledStateGraph | None = None
        self._last_formatted: str | None = None

    # -- customisation points ----------------------------------------------------
    def format_prompt(self, state: dict[str, Any]) -> str:
        """Generic placeholder replacement method"""
        prompt = self.prompt_template
        def repl(m: re.Match) -> str:
            key = m.group(1)
            if key in state:
                return str(state[key])
            return m.group(0)

        return _PLACEHOLDER_RE.sub(repl, prompt)


    # -- construction ------------------------------------------------------------
    def _skills_setup(self) -> dict[str, Any]:
        """Backend, skill sources and permissions exposing the skills read-only under /skills/."""
        if not self.skills:
            return {}
        roots = {s.path.parent.resolve() for s in self.skills}
        if len(roots) != 1:
            raise ValueError(f"{self.name}: all skills must live in the same folder, got {sorted(map(str, roots))}")
        names = {s.name for s in self.skills}
        backend = CompositeBackend(default=StateBackend(), routes={SKILLS_ROUTE: _SkillsBackend(roots.pop(), names)})
        permissions = [
            FilesystemPermission(operations=["read"], paths=[f"{SKILLS_ROUTE}{n}/**" for n in sorted(names)]),
            FilesystemPermission(operations=["read", "write"], paths=[f"{SKILLS_ROUTE}**"], mode="deny"),
        ]
        return {"backend": backend, "skills": [SKILLS_ROUTE], "permissions": permissions}

    def _subagents_with_run_model(self, run_model: RunModelMiddleware, skill_sources: list[str] | None) -> list[SubAgent]:
        """Make subagents follow the run's model too (unless a spec sets its own `model`)."""
        specs: list[SubAgent] = []
        for spec in self.subagents:
            spec = dict(spec)  # type: ignore[assignment]
            if "model" not in spec:
                spec["middleware"] = [*spec.get("middleware", []), run_model]
            specs.append(spec)  # type: ignore[arg-type]
        if not any(s["name"] == GENERAL_PURPOSE_SUBAGENT["name"] for s in specs):
            # Explicit copy of the default general-purpose subagent, to add the middleware.
            general: SubAgent = {**GENERAL_PURPOSE_SUBAGENT, "tools": self.tools, "middleware": [run_model]}
            if skill_sources:
                general["skills"] = skill_sources
            specs.append(general)
        return specs

    def build(self, state: dict[str, Any]) -> CompiledStateGraph:
        setup = self._skills_setup()
        kwargs = dict(self.deep_agent_kwargs)
        if "permissions" in setup:
            setup["permissions"] += list(kwargs.pop("permissions", None) or [])
        
        run_model = RunModelMiddleware(self.model_profile)
        
        system_prompt = self.format_prompt(state)
        
        return create_deep_agent(
            model=get_chat_model(self.model_profile),
            tools=self.tools,
            system_prompt=system_prompt,
            middleware=[*self.middleware, run_model],
            subagents=self._subagents_with_run_model(run_model, setup.get("skills")),
            name=self.name,
            **setup,
            **kwargs,
        )

    @property
    def agent(self) -> CompiledStateGraph:
        if self._agent is None:
            # empty state for compulation, will be replaced later
            self._agent = self.build(state={})
        return self._agent

    # -- LangGraph integration -------------------------------------------------
    def as_node(self) -> CompiledStateGraph:
        """The compiled deep agent: a subgraph whose steps and calls are all traced."""
        async def _invoke(state: dict [str, Any], config: RunnableConfig) -> dict[str, Any]:
            formatted = self.format_prompt(state)
            if formatted != self._last_formatted:
                self._last_formatted = formatted
                self._agent = self.build(state)
            return await self._agent.ainvoke(state, config)

        return RunnableLambda(_invoke)

    async def run(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        """Standalone use (outside a graph); in a graph, prefer `as_node()`."""
        formatted = self.format_prompt(state)
        if formatted != self._last_formatted:
            self._last_formatted = formatted
            self._agent = self.build(state)

        return await self.agent.ainvoke(state, config)
