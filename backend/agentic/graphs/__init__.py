"""Graphs: the `BaseGraph` contract and the registry that discovers and compiles graphs."""

from backend.agentic.graphs.base import BaseGraph
from backend.agentic.graphs.graphs_registry import GraphRegistry, discover_graphs, register_graph

__all__ = ["BaseGraph", "GraphRegistry", "discover_graphs", "register_graph"]
