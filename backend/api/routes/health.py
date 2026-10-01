from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from backend.agentic.skills import get_skill_registry
from backend.api.dependencies import AppContainer, get_container
from backend.db import session_scope

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(c: AppContainer = Depends(get_container)) -> dict:
    db_ok = True
    try:
        async with session_scope() as s:
            await s.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "graphs": [g.name for g in c.graphs.all()],
        "tools": [t.name for t in c.tools.all()],
        "skills": [s.name for s in get_skill_registry().all()],
    }
