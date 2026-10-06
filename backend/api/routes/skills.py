"""Skill routes: list skills and read their instructions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import AppContainer, get_container
from backend.schemas import SkillDetail, SkillSummary

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[SkillSummary])
async def list_skills(c: AppContainer = Depends(get_container)) -> list[SkillSummary]:
    return [SkillSummary(name=s.name, description=s.description, files=s.files()) for s in c.skills.all()]


@router.get("/skills/{name}", response_model=SkillDetail)
async def get_skill(name: str, c: AppContainer = Depends(get_container)) -> SkillDetail:
    try:
        s = c.skills.get(name)
    except KeyError as exc:
        raise HTTPException(404, str(exc).strip("'\"")) from exc
    return SkillDetail(name=s.name, description=s.description, files=s.files(), body=s.body)
