"""CLI: `mcp-template stdio` for local clients, `mcp-template http` for a network deployment."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .http import load_tokens, make_app
from .server import build_server


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mcp-template")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stdio", help="speak MCP over stdin/stdout (Claude Desktop, Claude Code, Cursor)")
    h = sub.add_parser("http", help="serve Streamable HTTP with bearer auth and rate limits")
    h.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    h.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")))
    h.add_argument("--rate", type=int, default=int(os.environ.get("MCP_RATE_PER_MINUTE", "60")), help="tool calls per client per minute")
    h.add_argument("--allowed-host", action="append", default=None,
                   help="Host header values clients will use (repeatable); default from MCP_ALLOWED_HOSTS or localhost only")
    h.add_argument("--insecure-no-auth", action="store_true", help="serve without tokens (local testing only)")
    args = p.parse_args(argv)

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s", stream=sys.stderr)
    server = build_server()
    if args.cmd == "stdio":
        server.run("stdio")
        return 0

    tokens = load_tokens()
    if not tokens and not args.insecure_no_auth:
        print("refusing to serve HTTP without MCP_TOKENS (name:token,...); pass --insecure-no-auth for local tests", file=sys.stderr)
        return 2
    import uvicorn

    allowed = args.allowed_host or [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()] or None
    app = make_app(server, tokens if tokens else {"dev": "dev"}, per_minute=args.rate, host=args.host, allowed_hosts=allowed)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
