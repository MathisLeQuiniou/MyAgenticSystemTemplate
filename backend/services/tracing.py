"""Translate LangGraph `astream_events(version="v2")` into `TraceEvent`s.

LangGraph emits a very verbose stream (every runnable, every channel write...).
The collector keeps what matters to understand a run:

    node_started / node_completed   one per graph step (incl. subgraph steps)
    llm_started / llm_completed     every chat model call, with usage
    tool_started / tool_completed   every tool call, with args and result
    llm_token                       streamed tokens (live only)
    custom                          events dispatched by agents (`BaseAgent.emit`)

Each event carries `node_path` (e.g. "researcher:tools") matching the node ids of
`BaseGraph.describe()`, plus `span_id` / `parent_span_id` to rebuild the tree.

Used by `RunService`: graph execution -> `TraceCollector` -> `EventBus` (live) and
`EventRepository` (persisted). It relies on conventions of the agentic layer:
`BaseGraph.describe()` node ids and `BaseAgent.emit` custom events.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, ToolMessage

from backend.schemas import EventType, TraceEvent
from backend.utils import to_jsonable, utcnow


@dataclass
class _Span:
    type: str  # node | llm | tool
    name: str
    node_path: str | None
    started: float = field(default_factory=time.perf_counter)


def node_path_from_ns(ns: str | None) -> str | None:
    """'researcher:<uuid>|agent:<uuid>' -> 'researcher:agent'."""
    if not ns:
        return None
    return ":".join(segment.split(":")[0] for segment in ns.split("|"))


class TraceCollector:
    def __init__(self, run_id: uuid.UUID, *, max_chars: int = 20_000, stream_tokens: bool = True) -> None:
        self.run_id = run_id
        self.max_chars = max_chars
        self.stream_tokens = stream_tokens
        self._spans: dict[str, _Span] = {}  # open spans by LangChain run id
        self._known: set[str] = set()  # every traced span id (open or closed)
        self._node_ns: set[str] = set()  # checkpoint namespaces already traced as nodes
        self.total_tokens = 0

    # -- public API ----------------------------------------------------------------
    def process(self, ev: dict[str, Any]) -> list[TraceEvent]:
        kind = ev.get("event", "")
        handler = getattr(self, f"_on_{kind.removeprefix('on_')}", None)
        return handler(ev) if handler else []

    def close_open_spans(self, error: str) -> list[TraceEvent]:
        """Mark still-open spans as failed (run crashed or was cancelled)."""
        out = []
        failed = {"node": EventType.NODE_FAILED, "llm": EventType.LLM_FAILED, "tool": EventType.TOOL_FAILED}
        for span_id, span in reversed(list(self._spans.items())):
            out.append(self._event(failed[span.type], span.name, span.node_path, span_id, None, {"error": error}, self._duration(span)))
        self._spans.clear()
        return out

    # -- helpers ---------------------------------------------------------------------
    def _json(self, value: Any) -> Any:
        return to_jsonable(value, max_chars=self.max_chars)

    def _parent(self, ev: dict[str, Any]) -> str | None:
        for pid in reversed(ev.get("parent_ids") or []):
            if pid in self._known:
                return pid
        return None

    @staticmethod
    def _duration(span: _Span) -> float:
        return round((time.perf_counter() - span.started) * 1000, 2)

    def _event(self, type_, name, node_path, span_id, parent, payload, duration=None) -> TraceEvent:
        return TraceEvent(
            run_id=self.run_id,
            type=type_,
            name=name,
            node_path=node_path,
            span_id=span_id,
            parent_span_id=parent,
            timestamp=utcnow(),
            duration_ms=duration,
            payload=payload,
        )

    def _open(self, ev, type_: str, event_type: EventType, name: str, payload: dict) -> list[TraceEvent]:
        md = ev.get("metadata") or {}
        span_id = ev["run_id"]
        node_path = node_path_from_ns(md.get("langgraph_checkpoint_ns"))
        parent = self._parent(ev)
        self._spans[span_id] = _Span(type_, name, node_path)
        self._known.add(span_id)
        return [self._event(event_type, name, node_path, span_id, parent, payload)]

    def _close(self, ev, event_type: EventType, payload: dict) -> list[TraceEvent]:
        span = self._spans.pop(ev["run_id"], None)
        if span is None:
            return []
        return [self._event(event_type, span.name, span.node_path, ev["run_id"], self._parent(ev), payload, self._duration(span))]

    # -- graph nodes -------------------------------------------------------------------
    def _on_chain_start(self, ev) -> list[TraceEvent]:
        md = ev.get("metadata") or {}
        node, ns, name = md.get("langgraph_node"), md.get("langgraph_checkpoint_ns"), ev.get("name")
        # A graph step: the runnable named after the node, first time we see its namespace.
        if not node or name != node or node.startswith("__") or not ns or ns in self._node_ns:
            return []
        if ns.split("|")[-1].split(":")[0] != node:
            return []
        self._node_ns.add(ns)
        return self._open(ev, "node", EventType.NODE_STARTED, node, {"input": self._json(ev.get("data", {}).get("input"))})

    def _on_chain_end(self, ev) -> list[TraceEvent]:
        if ev["run_id"] not in self._spans or self._spans[ev["run_id"]].type != "node":
            return []
        return self._close(ev, EventType.NODE_COMPLETED, {"output": self._json(ev.get("data", {}).get("output"))})

    def _on_chain_error(self, ev) -> list[TraceEvent]:  # emitted by some runnables
        if ev["run_id"] not in self._spans:
            return []
        return self._close(ev, EventType.NODE_FAILED, {"error": str(ev.get("data", {}).get("error"))})

    # -- LLM calls -----------------------------------------------------------------------
    def _on_chat_model_start(self, ev) -> list[TraceEvent]:
        md = ev.get("metadata") or {}
        messages = (ev.get("data", {}).get("input") or {}).get("messages") or []
        if messages and isinstance(messages[0], list):
            messages = messages[0]
        payload = {
            "model": md.get("ls_model_name") or ev.get("name"),
            "provider": md.get("ls_provider"),
            "agent": md.get("langgraph_node"),
            "messages": self._json(messages),
            "invocation_params": self._json({k: md.get(k) for k in ("ls_temperature", "ls_max_tokens") if md.get(k) is not None}),
        }
        return self._open(ev, "llm", EventType.LLM_STARTED, str(payload["model"]), payload)

    def _on_chat_model_stream(self, ev) -> list[TraceEvent]:
        if not self.stream_tokens:
            return []
        chunk = ev.get("data", {}).get("chunk")
        text = getattr(chunk, "content", "")
        if not text or not isinstance(text, str):
            return []
        span = self._spans.get(ev["run_id"])
        return [self._event(EventType.LLM_TOKEN, span.name if span else "llm", span.node_path if span else None, ev["run_id"], None, {"token": text})]

    def _on_chat_model_end(self, ev) -> list[TraceEvent]:
        output = ev.get("data", {}).get("output")
        usage = getattr(output, "usage_metadata", None) or {}
        self.total_tokens += int(usage.get("total_tokens") or 0)
        payload = {"output": self._json(output), "usage": self._json(usage)}
        return self._close(ev, EventType.LLM_COMPLETED, payload)

    # -- tools ---------------------------------------------------------------------------------
    def _on_tool_start(self, ev) -> list[TraceEvent]:
        return self._open(ev, "tool", EventType.TOOL_STARTED, ev.get("name", "tool"), {"input": self._json(ev.get("data", {}).get("input"))})

    def _on_tool_end(self, ev) -> list[TraceEvent]:
        output = ev.get("data", {}).get("output")
        failed = isinstance(output, ToolMessage) and output.status == "error"
        content = output.content if isinstance(output, BaseMessage) else output
        return self._close(ev, EventType.TOOL_FAILED if failed else EventType.TOOL_COMPLETED, {"output": self._json(content)})

    def _on_tool_error(self, ev) -> list[TraceEvent]:
        return self._close(ev, EventType.TOOL_FAILED, {"error": str(ev.get("data", {}).get("error"))})

    # -- custom events from agents --------------------------------------------------------------
    def _on_custom_event(self, ev) -> list[TraceEvent]:
        md = ev.get("metadata") or {}
        node_path = node_path_from_ns(md.get("langgraph_checkpoint_ns"))
        # Custom events carry no parent ids: attach them to the open node span.
        parent = self._parent(ev) or next(
            (sid for sid, sp in reversed(list(self._spans.items())) if sp.type == "node" and sp.node_path == node_path), None
        )
        return [
            self._event(
                EventType.CUSTOM,
                ev.get("name", "custom"),
                node_path,
                str(uuid.uuid4()),
                parent,
                {"data": self._json(ev.get("data"))},
            )
        ]
