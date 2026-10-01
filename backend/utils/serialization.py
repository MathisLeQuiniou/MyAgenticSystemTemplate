"""Turn arbitrary LangChain / LangGraph objects into JSON-safe structures."""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from enum import Enum
from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from pydantic import BaseModel


def message_to_dict(message: BaseMessage) -> dict[str, Any]:
    data: dict[str, Any] = {"type": message.type, "content": message.content}
    for attr in ("name", "id", "tool_calls", "tool_call_id", "usage_metadata", "status"):
        value = getattr(message, attr, None)
        if value:
            data[attr] = value
    return data


def to_jsonable(obj: Any, *, max_chars: int | None = None, _depth: int = 0) -> Any:
    """Best-effort conversion to JSON-compatible data, truncating long strings."""
    if _depth > 20:
        return "<max depth>"
    rec = lambda o: to_jsonable(o, max_chars=max_chars, _depth=_depth + 1)  # noqa: E731

    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        if max_chars and len(obj) > max_chars:
            return obj[:max_chars] + f"... <truncated {len(obj) - max_chars} chars>"
        return obj
    if isinstance(obj, BaseMessage):
        return rec(message_to_dict(obj))
    if isinstance(obj, Document):
        return rec({"page_content": obj.page_content, "metadata": obj.metadata})
    if isinstance(obj, BaseModel):
        return rec(obj.model_dump(mode="python"))
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return rec(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): rec(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [rec(v) for v in obj]
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    return rec(repr(obj))
