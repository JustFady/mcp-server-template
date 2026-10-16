from starlette.testclient import TestClient

from mcp_template.http import make_app
from mcp_template.server import build_server

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
}


def client(per_minute: int = 60) -> TestClient:
    app = make_app(build_server(), {"secret-a": "alice"}, per_minute=per_minute, allowed_hosts=["testserver"])
    return TestClient(app)


def test_unknown_host_is_rejected():
    app = make_app(build_server(), {"secret-a": "alice"}, allowed_hosts=["mcp.example.com"])
    with TestClient(app) as c:
        r = c.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": "Bearer secret-a"})
        assert r.status_code == 421


def test_health_is_open():
    with client() as c:
        assert c.get("/healthz").status_code == 200


def test_mcp_requires_bearer_token():
    with client() as c:
        r = c.post("/mcp", json=INIT, headers=HEADERS)
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"
        r = c.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": "Bearer wrong"})
        assert r.status_code == 401


def test_initialize_with_token_succeeds():
    with client() as c:
        r = c.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": "Bearer secret-a"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["result"]["serverInfo"]["name"] == "mcp-template"
        assert r.headers.get("mcp-session-id")


def test_per_client_rate_limit_returns_429():
    with client(per_minute=2) as c:
        auth = {**HEADERS, "Authorization": "Bearer secret-a"}
        assert c.post("/mcp", json=INIT, headers=auth).status_code == 200
        c.post("/mcp", json=INIT, headers=auth)
        r = c.post("/mcp", json=INIT, headers=auth)
        assert r.status_code == 429
        assert int(r.headers["retry-after"]) >= 1
