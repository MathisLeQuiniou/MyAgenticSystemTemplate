from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from backend.agentic.graphs import GraphRegistry
from backend.agentic.tools import ToolRegistry
from backend.services import EventBus, RunService


@dataclass
class AppContainer:
    """
    Long-lived services, built once in the app lifespan.
    """
    tools: ToolRegistry
    graphs: GraphRegistry
    bus: EventBus
    runs: RunService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
