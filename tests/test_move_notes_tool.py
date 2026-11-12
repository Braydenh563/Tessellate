"""The agent's `move_notes` tool (OPEN row 1374, BACKLOG 14): chosen notes into a
category or another space, asked first, and undoable. Driven the way the app
drives it: the Confirm click posts the call to `/chat/tools/execute`, and the
Undo posts back the call the result carried."""

from __future__ import annotations

from tests._tool_sig import call

from tessellate.ai import tools


def _note(client, text, category="Garden"):
    reply = client.post("/entries", json={"content": text, "category": category})
    assert reply.status_code == 201, reply.text
    return reply.json()


def _category_of(client, note_id, workspace=None):
    headers = {"X-Workspace-ID": workspace} if workspace else {}
    return client.get(f"/entries/{note_id}", headers=headers).json()["category"]


def _run(client, arguments):
    reply = client.post("/chat/tools/execute", json=call("move_notes", arguments))
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_it_asks_first_and_names_what_will_move(client):
    spec = tools.TOOLS["move_notes"]
    assert spec.destructive is True  # the app confirms; it never runs inside the loop
    assert "move_notes" in tools.WRITE_TOOLS
    sentence = tools.confirm_label("move_notes", {"ids": [1, 2], "category": "Travel"})
    assert sentence == "Move 2 notes to the category “Travel”"
    assert tools.confirm_label("move_notes", {"ids": [1], "space": "Work"}) == "Move 1 note to the space “Work”"


def test_a_category_move_and_its_undo_put_every_note_back(client):
    a = _note(client, "Beans in May", "Garden")
    b = _note(client, "Passport", "Travel")
    done = _run(client, {"ids": [a["id"], b["id"]], "category": "Plans"})
    assert done["label"].endswith("Moved 2 notes to “Plans”")
    assert _category_of(client, a["id"]) == _category_of(client, b["id"]) == "Plans"
    _run(client, done["undo"]["arguments"] | {})  # the Undo posts the call it was given
    assert (_category_of(client, a["id"]), _category_of(client, b["id"])) == ("Garden", "Travel")


def test_the_undo_is_the_same_tool_so_it_is_one_door(client):
    a = _note(client, "Beans", "Garden")
    done = _run(client, {"ids": [a["id"]], "category": "Plans"})
    assert done["undo"]["tool"] == "move_notes"
    reply = client.post("/chat/tools/execute", json={"name": "move_notes", "arguments": done["undo"]["arguments"], "sig": done["undo"]["sig"]})
    assert reply.status_code == 200 and reply.json()["label"].endswith("Put 1 note back")
    assert _category_of(client, a["id"]) == "Garden"


def test_a_space_move_carries_the_category_and_the_undo_returns_it(client):
    a = _note(client, "Hotel in Kyoto", "Travel")
    done = _run(client, {"ids": [a["id"]], "space": "work"})
    assert "to the space" in done["label"]
    assert _category_of(client, a["id"], "work") == "Travel"
    _run(client, done["undo"]["arguments"])
    assert _category_of(client, a["id"]) == "Travel"  # back in the default space
    assert client.get(f"/entries/{a['id']}", headers={"X-Workspace-ID": "work"}).status_code in (404, 200)


def test_it_refuses_a_bad_call_and_changes_nothing(client):
    a = _note(client, "Stay", "Garden")
    for arguments in (
        {"ids": [a["id"]]},  # no destination
        {"ids": [a["id"]], "category": "X", "space": "work"},  # two destinations
        {"ids": [999999], "category": "X"},  # not a note
        {"ids": list(range(1, 102)), "category": "X"},  # too many at once
        {"ids": [a["id"]], "space": "nowhere"},
    ):
        result = tools.execute_tool(_session(client), "move_notes", arguments)
        assert "error" in result, arguments
    assert _category_of(client, a["id"]) == "Garden"


def test_a_note_already_there_is_said_not_moved(client):
    a = _note(client, "Stay", "Garden")
    done = _run(client, {"ids": [a["id"]], "category": "Garden"})
    assert "Already in" in done["label"] and done["undo"] is None


def _session(client):  # noqa: ANN001
    from tessellate.core import deps

    return deps.get_db().session()


def test_the_agent_loop_parks_a_move_for_the_users_yes_and_never_runs_it(monkeypatch, app_state):
    """Asked first, in the loop itself: the model's call becomes a confirm card
    saying what will move, and the handler is never reached until the click."""
    import pytest

    from tessellate.ai import agent
    from tests.test_agent_recovery import _FakeModels, _FakeOllama, _Session

    call = {"name": "move_notes", "arguments": {"ids": [1, 2], "category": "Travel"}}
    fake = _FakeOllama([[call], []])
    monkeypatch.setattr(agent.tools, "ollama_tools", lambda allowed=None: [])
    monkeypatch.setattr(agent.tools, "execute_tool", lambda *a, **k: pytest.fail("a move ran without a yes"))
    events = list(agent.run_agent(_Session(), "file my trip notes under Travel", [], _FakeModels(), fake))
    confirms = [e for e in events if e.get("type") == "confirm"]
    assert len(confirms) == 1
    assert "Move 2 notes to the category “Travel”" in str(confirms[0])
