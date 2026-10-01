"""Example graph: router -> (researcher with tools) -> writer.

    START -> router --research--> researcher[agent <-> tools] -> writer -> END
                    \--direct----------------------------------> writer

- `router`: RouterAgent choosing between a tool-assisted answer and a direct one.
- `researcher`: LLMAgent with local + MCP tools (a subgraph with a tool loop)
  and the `financial-calculations` skill (loaded on demand).
- `writer`: LLMAgent without tools that writes the final answer.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from typing_extensions import NotRequired

from backend.agentic.agents import LLMAgent, RouterAgent
from backend.agentic.graphs.base import BaseGraph
from backend.agentic.graphs.registry import register_graph
from backend.agentic.states import BaseState


class ResearchAssistantState(BaseState):
    route: NotRequired[str]


@register_graph
class ResearchAssistantGraph(BaseGraph):
    name = "research_assistant"
    description = "Router -> researcher (tools: knowledge base, calculator, clock) -> writer."
    state_schema = ResearchAssistantState

    def build(self) -> StateGraph:
        router = RouterAgent(
            "router",
            routes={
                "research": "the question needs facts, documentation, a calculation or the current date/time",
                "direct": "small talk or a question that can be answered directly without any tool",
            },
            default="research",
        )
        researcher = LLMAgent(
            "researcher",
            prompt="researcher",
            tools=self.tools.get("search_knowledge_base", "calculate", "get_current_time"),
            skills=["financial-calculations"],
        )
        writer = LLMAgent("writer", prompt="writer")

        builder = StateGraph(self.state_schema)
        for agent in (router, researcher, writer):
            builder.add_node(agent.name, agent.as_node())
        builder.add_edge(START, router.name)
        builder.add_conditional_edges(router.name, router.route, {"research": researcher.name, "direct": writer.name})
        builder.add_edge(researcher.name, writer.name)
        builder.add_edge(writer.name, END)
        return builder
