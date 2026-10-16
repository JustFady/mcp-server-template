# mcp-server-template

Reusable base for client MCP-server projects (Engine 1, Offer B). Python 3.11+, `mcp` 2.x (`MCPServer`), Starlette, uvicorn; run with `.venv/bin/python`.

- Tools live in `src/mcp_template/server.py` (`build_server(backend)`); auth + per-client limits in `http.py` (pure ASGI middleware around `server.streamable_http_app(json_response=True)`); MCP-level logging/budget in `middleware.py`.
- Tests: `.venv/bin/python -m pytest -q` (TestClient drives the real transport; `initialize` must return 200 + `mcp-session-id`).
- For a client project: copy the repo, rename the package, replace `Backend` and the tools, keep the tests green, add the client's auth story.
- Never commit tokens; `MCP_TOKENS` is env-only.
