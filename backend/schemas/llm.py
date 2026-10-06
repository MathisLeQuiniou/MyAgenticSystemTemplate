from __future__ import annotations

from pydantic import BaseModel


class ModelProfileSummary(BaseModel):
    name: str
    provider: str
    model: str
    is_default: bool = False
