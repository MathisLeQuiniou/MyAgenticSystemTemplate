"""Run lifecycle: create -> execute graph in background -> trace -> persist."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from typing import Any

from backend.agentic.graphs import GraphRegistry
from backend.config import get_profile, get_settings
from backend.db import EventRepository, RunRepository
from backend.schemas import EventType, RunCreate, RunRead, TraceEvent
from backend.services.event_bus import EventBus
from backend.services.tracing import TraceCollector
from backend.utils import get_logger, to_jsonable, utcnow

logger = get_logger(__name__)


class RunService:
    def __init__(self, graphs: GraphRegistry, bus: EventBus, runs: RunRepository, events: EventRepository) -> None:
        self.graphs = graphs
        self.bus = bus
        self.runs = runs
        self.events = events
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    # -- public API --------------------------------------------------------------
    async def start(self, req: RunCreate) -> RunRead:
        graph = self.graphs.get(req.graph)  # raises KeyError if unknown
        if req.model_profile:
            get_profile(req.model_profile)  # raises KeyError if unknown
        run = await self.runs.create(
            graph_name=graph.name,
            thread_id=req.thread_id or str(uuid.uuid4()),
            input=req.input,
            model_profile=req.model_profile,
        )
        task = asyncio.create_task(self._execute(run), name=f"run-{run.id}")
        self._tasks[run.id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run.id, None))
        return run

    async def cancel(self, run_id: uuid.UUID) -> bool:
        task = self._tasks.get(run_id)
        if not task:
            return False
        task.cancel()
        return True

    def is_active(self, run_id: uuid.UUID) -> bool:
        return run_id in self._tasks

    async def shutdown(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    # -- execution ------------------------------------------------------------------
    async def _execute(self, run: RunRead) -> None:
        settings = get_settings()
        graph = self.graphs.get(run.graph_name)
        collector = TraceCollector(run.id, max_chars=settings.trace_max_payload_chars, stream_tokens=settings.stream_llm_tokens)
        seq = 0

        async def emit(events: list[TraceEvent]) -> None:
            nonlocal seq
            to_store = []
            for event in events:
                if event.type == EventType.LLM_TOKEN.value:
                    event.seq = seq  # tokens are live-only and reuse the last seq
                else:
                    seq += 1
                    event.seq = seq
                    to_store.append(event)
                self.bus.publish(event)
            await self.events.add_many(to_store)

        def run_event(type_: EventType, payload: dict[str, Any]) -> TraceEvent:
            return TraceEvent(run_id=run.id, type=type_, name=graph.name, timestamp=utcnow(), payload=payload)

        config: dict[str, Any] = {
            "configurable": {"thread_id": run.thread_id, "model_profile": run.model_profile},
            "recursion_limit": settings.graph_recursion_limit,
            "metadata": {"app_run_id": str(run.id), "graph": graph.name},
        }

        started = utcnow()
        try:
            await self.runs.update(run.id, status="running", started_at=started)
            await emit([run_event(EventType.RUN_STARTED, {"input": run.input, "thread_id": run.thread_id, "model_profile": run.model_profile})])

            async def _stream() -> None:
                async for lc_event in graph.compiled.astream_events(graph.build_input(run.input), config, version="v2"):
                    events = collector.process(lc_event)
                    if events:
                        await emit(events)

            await asyncio.wait_for(_stream(), timeout=settings.run_timeout_seconds)

            snapshot = await graph.compiled.aget_state(config)
            output = to_jsonable(graph.build_output(snapshot.values))
            finished = utcnow()
            duration = (finished - started).total_seconds() * 1000
            await emit([run_event(EventType.RUN_COMPLETED, {"output": output, "total_tokens": collector.total_tokens, "duration_ms": duration})])
            await self.runs.update(run.id, status="completed", output=output, total_tokens=collector.total_tokens, finished_at=finished)

        except asyncio.CancelledError:
            await self._finish_with_error(run, collector, emit, run_event, EventType.RUN_CANCELLED, "cancelled", "Run cancelled by user.")
        except Exception as exc:  # noqa: BLE001
            message = "Run timed out." if isinstance(exc, asyncio.TimeoutError) else f"{type(exc).__name__}: {exc}"
            if "Connect" in type(exc).__name__:
                profile = run.model_profile or "default"
                message += f" (is the LLM endpoint of model profile '{profile}' reachable? see backend/config/models.yaml)"
            logger.exception("Run %s failed", run.id)
            await self._finish_with_error(
                run, collector, emit, run_event, EventType.RUN_FAILED, "failed", message, traceback.format_exc()
            )
        finally:
            self.bus.close(run.id)

    async def _finish_with_error(self, run, collector, emit, run_event, type_, status, message, tb=None) -> None:
        try:
            await emit([*collector.close_open_spans(message), run_event(type_, {"error": message, "traceback": tb, "total_tokens": collector.total_tokens})])
            await self.runs.update(run.id, status=status, error=message, total_tokens=collector.total_tokens, finished_at=utcnow())
        except Exception:  # noqa: BLE001
            logger.exception("Could not record the end of run %s", run.id)
