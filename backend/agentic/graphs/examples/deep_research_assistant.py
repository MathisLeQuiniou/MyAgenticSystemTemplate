"""Example graph: a deep agent (`deepagents`) used as a node.

    START -> deep_researcher[model <-> tools (+ middleware nodes)] -> END

- `deep_researcher`: `DeepAgent` with the same tools and skill as the
  `research_assistant` researcher, plus the deep agent's built-in tools:
  planning (`write_todos`), virtual files (`ls`, `read_file`, `write_file`,
  `edit_file`, `glob`, `grep`) and subagents (`task`).
- `DeepAgentHostState` keeps the deep agent's `todos` and `files` in the graph
  state (visible in `/state` and in the run output).

The deep agent is a subgraph like any other node: add routers, writers or
other agents around it with regular edges.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.agentic.agents import DeepAgent
from backend.agentic.graphs.base import BaseGraph
from backend.agentic.graphs.graphs_registry import register_graph
from backend.agentic.states import DeepAgentHostState


@register_graph
class DeepResearchAssistantGraph(BaseGraph):
    name = "deep_research_assistant"
    description = "Deep agent (planning, virtual files, subagents) with the knowledge base, calculator and clock tools."
    state_schema = DeepAgentHostState

    def build(self) -> StateGraph:
        researcher = DeepAgent(
            "deep_researcher",
            prompt="deep_researcher",
            tools=self.tools.get("search_knowledge_base", "calculate", "get_current_time"),
            skills=self.skills.get_many("financial-calculations"),
        )

        builder = StateGraph(self.state_schema)
        builder.add_node(researcher.name, researcher.as_node())
        builder.add_edge(START, researcher.name)
        builder.add_edge(researcher.name, END)
        return builder
