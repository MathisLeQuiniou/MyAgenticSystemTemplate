"""Schemas of a run: creation request, status and stored representation."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunCreate(BaseModel):
    graph: str = Field(description="Registered graph name")
    input: dict[str, Any] = Field(description="Graph input, e.g. {'message': 'Hello'}")
    model_profile: str | None = Field(default=None, description="Override the model profile for every agent")
    thread_id: str | None = Field(default=None, description="Reuse a thread to continue a conversation")


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: UUID
    graph_name: str
    thread_id: str
    status: RunStatus
    model_profile: str | None = None
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None
    total_tokens: int = 0
    created_at: dt.datetime
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None

    @property
    def duration_ms(self) -> float | None:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds() * 1000
        return None
