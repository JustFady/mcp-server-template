"""MCP-level middleware: structured logging of every request, plus a global call budget.

Per-client limits live at the HTTP layer (see http.py) where the caller's identity is known.
This layer sees every JSON-RPC method regardless of transport, so it is the right place to log
and to apply a process-wide ceiling as defense in depth.
"""

from __future__ import annotations

import json
import logging
import time

from mcp.shared.exceptions import MCPError

from .ratelimit import SlidingWindow

log = logging.getLogger("mcp_template.calls")
RATE_LIMITED = -32001  # implementation-defined JSON-RPC error code


def _tool_name(ctx) -> str | None:
    params = getattr(ctx, "params", None)
    if isinstance(params, dict):
        return params.get("name")
    return None


async def call_logger(ctx, call_next):
    """Log method, tool name, duration and outcome for every inbound request."""
    start = time.perf_counter()
    record = {"method": ctx.method, "tool": _tool_name(ctx), "request_id": ctx.request_id}
    try:
        result = await call_next(ctx)
        record.update(status="ok", ms=round((time.perf_counter() - start) * 1000, 1))
        log.info(json.dumps(record))
        return result
    except MCPError as e:
        record.update(status="error", code=e.code, message=e.message, ms=round((time.perf_counter() - start) * 1000, 1))
        log.warning(json.dumps(record))
        raise
    except Exception as e:  # noqa: BLE001 - log then let the SDK turn it into an internal error
        record.update(status="exception", error=type(e).__name__, ms=round((time.perf_counter() - start) * 1000, 1))
        log.exception(json.dumps(record))
        raise


class GlobalToolBudget:
    """Process-wide ceiling on tools/call per minute, regardless of client."""

    def __init__(self, per_minute: int = 600) -> None:
        self.window = SlidingWindow(per_minute)

    async def __call__(self, ctx, call_next):
        if ctx.method == "tools/call" and not self.window.allow("global"):
            raise MCPError(RATE_LIMITED, "server busy: global tool budget exceeded, retry shortly")
        return await call_next(ctx)
