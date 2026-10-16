"""The MCP server: tools go here. Everything else (auth, limits, logging, transport) is wired around it.

Replace the example tools with your product's operations. Keep tool docstrings written for the
model: what the tool does, when to use it, what it returns, and what it must not be used for.
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from .middleware import GlobalToolBudget, call_logger


class Backend:
    """Swap this for your real API client. Keeping it a class makes tests trivial to fake."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {"hello": "world"}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def put(self, key: str, value: str) -> None:
        self._store[key] = value


def build_server(backend: Backend | None = None, global_budget_per_minute: int = 600) -> MCPServer:
    be = backend or Backend()
    server = MCPServer(
        name="mcp-template",
        version="0.1.0",
        instructions=(
            "Example server. Use `lookup` to read a value, `store` to write one, and `add` for arithmetic. "
            "Writes are rate limited per client; if you receive a rate-limit error, wait and retry once."
        ),
        middleware=[call_logger, GlobalToolBudget(global_budget_per_minute)],
    )

    @server.tool()
    def add(a: float, b: float) -> dict[str, float]:
        """Add two numbers and return {"sum": a + b}. Use for arithmetic the model should not do mentally."""
        return {"sum": a + b}

    @server.tool()
    def lookup(key: str) -> dict[str, Any]:
        """Read the value stored under `key`. Returns {"key", "value", "found"}; never raises for a missing key."""
        value = be.get(key)
        return {"key": key, "value": value, "found": value is not None}

    @server.tool()
    def store(key: str, value: str) -> dict[str, Any]:
        """Store `value` under `key`, overwriting any previous value. Keys are case-sensitive and max 64 chars."""
        if not key or len(key) > 64:
            raise ValueError("key must be 1-64 characters")
        be.put(key, value)
        return {"key": key, "stored": True}

    return server


server = build_server()
