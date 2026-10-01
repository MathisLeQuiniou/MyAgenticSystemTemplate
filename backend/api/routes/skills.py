from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agentic.skills import get_skill_registry

router = APIRouter(tags=["skills"])


class SkillSummary(BaseModel):
    name: str
    description: str
    files: list[str]


class SkillDetail(SkillSummary):
    body: str


@router.get("/skills", response_model=list[SkillSummary])
async def list_skills() -> list[SkillSummary]:
    return [SkillSummary(name=s.name, description=s.description, files=s.files()) for s in get_skill_registry().all()]


@router.get("/skills/{name}", response_model=SkillDetail)
async def get_skill(name: str) -> SkillDetail:
    try:
        s = get_skill_registry().get(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc
    return SkillDetail(name=s.name, description=s.description, files=s.files(), body=s.body)
