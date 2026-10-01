"""
FastAPI application.

    uvicorn backend.api.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agentic.graphs import GraphRegistry
from backend.agentic.tools import ToolRegistry
from backend.api.dependencies import AppContainer
from backend.api.routes import graphs, health, runs, skills
from backend.config import get_settings
from backend.db import RunRepository, dispose_engine
from backend.services import EventBus, RunService, postgres_checkpointer
from backend.utils import get_logger, setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    interrupted = await RunRepository().mark_interrupted()
    if interrupted:
        log.warning("%d run(s) were interrupted by the last shutdown", interrupted)

    async with postgres_checkpointer() as checkpointer:
        tools = ToolRegistry()
        await tools.load()
        graphs_registry = GraphRegistry(tools, checkpointer)
        graphs_registry.load()
        bus = EventBus()
        run_service = RunService(graphs_registry, bus)
        app.state.container = AppContainer(tools=tools, graphs=graphs_registry, bus=bus, runs=run_service)
        log.info("API ready: %d graph(s), %d tool(s)", len(graphs_registry.all()), len(tools.all()))
        try:
            yield
        finally:
            await run_service.shutdown()
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title=f"{settings.app_name} API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(graphs.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    return app


app = create_app()
