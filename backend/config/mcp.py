"""Load the MCP server declarations (backend/config/mcp_servers.yaml).

Shared by the server launcher (`backend/tool_servers/__main__.py`) and the
MCP client (`backend/infra/mcp_client.py`).
"""

from __future__ import annotations

from typing import Any

from backend.config.settings import get_settings
from backend.utils import load_yaml

# Keys of mcp_servers.yaml that are ours (launching / toggling a server),
# not part of the MCP connection spec passed to the client.
LAUNCH_KEYS = frozenset({"module", "host", "port", "enabled"})


def load_mcp_config() -> dict[str, dict[str, Any]]:
    """Return the enabled servers declared in mcp_servers.yaml, by name."""
    path = get_settings().mcp_config_path
    if not path.exists():
        return {}
    servers = load_yaml(path).get("servers") or {}
    return {name: cfg for name, cfg in servers.items() if cfg and cfg.get("enabled", True)}
