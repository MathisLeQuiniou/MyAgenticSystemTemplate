"""Data access for runs and events. Keep SQL here, not in services or routes."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update

from backend.db.models import EventORM, RunORM
from backend.infra.database import DbSessionmaker, session_scope
from backend.schemas import RunRead, TraceEvent


class RunRepository:
    def __init__(self, sessionmaker: DbSessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def create(self, *, graph_name: str, thread_id: str, input: dict[str, Any], model_profile: str | None) -> RunRead:
        async with session_scope(self._sessionmaker) as s:
            run = RunORM(graph_name=graph_name, thread_id=thread_id, input=input, model_profile=model_profile, status="pending")
            s.add(run)
            await s.flush()
            await s.refresh(run)
            return RunRead.model_validate(run)

    async def update(self, run_id: uuid.UUID, **fields: Any) -> None:
        async with session_scope(self._sessionmaker) as s:
            await s.execute(update(RunORM).where(RunORM.id == run_id).values(**fields))

    async def get(self, run_id: uuid.UUID) -> RunRead | None:
        async with session_scope(self._sessionmaker) as s:
            run = await s.get(RunORM, run_id)
            return RunRead.model_validate(run) if run else None

    async def list(self, *, graph_name: str | None = None, limit: int = 50, offset: int = 0) -> list[RunRead]:
        async with session_scope(self._sessionmaker) as s:
            q = select(RunORM).order_by(RunORM.created_at.desc()).limit(limit).offset(offset)
            if graph_name:
                q = q.where(RunORM.graph_name == graph_name)
            rows = (await s.scalars(q)).all()
            return [RunRead.model_validate(r) for r in rows]

    async def mark_interrupted(self) -> int:
        """Runs still `running` at startup were killed with the process."""
        async with session_scope(self._sessionmaker) as s:
            res = await s.execute(
                update(RunORM)
                .where(RunORM.status.in_(["pending", "running"]))
                .values(status="failed", error="Interrupted: the API stopped while the run was in progress.")
            )
            return res.rowcount or 0


class EventRepository:
    def __init__(self, sessionmaker: DbSessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def add_many(self, events: list[TraceEvent]) -> None:
        if not events:
            return
        async with session_scope(self._sessionmaker) as s:
            s.add_all([EventORM(**e.model_dump()) for e in events])

    async def list(self, run_id: uuid.UUID, *, after_seq: int = -1) -> list[TraceEvent]:
        async with session_scope(self._sessionmaker) as s:
            q = select(EventORM).where(EventORM.run_id == run_id, EventORM.seq > after_seq).order_by(EventORM.seq)
            return [TraceEvent.model_validate(r) for r in (await s.scalars(q)).all()]
