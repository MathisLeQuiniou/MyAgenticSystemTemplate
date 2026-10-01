"""Reusable LangGraph reducers.

A reducer tells LangGraph how to merge a node's partial update into the state:
`Annotated[list[str], append_list]` appends instead of overwriting.
"""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


def merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Shallow merge; keys from `right` win."""
    return {**(left or {}), **(right or {})}


def append_list(left: list[T] | None, right: list[T] | T | None) -> list[T]:
    if right is None:
        return list(left or [])
    if not isinstance(right, list):
        right = [right]
    return [*(left or []), *right]


def replace(left: T, right: T) -> T:  # noqa: ARG001
    """Explicit "last write wins" (the default behaviour, useful for readability)."""
    return right


def increment(left: int | None, right: int | None) -> int:
    return (left or 0) + (right or 0)
