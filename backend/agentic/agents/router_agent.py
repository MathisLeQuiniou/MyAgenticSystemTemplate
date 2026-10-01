from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from backend.agentic.agents.base import BaseAgent, load_prompt
from backend.agentic.agents.llm_agent import strip_thinking


class RouterAgent(BaseAgent):
    """Asks the LLM to pick one route among `routes` and stores it in the state.

    Use with a conditional edge:
        builder.add_conditional_edges(router.name, router.route, {"research": "researcher", ...})

    The answer is parsed leniently (first route name found in the text), falling
    back to `default` so a chatty model never breaks the graph.
    """

    def __init__(
        self,
        name: str,
        routes: dict[str, str],
        default: str,
        *,
        prompt: str = "router",
        state_key: str = "route",
        description: str = "",
        model_profile: str | None = None,
    ) -> None:
        super().__init__(name, description, model_profile)
        if default not in routes:
            raise ValueError(f"default route '{default}' not in routes")
        self.routes = routes
        self.default = default
        self.prompt_template = load_prompt(prompt)
        self.state_key = state_key

    def format_prompt(self, state: dict[str, Any]) -> str:
        routes = "\n".join(f"- {name}: {desc}" for name, desc in self.routes.items())
        return self.prompt_template.replace("{routes}", routes)

    def parse(self, text: str) -> str:
        text = strip_thinking(text).lower()
        positions = {r: text.find(r.lower()) for r in self.routes}
        found = {r: p for r, p in positions.items() if p >= 0}
        return min(found, key=found.get) if found else self.default

    async def run(self, state: dict[str, Any], config: RunnableConfig) -> dict[str, Any]:
        last_human = next((m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None)
        messages = [SystemMessage(self.format_prompt(state)), HumanMessage(str(last_human.content) if last_human else "")]
        response = await self.get_model(config).ainvoke(messages, config)
        route = self.parse(str(response.content))
        await self.emit("route_decision", {"route": route, "raw": str(response.content)[:500]}, config)
        return {self.state_key: route}

    def route(self, state: dict[str, Any]) -> str:
        """Condition function for `add_conditional_edges`."""
        return state.get(self.state_key) or self.default
