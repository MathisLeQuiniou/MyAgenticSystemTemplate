"""SQLAlchemy ORM models (our own tables; LangGraph manages its checkpoint tables)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base


class RunORM(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_name: Mapped[str] = mapped_column(String(128), index=True)
    thread_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    model_profile: Mapped[str | None] = mapped_column(String(128))
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list[EventORM]] = relationship(back_populates="run", cascade="all, delete-orphan", passive_deletes=True)


class EventORM(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_run_id_seq", "run_id", "seq", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(256))
    node_path: Mapped[str | None] = mapped_column(String(512))
    span_id: Mapped[str | None] = mapped_column(String(64))
    parent_span_id: Mapped[str | None] = mapped_column(String(64))
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    run: Mapped[RunORM] = relationship(back_populates="events")
