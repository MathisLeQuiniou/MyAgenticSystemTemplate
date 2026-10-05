from __future__ import annotations

from langchain_core.tools import BaseTool

from backend.agentic.tools.local_tools import LOCAL_TOOLS
from backend.infra.mcp_client import MCPToolProvider
from backend.utils import get_logger

log = get_logger(__name__)


class ToolRegistry:
    """Single place where graphs get their tools from (local + MCP), by name."""

    def __init__(self, mcp: MCPToolProvider | None = None, local_tools: list[BaseTool] | None = None) -> None:
        self.mcp = mcp or MCPToolProvider()
        self._local = {t.name: t for t in (local_tools if local_tools is not None else LOCAL_TOOLS)}

    async def load(self) -> None:
        await self.mcp.load()

    def all(self) -> list[BaseTool]:
        return [*self._local.values(), *self.mcp.tools()]

    def get(self, *names: str, required: bool = False) -> list[BaseTool]:
        """Return tools by name; missing ones are skipped (or raise if `required`).

        A tool can be missing because its name is wrong or because the MCP
        server exposing it was unavailable at startup: both cases look the same here.
        """
        index = {t.name: t for t in self.all()}
        missing = [n for n in names if n not in index]
        if missing:
            msg = f"Tools not available: {', '.join(missing)} (unknown name or MCP server unavailable)"
            if required:
                raise LookupError(msg)
            log.warning(msg)
        return [index[n] for n in names if n in index]

    def from_servers(self, *servers: str) -> list[BaseTool]:
        return self.mcp.tools(*servers)
