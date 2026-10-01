"""
Demo MCP tool server (streamable HTTP).

Start alone:   python -m backend.tool_servers.demo_server --port 8001
Or with all:   python -m backend.tool_servers
"""
from __future__ import annotations

import argparse
import ast
import operator

from mcp.server.fastmcp import FastMCP

# --- A tiny knowledge base ---------------------------------------------------
KNOWLEDGE_BASE = {
    "langgraph": "LangGraph is a library for building stateful, multi-actor LLM applications as graphs of nodes and edges, with checkpointing and human-in-the-loop.",
    "mcp": "The Model Context Protocol (MCP) is an open protocol that standardises how applications expose tools, resources and prompts to LLMs.",
    "fastapi": "FastAPI is a modern, high-performance Python web framework based on type hints and Starlette.",
    "postgres": "PostgreSQL is an open-source relational database. Here it stores runs, trace events and LangGraph checkpoints.",
    "react flow": "React Flow is a library for building node-based UIs; the frontend uses it to draw the agentic graph.",
}

# --- Safe calculator ---------------------------------------------------------
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expression")

def main() -> None:
    # --- MCP server initialization -------------------------------------------
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    mcp = FastMCP(
        "demo",
        log_level="INFO",
        host=args.host,
        port=args.port,
    )

    # --- Tools definition ----------------------------------------------------
    @mcp.tool()
    def calculate(expression: str) -> str:
        """Evaluate an arithmetic expression, e.g. '(12 + 30) * 2 / 3'. Supports + - * / ** % //."""
        try:
            return str(_eval(ast.parse(expression, mode="eval")))
        except Exception as exc:  # noqa: BLE001
            return f"Error: cannot evaluate '{expression}' ({exc})"

    @mcp.tool()
    def search_knowledge_base(query: str) -> str:
        """Search the internal knowledge base for documentation about a technical topic."""
        q = query.lower()
        hits = [f"- {k}: {v}" for k, v in KNOWLEDGE_BASE.items() if k in q or any(w in k for w in q.split() if len(w) > 3)]
        return "\n".join(hits) if hits else f"No entry found for '{query}'. Known topics: {', '.join(KNOWLEDGE_BASE)}."

    # --- Start the server ----------------------------------------------------
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
