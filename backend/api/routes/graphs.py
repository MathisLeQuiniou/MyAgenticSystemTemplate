from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import AppContainer, get_container
from backend.schemas import GraphDescription, GraphSummary

router = APIRouter(tags=["graphs"])


@router.get("/graphs", response_model=list[GraphSummary])
async def list_graphs(c: AppContainer = Depends(get_container)) -> list[GraphSummary]:
    return [GraphSummary(name=g.name, description=g.description) for g in c.graphs.all()]


@router.get("/graphs/{name}", response_model=GraphDescription)
async def describe_graph(name: str, c: AppContainer = Depends(get_container)) -> GraphDescription:
    try:
        return c.graphs.get(name).describe()
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
