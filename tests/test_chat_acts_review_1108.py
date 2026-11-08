"""The review of the chat acts merged on 2026-11-08 (X17 cancel, X5 rename a
tag, category or note, X8 restore, X10 add to today): each finding is a test
that failed before its fix. Every provider runs against a fake transport
(CLAUDE.md section 4); the clock is fixed."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import commands
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


# --- 3, 7, 8: reading a rename or a restore ----------------------------------------------------


def _read(said):
    return commands.read_typed(said, NOW)


@pytest.mark.parametrize("said", ["rename note 12 to Travel", "rename the note 12 to Travel", "rename note #12 to Travel", "rename #12 to Travel"])
def test_a_note_named_by_its_number_keeps_its_id(said):
    found = _read(said)
    assert found and found["intent"] == "rename" and found["note_id"] == 12 and found["title"] == "Travel", said


def test_a_rename_by_number_reaches_that_note_not_a_title_with_the_number(client):
    for i in range(12):
        _note(client, f"# Filler {i}\n\nx")
    lease = _note(client, "# Flat 12 lease\n\nRoom 12.")
    target = _note(client, "# Passport\n\nRenew.")
    card, _ = _card(client, f"rename note {target} to Travel")
    assert card and card["steps"][0]["arguments"]["note_id"] == target and lease != target


def test_a_rename_stops_before_a_second_request(client):
    _note(client, "# S\n\nx", tags=["gym"])
    found = _read("rename the tag gym to fitness and delete the boiler note")
    assert found["intent"] == "rename_tag" and found["new"] == "fitness"
    card, events = _card(client, "rename the tag gym to fitness and delete the boiler note")
    assert card["label"] == "Rename the tag “gym” to “fitness” on 1 note"
    assert "delete the boiler note" in _text(events), "the part left over is said, not dropped"


def test_a_name_holding_and_without_a_verb_is_kept_whole():
    assert _read("rename the tag R and D to research")["old"] == "R and D"
    assert _read("rename the tag gym to arts and crafts")["new"] == "arts and crafts"


def test_a_note_title_holding_to_is_found_by_the_longer_name(client):
    cook = _note(client, "# How to cook\n\nBoil water.")
    _note(client, "# How to park\n\nSlowly.")
    card, _ = _card(client, "rename the note how to cook to Recipes")
    assert card and card["steps"][0]["arguments"]["note_id"] == cook
    assert card["steps"][0]["arguments"]["content"].startswith("# Recipes")


def test_the_first_to_still_splits_when_the_old_name_is_the_short_one(client):
    atlas = _note(client, "# Atlas\n\nMaps.")
    card, _ = _card(client, "rename the note Atlas to Trip to Lisbon")
    assert card and card["steps"][0]["arguments"]["note_id"] == atlas
    assert card["steps"][0]["arguments"]["content"].startswith("# Trip to Lisbon")


@pytest.mark.parametrize("said", [
    "rename the tag “back to school” to school",
    "rename the tag \"back to school\" to school",
    "rename the tag back to school to school",
    "rename the tag back-to-school to “school”",
])
def test_a_tag_name_holding_to_is_renamed(client, said):
    _note(client, "# A\n\nx", tags=["back-to-school"])
    card, events = _card(client, said)
    assert card and card["steps"] == [{"name": "rename_tag", "arguments": {"old": "back-to-school", "new": "school"}}], _text(events)


def test_a_quoted_new_name_may_hold_to(client):
    _note(client, "# A\n\nx", tags=["school"])
    card, _ = _card(client, "rename the tag school to “back to school”")
    assert card and card["steps"][0]["arguments"]["new"] == "back to school"


@pytest.mark.parametrize("said", ["get back to John about the boiler note", "get back to me about the passport note", "recover from the flu note", "recover from the flu"])
def test_get_back_and_recover_need_the_bin_named(said):
    found = _read(said)
    assert found is None or found["intent"] != "restore", said


@pytest.mark.parametrize("said", ["recover the passport note from the bin", "get back the passport note from the trash", "restore the passport note"])
def test_get_back_and_recover_read_with_the_bin_named(said):
    found = _read(said)
    assert found and found["intent"] == "restore" and found["about"] == "passport", said


def test_restore_all_says_how_many_and_asks(client):
    for name in ("Passport", "Boiler"):
        client.delete("/entries/" + str(_note(client, "# " + name + "\n\nx")))
    card, events = _card(client, "restore all my notes from the bin")
    assert card is None and "2 notes in the bin" in _text(events) and "“restore the Boiler note”" in _text(events)


# --- 4, 6: restore never says what a sealed note holds, and brings back notes only ------------


def test_restore_treats_a_private_note_as_missing(client, session):
    secret = _note(client, "# Divorce lawyer\n\nsecret")
    client.delete(f"/entries/{secret}")
    _seal(session, secret)
    _, private = _card(client, "restore the divorce note")
    _, absent = _card(client, "restore the zebra note")
    assert "private" not in _text(private).lower()
    assert _text(private).replace("divorce", "X") == _text(absent).replace("zebra", "X")
    _, numbered = _card(client, f"restore note {secret}")
    assert "private" not in _text(numbered).lower() and "nothing in the bin" in _text(numbered)


def test_restore_offers_a_public_note_beside_a_private_one(client, session):
    public = _note(client, "# Passport\n\nRenew.")
    secret = _note(client, "# Passport secret\n\nx")
    client.delete(f"/entries/{public}")
    client.delete(f"/entries/{secret}")
    _seal(session, secret)
    card, _ = _card(client, "restore the passport note")
    assert card and card["steps"][0]["arguments"]["note_id"] == public


def test_restore_leaves_a_binned_board_to_the_bin_view(client, session):
    board = _note(client, "# Kitchen plan\n\nboard")
    session.get(Entry, board).is_board = True
    session.commit()
    client.delete(f"/entries/{board}")
    card, events = _card(client, "restore the kitchen plan from the bin")
    assert card is None and "nothing in the bin" in _text(events)
    done = _run(client, [{"name": "restore_note", "arguments": {"note_id": board}}])
    assert not done["ok"]
    session.expire_all()
    assert session.get(Entry, board).is_deleted


def test_restore_matches_whole_words(client):
    client.delete("/entries/" + str(_note(client, "# Cardiology appointment\n\nx")))
    card, events = _card(client, "restore the car note")
    assert card is None and "nothing in the bin" in _text(events)
    card, _ = _card(client, "restore the cardiology note")
    assert card
