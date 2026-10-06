"""Dependency injection: the container of long-lived services shared by the routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from backend.agentic.graphs import GraphRegistry
from backend.agentic.skills import SkillRegistry
from backend.agentic.tools import ToolRegistry
from backend.infra import DbSessionmaker
from backend.services import EventBus, RunService


@dataclass
class AppContainer:
    """
    Long-lived services, built once in the app lifespan.
    """
    db: DbSessionmaker
    tools: ToolRegistry
    skills: SkillRegistry
    graphs: GraphRegistry
    bus: EventBus
    runs: RunService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
