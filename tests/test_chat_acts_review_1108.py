"""The review of the chat acts merged on 2026-11-08 (X17 cancel, X5 rename a
tag, category or note, X8 restore, X10 add to today): each finding is a test
that failed before its fix. Every provider runs against a fake transport
(CLAUDE.md section 4); the clock is fixed."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import commands, composer_cancel, starter_acts
from tessellate.core.database import Entry

NOW = datetime(2026, 11, 8, 10, 0)
HEADING = "# 2026-11-08"


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    from tessellate.api import routes_chat

    monkeypatch.setattr("tessellate.core.config.user_now", lambda _config: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _config: NOW)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _text(events) -> str:
    return " ".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def _card(client, said, **body):
    events = _events(client, said, **body)
    return next((e for e in events if e.get("type") == "act"), None), events


def _run(client, steps):
    return client.post("/chat/command/run", json={"steps": steps}).json()


def _note(client, content, **body):
    return client.post("/entries", json={"content": content, **body}).json()["id"]


def _seal(session, note_id):
    session.get(Entry, note_id).is_private = True
    session.commit()


def _tags(session, note_id):
    session.expire_all()
    return session.get(Entry, note_id).tags


# --- 1, 2, 11: a rename never merges, whatever hides the other holder ------------------------------


def test_a_locked_private_note_holding_the_new_tag_blocks_the_merge(client, session):
    public = [_note(client, f"# S{i}\n\nx", tags=["gym"]) for i in range(2)]
    secret = _note(client, "# Secret\n\nbody", tags=["fitness"])
    _seal(session, secret)
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "There is already a tag called “fitness”" in _text(events)
    assert [json.loads(_tags(session, i)) for i in public] == [["gym"]] * 2


def test_a_binned_note_holding_the_new_tag_blocks_the_merge(client, session):
    _note(client, "# S\n\nx", tags=["gym"])
    old = _note(client, "# Old\n\nx", tags=["fitness"])
    client.delete(f"/entries/{old}")
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "There is already a tag called “fitness”" in _text(events)


def test_a_binned_private_note_holding_the_old_tag_blocks_the_rename(client, session):
    _note(client, "# S\n\nx", tags=["gym"])
    secret = _note(client, "# Secret\n\nx", tags=["gym"])
    _seal(session, secret)
    client.delete(f"/entries/{secret}")
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "also on private notes" in _text(events)


def test_a_rename_touching_a_binned_note_undoes_exactly(client, session):
    live = _note(client, "# S\n\nx", tags=["gym", "legs"])
    binned = _note(client, "# Old\n\nx", tags=["legs", "gym"])
    client.delete(f"/entries/{binned}")
    before = (_tags(session, live), _tags(session, binned))
    card, _ = _card(client, "rename the tag gym to fitness")
    done = _run(client, card["steps"])
    assert done["ok"] and "fitness" in _tags(session, live) and "fitness" in _tags(session, binned)
    _run(client, done["undo"])
    assert sorted(json.loads(_tags(session, live))) == sorted(json.loads(before[0]))
    assert sorted(json.loads(_tags(session, binned))) == sorted(json.loads(before[1]))


def test_a_category_cannot_be_renamed_onto_one_that_only_a_binned_note_holds(client):
    _note(client, "# S\n\nx", category="Work")
    old = _note(client, "# Old\n\nx", category="Job")
    client.delete(f"/entries/{old}")
    card, events = _card(client, "rename the category Work to Job")
    assert card is None and "There is already a category called “Job”" in _text(events)


def test_the_confirm_route_runs_the_same_checks_as_the_planner(client, session):
    _note(client, "# S\n\nx", tags=["gym"])
    secret = _note(client, "# Secret\n\nx", tags=["fitness"])
    _seal(session, secret)
    done = _run(client, [{"name": "rename_tag", "arguments": {"old": "gym", "new": "fitness"}}])
    assert not done["ok"]
    assert json.loads(_tags(session, secret)) == ["fitness"]
    a = _note(client, "# A\n\nx", category="Work")
    _note(client, "# B\n\nx", category="Job")
    done = _run(client, [{"name": "rename_category", "arguments": {"old": "Work", "new": "Job"}}])
    assert not done["ok"] and client.get(f"/entries/{a}").json()["category"] == "Work"


def test_the_command_route_is_behind_the_apps_origin_check(client):
    """No route of its own: the app-wide Origin check refuses a page on another site."""
    step = [{"name": "rename_tag", "arguments": {"old": "gym", "new": "fitness"}}]
    refused = client.post("/chat/command/run", json={"steps": step}, headers={"Origin": "https://evil.example"})
    assert refused.status_code == 403
