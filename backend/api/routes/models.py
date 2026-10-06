from __future__ import annotations

from fastapi import APIRouter

from backend.config import load_models_config
from backend.schemas import ModelProfileSummary

router = APIRouter(tags=["models"])


@router.get("/models", response_model=list[ModelProfileSummary])
async def list_models() -> list[ModelProfileSummary]:
    cfg = load_models_config()
    return [
        ModelProfileSummary(name=p.name, provider=p.provider, model=p.model, is_default=p.name == cfg.default)
        for p in cfg.profiles.values()
    ]
