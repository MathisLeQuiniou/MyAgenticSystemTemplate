from __future__ import annotations

from pydantic import BaseModel


class SkillSummary(BaseModel):
    name: str
    description: str
    files: list[str]


class SkillDetail(SkillSummary):
    body: str
