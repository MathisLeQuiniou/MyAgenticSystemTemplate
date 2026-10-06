"""Graph base class.

A graph = a LangGraph `StateGraph` + a name + input/output adapters. Subclass
`BaseGraph`, implement `build()` and decorate with `@register_graph`: the API
discovers it automatically and the frontend can run and trace it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.agentic.skills import SkillRegistry
from backend.agentic.states import BaseState
from backend.agentic.tools import ToolRegistry
from backend.schemas import GraphDescription, GraphEdge, GraphNode
from backend.utils import to_jsonable


class BaseGraph(ABC):
    name: ClassVar[str]
    description: ClassVar[str] = ""
    state_schema: ClassVar[type] = BaseState

    def __init__(self, tools: ToolRegistry, skills: SkillRegistry) -> None:
        self.tools = tools
        self.skills = skills
        self._compiled: CompiledStateGraph | None = None

    # -- to implement --------------------------------------------------------
    @abstractmethod
    def build(self) -> StateGraph:
        """Return the (uncompiled) StateGraph: add agents as nodes and wire edges."""

    # -- input / output adapters (override if your graph needs more) ---------
    def build_input(self, payload: dict[str, Any]) -> dict[str, Any]:
        """API payload -> initial state. Default: {'message': str, 'state': {...}}."""
        state = dict(payload.get("state") or {})
        if payload.get("message"):
            state["messages"] = [HumanMessage(content=str(payload["message"]))]
        return state

    def build_output(self, final_state: dict[str, Any]) -> dict[str, Any]:
        """Final state -> what is stored as the run output and shown in the UI."""
        answer = next(
            (m.content for m in reversed(final_state.get("messages", [])) if isinstance(m, AIMessage) and m.content),
            None,
        )
        return {"answer": answer, "state": to_jsonable(final_state, max_chars=5000)}

    # -- compilation -------------------------------------------------------------
    def compile(self, checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
        self._compiled = self.build().compile(checkpointer=checkpointer, name=self.name)
        return self._compiled

    @property
    def compiled(self) -> CompiledStateGraph:
        if self._compiled is None:
            raise RuntimeError(f"Graph '{self.name}' is not compiled; call compile() first.")
        return self._compiled

    # -- introspection for the frontend --------------------------------------------
    def describe(self) -> GraphDescription:
        g = self.compiled.get_graph(xray=True)
        nodes: list[GraphNode] = []
        for node_id, node in g.nodes.items():
            kind = "start" if node_id.endswith("__start__") else "end" if node_id.endswith("__end__") else "node"
            parent = node_id.rsplit(":", 1)[0] if ":" in node_id else None
            label = node_id.rsplit(":", 1)[-1]
            nodes.append(GraphNode(id=node_id, label=label, parent=parent, kind=kind))
        edges = [
            GraphEdge(source=e.source, target=e.target, conditional=e.conditional, label=str(e.data) if e.data else None)
            for e in g.edges
        ]
        try:
            mermaid = g.draw_mermaid()
        except Exception:  # noqa: BLE001
            mermaid = None
        return GraphDescription(name=self.name, description=self.description, nodes=nodes, edges=edges, mermaid=mermaid)
