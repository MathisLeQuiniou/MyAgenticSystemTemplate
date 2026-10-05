"""Async SQLAlchemy connection to the application database (tables `runs` / `events`).

The engine is opened and closed by the API lifespan, which hands the resulting
sessionmaker to the repositories. Scripts and tests open their own:

    async with postgres_sessionmaker() as db:
        await RunRepository(db).list()
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings

DbSessionmaker = async_sessionmaker[AsyncSession]


@asynccontextmanager
async def postgres_sessionmaker(database_url: str | None = None) -> AsyncGenerator[DbSessionmaker]:
    """Create the engine (connection pool), yield a sessionmaker, dispose the engine on exit."""
    settings = get_settings()
    engine = create_async_engine(database_url or settings.database_url, echo=settings.db_echo, pool_pre_ping=True)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@asynccontextmanager
async def session_scope(sessionmaker: DbSessionmaker) -> AsyncGenerator[AsyncSession]:
    """Transactional scope: commit on success, rollback on error."""
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
