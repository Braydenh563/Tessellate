"""The notebook as a local service for other agents (WORLD_CLASS_PLAN B8, H4).

- a Markdown skill dropped into the skills folder is runnable on the next
  request, without a restart, and leaves when the file does;
- `/api/v1/...` is the same API behind the same unlock, and only the API;
- a write by an outside agent (the MCP server's client, or an HTTP request
  naming itself in `X-MemoryMap-Agent`) is filed under that agent in the
  event log the activity panel reads.
"""

from __future__ import annotations

import os
import time

from tessellate.ai import skill_folder, skills, tools
from tessellate.core import deps
from tessellate.mcp_server import handle_request

SKILL = """---
description: Lists what is still open this week
when: on a Friday
tools: search_notes, list_notes
inputs: topic
---
Find this week's notes about {{topic}} and list what is still open.

## Steps
1. Search for notes about {{topic}} from the last seven days.
2. List the ones with an unticked checkbox,
   oldest first.
"""


def _names(client) -> set[str]:
    return {s["name"] for s in client.get("/skills").json()["skills"]}


def test_a_skill_file_is_listed_without_a_restart_and_leaves_with_the_file(client):
    where = skill_folder.folder(deps.get_config())
    assert "Weekly review" not in _names(client)
    (where / "Weekly review.md").write_text(SKILL, encoding="utf-8")
    body = client.get("/skills").json()
    found = next(s for s in body["skills"] if s["name"] == "Weekly review")
    assert found["folder"] is True and found["builtin"] is False
    assert found["tools"] == ["search_notes", "list_notes"]
    assert [i["name"] for i in found["inputs"]] == ["topic"]
    assert found["steps"] == [
        "Search for notes about {{topic}} from the last seven days.",
        "List the ones with an unticked checkbox, oldest first.",
    ]
    assert found["when_to_use"] == "on a Friday"
    assert body["folder"]["path"].endswith("skills")
    # The agent's own lookup finds it too: it is runnable, not only listed.
    assert skills.find(deps.get_config(), "Weekly review", set(tools.TOOLS))
    (where / "Weekly review.md").unlink()
    assert "Weekly review" not in _names(client)


def test_an_edited_file_is_read_again(client):
    where = skill_folder.folder(deps.get_config())
    path = where / "tidy.md"
    path.write_text("Tidy the inbox.", encoding="utf-8")
    first = next(s for s in client.get("/skills").json()["skills"] if s["name"] == "tidy")
    assert first["prompt"] == "Tidy the inbox."
    path.write_text("Tidy the inbox and the archive.", encoding="utf-8")
    later = time.time() + 5
    os.utime(path, (later, later))
    again = next(s for s in client.get("/skills").json()["skills"] if s["name"] == "tidy")
    assert again["prompt"] == "Tidy the inbox and the archive."


def test_a_file_that_does_not_load_says_why(client):
    where = skill_folder.folder(deps.get_config())
    (where / "loop.md").write_text("---\ntools: run_skill\n---\nRun yourself.", encoding="utf-8")
    (where / "Find loose ends.md").write_text("Shadow a built-in.", encoding="utf-8")
    problems = {p["file"]: p["message"] for p in client.get("/skills").json()["folder"]["problems"]}
    assert "would never have to stop" in problems["loop.md"]
    if any(s["name"] == "Find loose ends" for s in skills.builtins()):
        assert "already has" in problems["Find loose ends.md"]
    assert "loop" not in _names(client)


def test_a_folder_skill_is_not_deleted_by_the_agent(app_state, session):
    where = skill_folder.folder(app_state)
    (where / "mine.md").write_text("Do the thing.", encoding="utf-8")
    result = tools.execute_tool(session, "delete_skill", {"name": "mine"})
    assert "skills folder" in result.get("error", "")
    assert (where / "mine.md").exists()


def test_api_v1_is_the_same_api_behind_the_same_unlock(client):
    note = client.post("/api/v1/entries", json={"content": "From the versioned API"})
    assert note.status_code == 201, note.text
    assert note.headers["API-Version"] == "1"
    got = client.get(f"/api/v1/entries/{note.json()['id']}")
    assert got.status_code == 200
    assert got.json()["content"] == "From the versioned API"
    assert client.get("/api/v1/capabilities").json()["api"]["prefix"] == "/api/v1"
    assert client.get("/api/v1/openapi.json").status_code == 200
    # The page is not part of the API.
    assert client.get("/api/v1/").status_code == 404
    assert client.get("/api/v1/index.html").status_code == 404
    assert client.get("/api/v1/js/app.js").status_code == 404
    # The bare paths are unchanged.
    assert client.get("/entries").status_code == 200
    assert "API-Version" not in client.get("/entries").headers


def test_api_v1_is_locked_like_the_bare_api(app_state):
    """With a password set and no session, `/api/v1` answers 401 as `/` does."""
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app

    raw = TestClient(create_app())
    raw.post("/auth/setup", json={"password": "testpassword123"})
    fresh = TestClient(create_app())
    bare = fresh.get("/entries").status_code
    assert bare in (401, 403)
    assert fresh.get("/api/v1/entries").status_code == bare


def test_an_http_write_naming_an_agent_is_filed_under_it(client):
    r = client.post(
        "/api/v1/entries",
        json={"content": "Written by a coding agent"},
        headers={"X-MemoryMap-Agent": "Code helper"},
    )
    entry_id = r.json()["id"]
    feed = client.get("/events?tail=20").json()
    mine = [e for e in feed["items"] if e.get("entity_id") == entry_id]
    assert mine and all(e["actor"] == "agent:api@Code helper" for e in mine), mine


def test_an_mcp_write_is_filed_under_the_client(client):
    deps.get_config().set_preference("mcp_writes_enabled", True)
    handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "Desk assistant"}},
        }
    )
    response = handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "create_note", "arguments": {"content": "Saved over MCP"}},
        }
    )
    assert response["result"]["isError"] is False, response
    feed = client.get("/events?tail=20").json()
    actors = {e["actor"] for e in feed["items"] if e.get("action") == "created"}
    assert "agent:create_note@Desk assistant" in actors, actors


def test_the_page_names_an_agent_in_the_history_label():
    from tests._app_js import app_js_text

    text = app_js_text()
    assert 'kind === "agent"' in text
    assert "(agent)" in text
