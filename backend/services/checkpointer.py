"""LangGraph Postgres checkpointer (persists graph state per thread).

Its tables live in their own schema (`CHECKPOINT_SCHEMA`, default `langgraph`)
and are created by `AsyncPostgresSaver.setup()`, not by Alembic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from backend.config import get_settings


@asynccontextmanager
async def postgres_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    settings = get_settings()
    url, schema = settings.checkpoint_database_url, settings.checkpoint_schema

    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')

    pool = AsyncConnectionPool(
        conninfo=url,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row, "options": f"-c search_path={schema}"},
    )
    await pool.open()
    try:
        saver = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
        await saver.setup()
        yield saver
    finally:
        await pool.close()
