"""The VS Code extension (L-world-class-183, INBOX 1862) speaks to the real
tool server: the request `tools/vscode/client.js` builds is replayed here
against `POST /mcp` with a real token, and the real reply goes back through
the extension's own parsing. Node runs the JavaScript; no VS Code is needed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_mcp_http import _made

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "vscode" / "test" / "harness.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def _node(job: dict) -> dict:
    done = subprocess.run(
        ["node", str(HARNESS), json.dumps(job)], capture_output=True, text=True, timeout=30, check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _replay(client, sent: dict):
    """The extension's request, sent as it built it, to the real route."""
    assert sent["url"].endswith("/mcp") and sent["method"] == "POST"
    return client.post("/mcp", json=sent["body"], headers=sent["headers"])


def test_a_search_from_the_extension_finds_the_note_and_links_to_it(client):
    writer = _made(client, name="VS Code", writes=True)
    client.post("/entries", json={"content": "Boiler service due in March\nCall the plumber first"})
    sent = _node({"mode": "request", "url": "http://127.0.0.1:8000/", "token": writer["token"],
                  "name": "search_notes", "args": {"query": "boiler", "limit": 10}})
    assert sent["url"] == "http://127.0.0.1:8000/mcp", "a trailing slash must not double up"
    reply = _replay(client, sent)
    assert reply.status_code == 200, reply.text
    got = _node({"mode": "reply", "url": "http://127.0.0.1:8000", "token": "t", "status": 200, "body": reply.json()})
    assert got["out"]["found"] >= 1
    (item,) = [row for row in got["items"] if row["label"] == "Boiler service due in March"]
    assert item["detail"] == "Call the plumber first"
    assert got["link"] == "http://127.0.0.1:8000/#/notes/7", "the app's own deep link (router.js)"


def test_a_selection_saved_from_the_extension_is_a_note(client):
    writer = _made(client, name="VS Code", writes=True)
    sent = _node({"mode": "request", "url": "http://127.0.0.1:8000", "token": writer["token"],
                  "name": "create_note", "args": {"content": "def retry(n): ...\nfrom the editor"}})
    reply = _replay(client, sent)
    made = json.loads(reply.json()["result"]["content"][0]["text"])
    assert made["id"] and "retry" in client.get(f"/entries/{made['id']}").json()["content"]


def test_a_read_only_token_cannot_save_and_the_extension_says_so(client):
    reader = _made(client, name="VS Code")
    sent = _node({"mode": "request", "url": "http://127.0.0.1:8000", "token": reader["token"],
                  "name": "create_note", "args": {"content": "x"}})
    reply = _replay(client, sent)
    got = _node({"mode": "reply", "url": "u", "token": "t", "status": reply.status_code, "body": reply.json()})
    assert got.get("typed") is True and got["error"], got


def test_a_refused_token_and_no_token_are_plain_sentences(client):
    sent = _node({"mode": "request", "url": "http://127.0.0.1:8000", "token": "tsl_not_a_real_token",
                  "name": "search_notes", "args": {"query": "x"}})
    reply = _replay(client, sent)
    assert reply.status_code == 401
    got = _node({"mode": "reply", "url": "u", "token": "t", "status": 401, "body": {}})
    assert got == {"error": "That token was refused. Make a new one in Settings, Tools it can use.", "typed": True}
    none = _node({"mode": "reply", "url": "u", "token": "", "status": 200, "body": {}})
    assert none["typed"] and "Set a tool server token first" in none["error"]


def test_activation_registers_the_commands_and_the_tool_server_for_chat():
    got = _node({"mode": "activate", "token": "tsl_abc"})
    manifest = json.loads((ROOT / "tools" / "vscode" / "package.json").read_text(encoding="utf-8"))
    declared = {c["command"] for c in manifest["contributes"]["commands"]}
    assert set(got["commands"]) == declared
    assert got["provider"] == manifest["contributes"]["mcpServerDefinitionProviders"][0]["id"]
    (definition,) = got["defs"]
    assert definition["uri"]["value"] == "http://127.0.0.1:8123/mcp"
    assert definition["headers"] == {"Authorization": "Bearer tsl_abc"}
    assert _node({"mode": "activate"})["defs"] == [], "no token, no server offered"
