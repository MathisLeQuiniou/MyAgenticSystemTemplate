"""Graph registry: `@register_graph` decorator, auto-discovery and compiled graph instances."""

from __future__ import annotations

import importlib
import pkgutil

from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.agentic.graphs.base import BaseGraph
from backend.agentic.skills import SkillRegistry
from backend.agentic.tools import ToolRegistry
from backend.utils import get_logger

logger = get_logger(__name__)

_GRAPH_CLASSES: dict[str, type[BaseGraph]] = {}


def register_graph(cls: type[BaseGraph]) -> type[BaseGraph]:
    """Class decorator: make a graph discoverable by the API."""
    if not getattr(cls, "name", None):
        raise ValueError(f"{cls.__name__} must define a `name`")
    if cls.name in _GRAPH_CLASSES and _GRAPH_CLASSES[cls.name] is not cls:
        raise ValueError(f"Graph name '{cls.name}' registered twice")
    _GRAPH_CLASSES[cls.name] = cls
    return cls


def discover_graphs(package: str = "backend.agentic.graphs") -> None:
    """Import every module under `package` so `@register_graph` decorators run."""
    pkg = importlib.import_module(package)
    for mod in pkgutil.walk_packages(pkg.__path__, prefix=f"{package}."):
        importlib.import_module(mod.name)


class GraphRegistry:
    """Holds one compiled instance of every registered graph."""

    def __init__(self, tools: ToolRegistry, skills: SkillRegistry, checkpointer: BaseCheckpointSaver | None = None) -> None:
        self.tools = tools
        self.skills = skills
        self.checkpointer = checkpointer
        self._graphs: dict[str, BaseGraph] = {}

    def load(self) -> None:
        discover_graphs()
        for name, cls in sorted(_GRAPH_CLASSES.items()):
            try:
                graph = cls(self.tools, self.skills)
                graph.compile(self.checkpointer)
                self._graphs[name] = graph
                logger.info("Graph %s compiled", name)
            except Exception:
                logger.exception("Failed to compile graph %s", name)

    def get(self, name: str) -> BaseGraph:
        try:
            return self._graphs[name]
        except KeyError:
            raise KeyError(f"Unknown graph '{name}'. Available: {', '.join(self._graphs) or '-'}") from None

    def all(self) -> list[BaseGraph]:
        return list(self._graphs.values())
