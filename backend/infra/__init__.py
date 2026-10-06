"""Connections to external systems (database, checkpointer and MCP clients are opened
once by the API lifespan; LLM clients are built lazily and cached per profile).

- database:     async SQLAlchemy engine for the application tables (runs, events)
- checkpointer: LangGraph Postgres checkpointer (graph state per thread)
- mcp_client:   clients of the MCP tool servers
- llm:          chat model clients, one per profile of config/models.yaml
"""

from backend.infra.checkpointer import postgres_checkpointer
from backend.infra.database import DbSessionmaker, postgres_sessionmaker, session_scope
from backend.infra.llm import get_chat_model
from backend.infra.mcp_client import MCPToolProvider

__all__ = [
    "DbSessionmaker",
    "MCPToolProvider",
    "get_chat_model",
    "postgres_checkpointer",
    "postgres_sessionmaker",
    "session_scope",
]
