"""Connections to external systems, opened once by the API lifespan.

- database:     async SQLAlchemy engine for the application tables (runs, events)
- checkpointer: LangGraph Postgres checkpointer (graph state per thread)
- mcp_client:   clients of the MCP tool servers
"""

from backend.infra.checkpointer import postgres_checkpointer
from backend.infra.database import DbSessionmaker, postgres_sessionmaker, session_scope
from backend.infra.mcp_client import MCPToolProvider

__all__ = ["DbSessionmaker", "MCPToolProvider", "postgres_checkpointer", "postgres_sessionmaker", "session_scope"]
