import asyncio
import inspect

from mcp.shared.exceptions import MCPError

from mcp_template.http import load_tokens
from mcp_template.middleware import GlobalToolBudget
from mcp_template.server import Backend, build_server


def _tools(server):
    tools = server.list_tools()
    if inspect.isawaitable(tools):
        tools = asyncio.run(tools)
    return {t.name: t for t in tools}


def test_tools_registered_with_model_facing_docs():
    tools = _tools(build_server())
    assert {"add", "lookup", "store"} <= tools.keys()
    for t in tools.values():
        assert t.description and len(t.description) > 30, f"{t.name} needs a real description"


def test_backend_is_swappable():
    class Fake(Backend):
        def __init__(self):
            self.calls = []

        def get(self, key):
            self.calls.append(key)
            return "fake"

    fake = Fake()
    server = build_server(backend=fake)
    assert "lookup" in _tools(server)
    assert fake.calls == []


def test_load_tokens():
    assert load_tokens("alice:abc,bob:def ") == {"abc": "alice", "def": "bob"}
    assert load_tokens("") == {}
    for bad in ("alice", "alice:", ":abc"):
        try:
            load_tokens(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should be rejected")


async def test_global_budget_raises_rate_limited():
    budget = GlobalToolBudget(per_minute=1)

    class Ctx:
        method = "tools/call"
        params = {"name": "add"}
        request_id = 1

    async def ok(ctx):
        return "result"

    assert await budget(Ctx(), ok) == "result"
    try:
        await budget(Ctx(), ok)
    except MCPError as e:
        assert e.code == -32001
    else:
        raise AssertionError("second call should be rate limited")
