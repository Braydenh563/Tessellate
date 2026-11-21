"""L114, driven both ways on the fake transport: the five parity sentences (a board, a mind map, rename a tag, delete a tag,
remember a preference) reach their tools from the composer with no model AND from a model that calls the tool itself. Either
way the write waits for Confirm, runs once, and Undo puts the notebook back. The 1.5B's own run is `pytest -m evals`
(the developer's local llama-server); this pins everything around it. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from tessellate.core.database import Entry, UserPreference
from tessellate.entry import manager

from tests.test_engine_routing_1114 import _fixed_now  # noqa: F401  (autouse clock)
from tests.test_parity_acts_1110 import card_of, confirm, notebook, stream, undo  # noqa: F401


def _events(client, question: str) -> list[dict]:
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


def _parked(events: list[dict]) -> list[dict]:
    """A model's own write call waits as a `confirm` event (`consent_id`); Confirm presses it through /chat/tools/execute."""
    return [e for e in events if e["type"] == "confirm"]


def _notebook_state(session) -> tuple:
    session.expire_all()
    notes = tuple(sorted((e.id, e.content, tuple(sorted(json.loads(e.tags or "[]"))), e.is_board) for e in session.scalars(select(Entry)) if e.deleted_at is None))
    return notes, tuple(sorted(p.content for p in session.scalars(select(UserPreference))))


#: (the sentence, the tool call a model makes for it, the tool the card runs)
CASES = [
    ("Make a board called Launch", {"name": "create_mindmap", "arguments": {"title": "Launch", "kind": "board"}}, "create_mindmap"),
    ("Make a mind map of Trips", {"name": "create_mindmap", "arguments": {"title": "Trips"}}, "create_mindmap"),
    ("Rename the tag harbor to docks", {"name": "rename_tag", "arguments": {"old": "harbor", "new": "docks"}}, "rename_tag"),
    ("Delete the tag harbor", {"name": "delete_tag", "arguments": {"name": "harbor"}}, "delete_tag"),
    ("Remember that I prefer short answers", {"name": "save_user_preference", "arguments": {"preference": "Prefers short answers"}}, "save_user_preference"),
]


@pytest.mark.parametrize(("said", "call", "tool"), CASES, ids=[c[2] + ":" + c[0][:12] for c in CASES])
def test_the_composer_path_parks_the_card_and_undo_restores(client, notebook, said, call, tool):  # noqa: F811
    manager.create_entry(notebook, "# Dock notes\n\nTide tables.", tags=["harbor"])
    notebook.commit()
    before = _notebook_state(notebook)
    card = card_of(stream(client, said))
    assert [s["name"] for s in card["steps"]] == [tool]
    assert _notebook_state(notebook) == before, "nothing changes before Confirm"
    done = confirm(client, card)
    assert done["ok"] and _notebook_state(notebook) != before
    undo(client, done)
    assert _notebook_state(notebook) == before


@pytest.mark.parametrize(("said", "call", "tool"), CASES, ids=[c[2] + ":" + c[0][:12] for c in CASES])
def test_a_model_that_calls_the_tool_is_parked_for_confirm(ai_client, fake_ollama, session, said, call, tool):
    manager.create_entry(session, "# Dock notes\n\nTide tables.", tags=["harbor"])
    session.commit()
    before = _notebook_state(session)
    fake_ollama.tool_script = [[call], []]
    events = _events(ai_client, said)
    parked = _parked(events)
    if tool == "save_user_preference":
        #: A suggestion is not a write to the notebook: it runs at once as a row that waits in Settings for an answer, never accepted.
        ran = [e for e in events if e["type"] == "tool" and e.get("tool") == tool]
        assert ran and not parked, [e["type"] for e in events]
        session.expire_all()
        rows = list(session.scalars(select(UserPreference)))
        assert [r.proposed for r in rows] == [True], "suggested, not accepted"
        return
    assert parked and parked[0]["name"] == tool, [e["type"] for e in events]
    assert _notebook_state(session) == before, "a model's write waits for Confirm"
    ran = ai_client.post("/chat/tools/execute", json={"name": tool, "arguments": parked[0]["arguments"], "consent_id": parked[0]["consent_id"]})
    assert ran.status_code == 200, ran.text
    assert _notebook_state(session) != before
    assert ran.json().get("undo"), "every one of these has an Undo"
    step = ran.json()["undo"]
    undone = ai_client.post("/chat/tools/execute", json={"name": step["tool"], "arguments": step.get("arguments") or {}, "steps": step.get("steps") or []})
    assert undone.status_code == 200, undone.text
    assert _notebook_state(session) == before
