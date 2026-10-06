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
from backend.agentic.skills import SkillRegistry
from backend.agentic.tools import ToolRegistry
from backend.api.dependencies import AppContainer
from backend.api.routes import graphs, health, models, runs, skills
from backend.config import get_settings
from backend.db import EventRepository, RunRepository
from backend.infra import postgres_checkpointer, postgres_sessionmaker
from backend.services import EventBus, RunService
from backend.utils import get_logger, setup_logging

settings = get_settings()
setup_logging(settings.log_level)
log = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # --- start up ------------------------------------------------------------
    # external connections (closed in reverse order on exit)
    async with postgres_sessionmaker() as db, postgres_checkpointer() as checkpointer:
        # data access to the app tables
        runs_repo = RunRepository(db)
        events_repo = EventRepository(db)

        interrupted = await runs_repo.mark_interrupted()
        if interrupted:
            log.warning("%d run(s) were interrupted by the last shutdown", interrupted)

        # get tools
        tools = ToolRegistry()
        await tools.load()

        # get skills
        skills = SkillRegistry()
        skills.load()

        # get agentic graphs
        graphs_registry = GraphRegistry(tools, skills, checkpointer)
        graphs_registry.load()

        # get events Bus
        bus = EventBus()

        # instantiate run service
        run_service = RunService(graphs_registry, bus, runs_repo, events_repo)

        # store persistent ressources
        app.state.container = AppContainer(
            db=db,
            tools=tools,
            skills=skills,
            graphs=graphs_registry,
            bus=bus,
            runs=run_service,
        )
        log.info(
            "API ready: %d graph(s), %d tool(s), %d skill(s)", len(graphs_registry.all()), len(tools.all()), len(skills.all())
        )
        try:
            yield

        # --- shut down--------------------------------------------------------
        finally:
            # cancel running runs while the database is still open to record it
            await run_service.shutdown()


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
    app.include_router(models.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    return app


app = create_app()
