from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from backend.agentic.agents.base import BaseAgent, load_prompt
from backend.agentic.skills import get_skill_registry, make_skill_tools, skills_catalog
from backend.agentic.states import AgentLoopState


class LLMAgent(BaseAgent):
    """An LLM with a system prompt and (optionally) tools.

    - Without tools: a single model call, the answer is appended to `messages`.
    - With tools: a ReAct loop compiled as a *subgraph* `agent <-> tools`, so each
      tool call shows up as a step of the graph path in the traces.
      After `max_iterations` model calls, tools are unbound to force an answer.
    - With skills (names of folders in `backend/skills/`, or `["*"]`): the skills
      catalog is appended to the system prompt and the `load_skill` /
      `read_skill_file` tools are added, so the agent loads instructions on demand.
    """

    def __init__(
        self,
        name: str,
        prompt: str,
        tools: Sequence[BaseTool] = (),
        *,
        skills: Sequence[str] = (),
        description: str = "",
        model_profile: str | None = None,
        max_iterations: int = 6,
    ) -> None:
        super().__init__(name, description, model_profile)
        self.prompt_template = load_prompt(prompt)
        self.skills = get_skill_registry().get_many(tuple(skills)) if skills else []
        self.tools = [*tools, *(make_skill_tools(self.skills) if self.skills else [])]
        self.max_iterations = max_iterations

    # -- customisation points --------------------------------------------------
    def format_prompt(self, state: dict[str, Any]) -> str:
        """Fill the prompt template. Override to inject values from the state."""
        prompt = self.prompt_template.replace("{today}", self.today())
        if self.skills:
            prompt += "\n\n" + skills_catalog(self.skills)
        return prompt

    def build_messages(self, state: dict[str, Any]) -> list[BaseMessage]:
        return [SystemMessage(self.format_prompt(state)), *state["messages"]]

    # -- execution -------------------------------------------------------------
    async def run(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        iterations = state.get("iterations", 0)
        model = self.get_model(config)
        if self.tools and iterations < self.max_iterations:
            model = model.bind_tools(self.tools)
        response = await model.ainvoke(self.build_messages(state), config)
        response.name = self.name
        if isinstance(response, AIMessage) and isinstance(response.content, str):
            response.content = strip_thinking(response.content)
        update: dict[str, Any] = {"messages": [response]}
        if self.tools:
            update["iterations"] = 1
        return update

    def as_node(self) -> Any:
        if not self.tools:
            return super().as_node()
        loop = StateGraph(AgentLoopState)
        loop.add_node("agent", super().as_node())
        loop.add_node("tools", ToolNode(self.tools, handle_tool_errors=True))
        loop.add_edge(START, "agent")
        loop.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
        loop.add_edge("tools", "agent")
        return loop.compile(name=self.name)


_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks produced by reasoning models (qwen3, deepseek-r1...)."""
    return _THINK_RE.sub("", text).strip()
