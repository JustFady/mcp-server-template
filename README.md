# mcp-server-template

A starting point for MCP servers that are going in front of real users, not just a demo. Clone it, replace the three example tools with your product's operations, and you already have:

- **Bearer-token auth** on the HTTP transport (`MCP_TOKENS="alice:token1,bob:token2"`), constant-time compare, `401` + `WWW-Authenticate` on failure
- **Per-client rate limits** (sliding window per token, `429` + `Retry-After`) and a process-wide tool budget as defense in depth
- **Host allow-list** (the SDK's DNS-rebinding protection, configured instead of disabled)
- **Structured call logging**: one JSON line per request with method, tool, duration, outcome
- **stdio and Streamable HTTP** from the same code (`mcp-template stdio` / `mcp-template http`)
- **Tests** that run without a network (Starlette TestClient against the real transport), **CI** on Linux and macOS, a **Dockerfile** that runs as non-root
- Tool docstrings written for the model, and a swappable `Backend` class so tests never touch your real API

Built on the official Python SDK (`mcp` 2.x, `MCPServer`).

## Quickstart

```bash
git clone https://github.com/JustFady/mcp-server-template my-server && cd my-server
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -q

# local, for Claude Desktop / Claude Code / Cursor
.venv/bin/mcp-template stdio

# network
MCP_TOKENS="alice:$(openssl rand -hex 24)" .venv/bin/mcp-template http --host 0.0.0.0 --port 8000 --rate 60
curl -s localhost:8000/healthz
```

Claude Code: `claude mcp add my-server -- /path/to/.venv/bin/mcp-template stdio`

Claude Desktop (`claude_desktop_config.json`):

```json
{ "mcpServers": { "my-server": { "command": "/path/to/.venv/bin/mcp-template", "args": ["stdio"] } } }
```

Remote clients connect to `https://your-host/mcp` with `Authorization: Bearer <token>`. Set the public hostname so the SDK's DNS-rebinding protection accepts it: `--allowed-host mcp.example.com` (repeatable) or `MCP_ALLOWED_HOSTS=mcp.example.com,mcp.example.com:443`. Unknown `Host` headers get `421`.

## Adapting it to your product

1. `src/mcp_template/server.py`: replace `Backend` with your API client and the example tools with 5–10 operations your users actually ask for. Keep return values small and structured; the model reads them every call.
2. Write each docstring as instructions to the model: what it does, when to use it, what it returns, what it must not be used for.
3. `tests/`: fake the backend; assert tool names, descriptions and error behavior.
4. Decide limits: `--rate` per client per minute; `GlobalToolBudget` per process.
5. Put it behind TLS (a reverse proxy or your platform's ingress). Rotate tokens by editing `MCP_TOKENS` and restarting.

## Layout

```
src/mcp_template/
  server.py      tools + build_server()
  http.py        BearerAuth ASGI middleware, make_app()
  middleware.py  call_logger, GlobalToolBudget (MCP-level middleware)
  ratelimit.py   SlidingWindow
  __main__.py    CLI
tests/           ratelimit, server, http (real transport via TestClient)
Dockerfile, .github/workflows/ci.yml
```

## Docker

```bash
docker build -t my-mcp .
docker run --rm -p 8000:8000 -e MCP_TOKENS="alice:changeme" my-mcp
```

## Why not OAuth?

For a server you operate for a known set of clients, static bearer tokens over TLS are simpler to run and to audit. The SDK supports full OAuth (`AuthSettings` + a `TokenVerifier`) when you need third-party clients to self-register; this template leaves that door open rather than making you walk through it on day one.

## License

MIT © Fady Youssef
