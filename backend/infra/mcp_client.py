"""MCP client: load the tools exposed by the MCP servers declared in backend/config/mcp_servers.yaml."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from backend.config import LAUNCH_KEYS, load_mcp_config
from backend.utils import get_logger

logger = get_logger(__name__)

class MCPToolProvider:
    """Connects to the configured MCP servers and exposes their tools as LangChain tools.

    A server that is down is logged and skipped so the API can still start.
    """

    def __init__(self, servers: dict[str, dict[str, Any]] | None = None) -> None:
        self.servers = servers if servers is not None else load_mcp_config()
        self._tools: dict[str, list[BaseTool]] = {}

    @staticmethod
    def _connection(cfg: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in cfg.items() if k not in LAUNCH_KEYS}

    async def load(self) -> None:
        for name, cfg in self.servers.items():
            try:
                client = MultiServerMCPClient({name: self._connection(cfg)})
                self._tools[name] = await client.get_tools()
                logger.info("MCP server %s: %d tools (%s)", name, len(self._tools[name]), ", ".join(t.name for t in self._tools[name]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("MCP server %s unavailable (%s). Its tools are disabled.", name, _root_cause(exc))
                self._tools[name] = []

    def tools(self, *servers: str) -> list[BaseTool]:
        """Tools from the given servers (all servers if none given)."""
        names = servers or tuple(self._tools)
        return [t for n in names for t in self._tools.get(n, [])]


def _root_cause(exc: BaseException) -> str:
    while True:
        sub = getattr(exc, "exceptions", None)  # ExceptionGroup (anyio / TaskGroup)
        if sub:
            exc = sub[0]
        elif exc.__cause__ is not None:
            exc = exc.__cause__
        else:
            return f"{type(exc).__name__}: {exc}"
