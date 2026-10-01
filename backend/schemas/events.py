"""Trace events emitted while a graph runs.

These are the single source of truth for observability: they are stored in
Postgres, streamed over SSE and rendered by the frontend.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    LLM_STARTED = "llm_started"
    LLM_COMPLETED = "llm_completed"
    LLM_FAILED = "llm_failed"
    LLM_TOKEN = "llm_token"  # live only, never persisted
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    CUSTOM = "custom"  # emitted by agents through `emit_custom_event`


TERMINAL_EVENT_TYPES = {EventType.RUN_COMPLETED, EventType.RUN_FAILED, EventType.RUN_CANCELLED}


class TraceEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    run_id: UUID
    seq: int = 0  # monotonically increasing per run, assigned by the run service
    type: EventType
    name: str  # node / model / tool name
    # Graph position: "researcher" for a top-level node, "researcher:tools" for
    # a node inside the `researcher` subgraph. Used to highlight the graph path.
    node_path: str | None = None
    span_id: str | None = None  # LangChain run id of the step
    parent_span_id: str | None = None  # closest traced ancestor
    timestamp: dt.datetime
    duration_ms: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
