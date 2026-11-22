"""The VS Code extension (editors/vscode, L-world-class-183 and 845) calls
Tessellate's own routes: a rename here must fail CI rather than break the
extension silently. The tool-token tests replay the extension's own requests
against the real `/mcp` route and activate it against a stub `vscode`; node
runs the JavaScript, no VS Code is needed."""

from __future__ import annotations

import json
import re
import subprocess
import shutil
from pathlib import Path

import pytest

from tests.test_mcp_http import _made

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "editors" / "vscode"


def _routes(client) -> dict[str, set[str]]:
    paths = client.get("/openapi.json").json()["paths"]
    return {path: {method.upper() for method in methods} for path, methods in paths.items()}


def _client_routes() -> dict[str, str]:
    block = re.search(r"const ROUTES = \{(.*?)\};", (EXT / "lib/client.js").read_text(), re.S).group(1)
    return dict(re.findall(r'(\w+): "(/[^"]*)"', block))


def test_every_route_the_client_calls_exists(client) -> None:
    routes = _routes(client)
    wanted = {
        "status": "GET",
        "unlock": "POST",
        "entries": "POST",
        "search": "GET",
        "tools": "POST",
    }
    assert set(_client_routes()) == set(wanted)
    for name, path in _client_routes().items():
        assert wanted[name] in routes.get(path, set()), f"{wanted[name]} {path} is gone from the app"
    assert "GET" in routes["/entries/{entry_id}"]


def test_package_is_agpl_and_local_only() -> None:
    package = json.loads((EXT / "package.json").read_text())
    assert package["license"].startswith("AGPL-3.0")
    assert package["main"] == "./extension.js"
    declared = {c["command"] for c in package["contributes"]["commands"]}
    used = set(re.findall(r'registerCommand\(name|command\("(tessellate\.\w+)"', (EXT / "extension.js").read_text()))
    assert declared == used - {""}
    source = (EXT / "extension.js").read_text() + (EXT / "lib/client.js").read_text()
    assert not re.search(r"https?://(?!127\.0\.0\.1)[\w.-]", source), "the extension may only talk to this computer"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_client_node_tests_pass() -> None:
    done = subprocess.run(["node", "--test", "test/client.test.js"], cwd=EXT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout[-1500:]


def test_the_tools_a_tool_token_calls_take_what_the_client_sends(client) -> None:
    """L-world-class-627: with a tool server token the client calls three tools
    and reads `notes[].id`, `notes[].content`, `id` and `content` from their
    answers. A renamed argument or key fails here, not in someone's editor."""
    made = client.post("/mcp-clients", json={"name": "VS Code", "writes": True}).json()
    headers = {"Authorization": f"Bearer {made['token']}", "Accept": "application/json, text/event-stream"}

    def call(method, **params):
        reply = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)
        assert reply.status_code == 200, reply.text
        return reply.json()["result"]

    schemas = {tool["name"]: tool["inputSchema"]["properties"] for tool in call("tools/list")["tools"]}
    js = (EXT / "lib/client.js").read_text()
    assert {"query", "limit"} <= set(schemas["search_notes"]) and 'tool("search_notes", { query: q, limit:' in js
    assert "note_id" in schemas["get_note"] and 'tool("get_note", { note_id:' in js
    assert {"content", "tags"} <= set(schemas["create_note"]) and 'tool("create_note", { content, tags })' in js
    made_note = json.loads(call("tools/call", name="create_note", arguments={"content": "# Harbour\nboats", "tags": ["x"]})["content"][0]["text"])
    found = json.loads(call("tools/call", name="search_notes", arguments={"query": "harbour", "limit": 10})["content"][0]["text"])
    assert [n["id"] for n in found["notes"]] == [made_note["id"]] and "content" in found["notes"][0]
    read = json.loads(call("tools/call", name="get_note", arguments={"note_id": made_note["id"]})["content"][0]["text"])
    assert read["content"] == "# Harbour\nboats"


HARNESS = EXT / "test" / "harness.js"
URL = "http://127.0.0.1:8000"


def _node(job: dict) -> dict:
    done = subprocess.run(["node", str(HARNESS), json.dumps(job)], capture_output=True, text=True, timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _replay(client, sent: dict):
    """The extension's request, sent as it built it, to the real route."""
    assert sent["url"].endswith("/mcp") and sent["method"] == "POST"
    return client.post("/mcp", json=sent["body"], headers={**sent["headers"], "Accept": "application/json, text/event-stream"})


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


@needs_node
def test_a_search_from_the_extension_finds_the_note_and_links_to_it(client) -> None:
    writer = _made(client, name="VS Code", writes=True)
    note = client.post("/entries", json={"content": "Boiler service due in March\nCall the plumber first"}).json()
    sent = _node({"mode": "request", "url": URL + "/", "token": writer["token"],
                  "name": "search_notes", "args": {"query": "boiler", "limit": 10}})
    assert sent["url"] == URL + "/mcp", "a trailing slash must not double up"
    reply = _replay(client, sent)
    assert reply.status_code == 200, reply.text
    got = _node({"mode": "reply", "op": "search", "url": URL, "token": writer["token"], "status": 200, "body": reply.json()})
    (hit,) = [row for row in got["out"] if row["title"] == "Boiler service due in March"]
    assert hit["ref_id"] == note["id"], "the hit carries the id openNote opens as tessellate:/<id>.md"
    assert "Call the plumber first" in hit["snippet"]


@needs_node
def test_a_selection_saved_from_the_extension_is_a_note(client) -> None:
    writer = _made(client, name="VS Code", writes=True)
    sent = _node({"mode": "request", "url": URL, "token": writer["token"],
                  "name": "create_note", "args": {"content": "def retry(n): ...\nfrom the editor"}})
    reply = _replay(client, sent)
    made = json.loads(reply.json()["result"]["content"][0]["text"])
    assert made["id"] and "retry" in client.get(f"/entries/{made['id']}").json()["content"]


@needs_node
def test_a_read_only_token_cannot_save_and_the_extension_says_so(client) -> None:
    reader = _made(client, name="VS Code")
    sent = _node({"mode": "request", "url": URL, "token": reader["token"],
                  "name": "create_note", "args": {"content": "x"}})
    reply = _replay(client, sent)
    got = _node({"mode": "reply", "op": "capture", "url": URL, "token": reader["token"],
                 "status": reply.status_code, "body": reply.json()})
    assert got.get("error") and got["error"][0].isupper() and "{" not in got["error"], got
    assert "out" not in got


@needs_node
def test_a_refused_token_and_no_token_are_plain_sentences(client) -> None:
    sent = _node({"mode": "request", "url": URL, "token": "tsl_mcp_not_a_real_token",
                  "name": "search_notes", "args": {"query": "x"}})
    assert _replay(client, sent).status_code == 401
    got = _node({"mode": "reply", "op": "search", "url": URL, "token": "tsl_mcp_not_a_real_token", "status": 401, "body": {}})
    assert got == {"error": "Tessellate refused this token. Make a new one in Settings, Tools it can use."}
    none = _node({"mode": "reply", "op": "search", "url": URL, "token": "", "status": 401, "body": {}})
    assert none == {"error": "Sign in to Tessellate first."}


@needs_node
def test_activation_registers_the_commands_and_the_tool_server_for_chat() -> None:
    manifest = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    got = _node({"mode": "activate", "token": "tsl_mcp_abc"})
    assert set(got["commands"]) == {c["command"] for c in manifest["contributes"]["commands"]}
    assert got["provider"] == manifest["contributes"]["mcpServerDefinitionProviders"][0]["id"]
    (definition,) = got["defs"]
    assert definition["uri"]["value"] == "http://127.0.0.1:8123/mcp"
    assert definition["headers"] == {"Authorization": "Bearer tsl_mcp_abc"}
    assert _node({"mode": "activate"})["defs"] == [], "no token, no server offered"
    assert _node({"mode": "activate", "token": "a-password-session-token"})["defs"] == [], "a password session is not offered"
    assert int(manifest["engines"]["vscode"].lstrip("^").split(".")[1]) >= 101
