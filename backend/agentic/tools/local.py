"""In-process tools (plain Python functions). Good for cheap, dependency-free tools.

Anything heavier, shared between projects, or written in another language is a
better fit for an MCP server in `backend/tool_servers/`.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from langchain_core.tools import tool


@tool
def get_current_time(timezone: str = "Europe/Paris") -> str:
    """Return the current date and time in the given IANA timezone (e.g. 'Europe/Paris')."""
    try:
        now = dt.datetime.now(ZoneInfo(timezone))
    except Exception:
        now = dt.datetime.now(dt.timezone.utc)
        timezone = "UTC"
    return f"{now:%Y-%m-%d %H:%M:%S} ({timezone})"


LOCAL_TOOLS = [get_current_time]
