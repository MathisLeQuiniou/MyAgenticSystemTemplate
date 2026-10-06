"""Deterministic offline chat model.

Lets you run the whole stack (graph, tools, tracing, frontend) without any LLM:
- with tools bound and no tool result yet -> calls the most relevant tool,
- otherwise -> answers with a short text built from the conversation.
Routers get a plain text answer; they fall back to their default route.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool


def _text(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return str(content)


class FakeToolCallingChatModel(BaseChatModel):
    model_name: str = "fake"
    tools: list[dict[str, Any]] = []

    @property
    def _llm_type(self) -> str:
        return "fake-tool-calling"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> FakeToolCallingChatModel:  # type: ignore[override]
        specs = [convert_to_openai_tool(t)["function"] for t in tools]
        return self.model_copy(update={"tools": specs})

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _last_human(messages: list[BaseMessage]) -> str:
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                return str(m.content)
        return ""

    def _pick_tool(self, text: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        words = set(re.findall(r"\w+", text.lower()))
        if re.search(r"\d\s*[-+*/%€]\s*\d?", text):
            words |= {"calculate", "math"}
        best = max(tools, key=lambda t: len(words & set(re.findall(r"\w+", (t["name"] + " " + t.get("description", "")).lower()))))
        return best

    @staticmethod
    def _fill_args(spec: dict[str, Any], text: str) -> dict[str, Any]:
        props = spec.get("parameters", {}).get("properties", {})
        required = spec.get("parameters", {}).get("required", list(props))
        args: dict[str, Any] = {}
        expr = re.search(r"[\d\s.()+\-*/]{3,}", text)
        for name in required:
            ptype = props.get(name, {}).get("type", "string")
            if ptype in ("integer", "number"):
                args[name] = 1
            elif ptype == "boolean":
                args[name] = True
            elif name in ("expression", "expr") and expr:
                args[name] = expr.group(0).strip()
            else:
                args[name] = text
        return args

    # Stop words ignored when matching a question to a skill (English + French questions).
    _STOP = {"the", "for", "any", "use", "and", "with", "what", "how", "une", "des", "les", "est", "quel", "quelle"}

    def _words(self, text: str) -> set[str]:
        return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 3 and w not in self._STOP}

    def _next_tool_call(self, question: str, system: str, turn: list[BaseMessage]) -> dict[str, Any] | None:
        """Scripted behaviour: (load a matching skill -> read its first file) -> one real tool -> answer."""
        called = [tc["name"] for m in turn if isinstance(m, AIMessage) for tc in m.tool_calls]
        names = {t["name"] for t in self.tools}
        # 1. Skill: load the first catalog entry sharing words with the question.
        if "load_skill" in names and "load_skill" not in called:
            for name, desc in re.findall(r"^- `([\w-]+)`: (.+)$", system, re.MULTILINE):
                if self._words(question) & self._words(desc):
                    return {"name": "load_skill", "args": {"name": name}}
        # 2. Skill file: open the first file listed by load_skill.
        if "load_skill" in called and "read_skill_file" not in called:
            loaded = next((m for m in reversed(turn) if isinstance(m, ToolMessage) and m.name == "load_skill"), None)
            files = re.search(r"open with read_skill_file\): (.+)$", _text(loaded.content) if loaded else "", re.MULTILINE)
            skill = re.search(r"# Skill: ([\w-]+)", _text(loaded.content) if loaded else "")
            if files and skill:
                return {"name": "read_skill_file", "args": {"name": skill.group(1), "path": files.group(1).split(",")[0].strip()}}
        # 3. One regular tool per turn.
        regular = [t for t in self.tools if t["name"] not in ("load_skill", "read_skill_file")]
        if regular and not any(n not in ("load_skill", "read_skill_file") for n in called):
            spec = self._pick_tool(question, regular)
            return {"name": spec["name"], "args": self._fill_args(spec, question)}
        return None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        question = self._last_human(messages)
        # Messages after the last human turn = what happened in this turn.
        idx = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
        turn = messages[idx + 1 :]
        tool_results = [m for m in turn if isinstance(m, ToolMessage)]
        system = next((str(m.content) for m in messages if isinstance(m, SystemMessage)), "")

        tool_call = self._next_tool_call(question, system, turn) if self.tools else None
        if tool_call:
            message = AIMessage(content="", tool_calls=[{**tool_call, "id": f"call_{uuid.uuid4().hex[:8]}"}])
        else:
            if tool_results:
                facts = "; ".join(_text(m.content)[:300] for m in tool_results if m.name not in ("load_skill", "read_skill_file"))
                content = f"[fake] Based on the tools ({facts}), here is my answer to: {question}"
            elif "route" in system.lower():
                content = "research"
            else:
                previous = next((str(m.content) for m in reversed(turn) if isinstance(m, AIMessage) and m.content), "")
                content = f"[fake] Final answer to '{question}'." + (f" Findings: {previous[:400]}" if previous else "")
            message = AIMessage(content=content)

        prompt_tokens = sum(len(str(m.content).split()) for m in messages)
        completion_tokens = len(str(message.content).split()) + len(json.dumps(message.tool_calls)) // 4
        message.usage_metadata = {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        message.response_metadata = {"model_name": self.model_name}
        return ChatResult(generations=[ChatGeneration(message=message)])
