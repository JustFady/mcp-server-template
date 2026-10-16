"""HTTP transport wiring: bearer-token auth and per-client rate limits around the SDK's Streamable HTTP app.

Tokens come from MCP_TOKENS as "name:token,name2:token2". Each tool call is one HTTP POST in
Streamable HTTP, so limiting POSTs per token per minute limits tool calls per client.
"""

from __future__ import annotations

import os
import secrets

from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from .ratelimit import SlidingWindow


def load_tokens(raw: str | None = None) -> dict[str, str]:
    """Parse "name:token,name2:token2" into {token: name}. Empty names or tokens are rejected."""
    raw = os.environ.get("MCP_TOKENS", "") if raw is None else raw
    tokens: dict[str, str] = {}
    for part in filter(None, (p.strip() for p in raw.split(","))):
        name, sep, token = part.partition(":")
        if not sep or not name.strip() or not token.strip():
            raise ValueError(f"bad MCP_TOKENS entry {part!r}; expected name:token")
        tokens[token.strip()] = name.strip()
    return tokens


class BearerAuth:
    """Pure-ASGI middleware: 401 without a known bearer token, 429 over the per-client limit."""

    def __init__(self, app, tokens: dict[str, str], per_minute: int = 60, exempt: tuple[str, ...] = ("/healthz",)) -> None:
        self.app = app
        self.tokens = tokens
        self.exempt = exempt
        self.limiter = SlidingWindow(per_minute)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in self.exempt:
            return await self.app(scope, receive, send)
        header = Headers(scope=scope).get("authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        name = self._match(token)
        if name is None:
            response = JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
            return await response(scope, receive, send)
        if scope["method"] == "POST" and not self.limiter.allow(name):
            retry = max(1, int(self.limiter.retry_after(name)) + 1)
            response = JSONResponse({"error": "rate limited", "retry_after": retry}, status_code=429,
                                    headers={"Retry-After": str(retry)})
            return await response(scope, receive, send)
        scope.setdefault("state", {})["mcp_client"] = name
        return await self.app(scope, receive, send)

    def _match(self, token: str) -> str | None:
        for known, name in self.tokens.items():
            if secrets.compare_digest(known, token):
                return name
        return None


def make_app(server, tokens: dict[str, str], per_minute: int = 60, host: str = "127.0.0.1", path: str = "/mcp",
             allowed_hosts: list[str] | None = None):
    """Starlette app: /healthz (open) and the MCP endpoint (bearer-protected, rate-limited).

    `allowed_hosts` feeds the SDK's DNS-rebinding protection: requests whose Host header is not
    listed get 421. Always include the public hostname (and host:port) clients will use.
    """
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts or [host, f"{host}:*", "localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"],
    )
    app = server.streamable_http_app(streamable_http_path=path, json_response=True, host=host, transport_security=security)
    app.router.routes.append(Route("/healthz", lambda _request: PlainTextResponse("ok")))
    app.add_middleware(BearerAuth, tokens=tokens, per_minute=per_minute)
    return app
