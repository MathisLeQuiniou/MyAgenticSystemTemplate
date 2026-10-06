"""Run routes: start, list, inspect, cancel and stream graph runs (SSE)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from backend.api.dependencies import AppContainer, get_container
from backend.schemas import TERMINAL_EVENT_TYPES, RunCreate, RunRead, TraceEvent
from backend.utils import to_jsonable

router = APIRouter(tags=["runs"])
_TERMINAL = {t.value for t in TERMINAL_EVENT_TYPES}


@router.post("/runs", response_model=RunRead, status_code=201)
async def create_run(req: RunCreate, c: AppContainer = Depends(get_container)) -> RunRead:
    try:
        return await c.runs.start(req)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc


@router.get("/runs", response_model=list[RunRead])
async def list_runs(graph: str | None = None, limit: int = 50, offset: int = 0, c: AppContainer = Depends(get_container)) -> list[RunRead]:
    return await c.runs.runs.list(graph_name=graph, limit=min(limit, 500), offset=offset)


async def _get_run(run_id: uuid.UUID, c: AppContainer) -> RunRead:
    run = await c.runs.runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(run_id: uuid.UUID, c: AppContainer = Depends(get_container)) -> RunRead:
    return await _get_run(run_id, c)


@router.get("/runs/{run_id}/events", response_model=list[TraceEvent])
async def get_run_events(run_id: uuid.UUID, after_seq: int = -1, c: AppContainer = Depends(get_container)) -> list[TraceEvent]:
    await _get_run(run_id, c)
    return await c.runs.events.list(run_id, after_seq=after_seq)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, c: AppContainer = Depends(get_container)) -> dict:
    await _get_run(run_id, c)
    return {"cancelled": await c.runs.cancel(run_id)}


@router.get("/runs/{run_id}/state")
async def get_run_state(run_id: uuid.UUID, c: AppContainer = Depends(get_container)) -> dict:
    """Latest checkpointed state of the run's thread (LangGraph checkpointer)."""
    run = await _get_run(run_id, c)
    graph = c.graphs.get(run.graph_name)
    snapshot = await graph.compiled.aget_state({"configurable": {"thread_id": run.thread_id}})
    return {"thread_id": run.thread_id, "values": to_jsonable(snapshot.values), "next": list(snapshot.next)}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, request: Request, c: AppContainer = Depends(get_container)) -> EventSourceResponse:
    """Server-Sent Events: replays stored events, then streams live ones until the run ends."""
    await _get_run(run_id, c)
    queue = c.bus.subscribe(run_id)

    async def generator():
        try:
            last_seq = 0
            for event in await c.runs.events.list(run_id):
                last_seq = event.seq
                yield {"event": "trace", "data": event.model_dump_json()}
                if event.type in _TERMINAL:
                    return
            run = await c.runs.runs.get(run_id)
            if run is None or (run.status not in ("pending", "running") and not c.runs.is_active(run_id)):
                return
            while True:
                if await request.is_disconnected():
                    return
                event = await queue.get()
                if event is None:
                    return
                if event.type != "llm_token" and event.seq <= last_seq:
                    continue
                yield {"event": "trace", "data": event.model_dump_json()}
        finally:
            c.bus.unsubscribe(run_id, queue)

    return EventSourceResponse(generator(), ping=15)
