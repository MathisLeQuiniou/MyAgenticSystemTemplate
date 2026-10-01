"""
Create the database if needed, then apply Alembic migrations.

Usage (from the repo root):  python -m backend.db.init_db
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from backend.config import get_settings
from backend.utils import get_logger, setup_logging

logger = get_logger(__name__)
setup_logging(get_settings().log_level)

ALEMBIC_INI = Path(__file__).with_name("alembic.ini")

async def ensure_database() -> None:
    url = make_url(get_settings().database_url)
    db_name = url.database
    conn = await asyncpg.connect(
        user=url.username, 
        password=url.password, 
        host=url.host or "localhost", 
        port=url.port or 5432, 
        database="postgres"
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info("Created database %s", db_name)
        else:
            logger.info("Database %s already exists", db_name)
    finally:
        await conn.close()

def run_migrations() -> None:
    command.upgrade(Config(str(ALEMBIC_INI)), "head")

def main() -> None:
    asyncio.run(ensure_database())
    run_migrations()
    logger.info("Database ready.")

if __name__ == "__main__":
    main()
