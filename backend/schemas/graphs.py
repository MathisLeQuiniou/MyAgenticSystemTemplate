from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str  # "researcher" or "researcher:tools" for subgraph nodes
    label: str
    parent: str | None = None  # id of the enclosing subgraph, if any
    kind: str = "node"  # node | start | end


class GraphEdge(BaseModel):
    source: str
    target: str
    conditional: bool = False
    label: str | None = None


class GraphSummary(BaseModel):
    name: str
    description: str


class GraphDescription(GraphSummary):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    mermaid: str | None = None


class ModelProfileSummary(BaseModel):
    name: str
    provider: str
    model: str
    is_default: bool = False
