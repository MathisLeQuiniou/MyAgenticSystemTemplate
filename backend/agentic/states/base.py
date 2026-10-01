"""Base graph state.

States are `TypedDict`s (LangGraph's native format): cheap, serialisable by the
checkpointer and easy to extend. Subclass `BaseState` and add your own keys:

    class MyState(BaseState):
        route: NotRequired[str]
        documents: Annotated[list[str], append_list]
"""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import NotRequired, TypedDict

from backend.agentic.states.reducers import increment, merge_dict


class BaseState(TypedDict):
    # Conversation shared by every agent. `add_messages` appends / updates by id.
    messages: Annotated[list[AnyMessage], add_messages]
    # Free-form scratchpad shared between agents (merged, never overwritten).
    context: NotRequired[Annotated[dict[str, Any], merge_dict]]


class AgentLoopState(TypedDict):
    """Private state of an `LLMAgent` tool loop (a subgraph).

    Only `messages` is shared with the parent graph; `iterations` lives in the
    subgraph and resets on every call.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    iterations: NotRequired[Annotated[int, increment]]
