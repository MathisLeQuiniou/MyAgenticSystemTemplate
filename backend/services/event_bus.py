"""In-memory pub/sub of trace events, used to stream live runs over SSE.

Single-process only. To run several API workers, swap it for Redis pub/sub or
Postgres LISTEN/NOTIFY behind the same interface.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict

from backend.schemas import TraceEvent


class EventBus:
    def __init__(self, max_queue: int = 10_000) -> None:
        self._subs: dict[uuid.UUID, set[asyncio.Queue[TraceEvent | None]]] = defaultdict(set)
        self._max_queue = max_queue

    def subscribe(self, run_id: uuid.UUID) -> asyncio.Queue[TraceEvent | None]:
        q: asyncio.Queue[TraceEvent | None] = asyncio.Queue(self._max_queue)
        self._subs[run_id].add(q)
        return q

    def unsubscribe(self, run_id: uuid.UUID, q: asyncio.Queue) -> None:
        self._subs.get(run_id, set()).discard(q)
        if run_id in self._subs and not self._subs[run_id]:
            del self._subs[run_id]

    def publish(self, event: TraceEvent) -> None:
        for q in list(self._subs.get(event.run_id, ())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # slow consumer: drop (it can reload from the DB)
                pass

    def close(self, run_id: uuid.UUID) -> None:
        """Signal subscribers that the run is over."""
        for q in list(self._subs.get(run_id, ())):
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                pass
