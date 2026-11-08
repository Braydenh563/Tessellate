"""Chat verbs that act on a kind of thing (CHAT_PLAN X5 and X8, acts-1108):
rename a tag, a category or a note by its kind word, restore a note from the
bin, delete always to the bin. Every write waits for Confirm and nothing is
written on read; a question or a sentence with a gap is never read as the act.
Every provider runs against a fake transport (CLAUDE.md section 4)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import commands

NOW = datetime(2026, 11, 8, 10, 0)


def _events(client, question, **body):
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True, **body}) as r:
        assert r.status_code == 200
        return [json.loads(line) for line in r.iter_lines() if line.strip()]


def _text(events) -> str:
    return " ".join(e.get("delta", "") for e in events if e.get("type") == "answer")


def _card(client, said):
    events = _events(client, said)
    return next((e for e in events if e.get("type") == "act"), None), events


def _confirm(client, card):
    return client.post("/chat/command/run", json={"steps": card["steps"], "skipped": card.get("skipped", [])}).json()


def _listed(client) -> list[int]:
    return [e["id"] for e in client.get("/entries", params={"limit": 50}).json()]


def _tagged(client, tag, n=2):
    return [client.post("/entries", json={"content": f"# Session {i}\n\nLegs and back.", "tags": [tag]}).json()["id"] for i in range(n)]


# --- X5: rename a tag, a category or a note by its kind word ------------------------------------------


@pytest.mark.parametrize("said, expect", [
    ("rename the tag gym to fitness", {"intent": "rename_tag", "old": "gym", "new": "fitness"}),
    ("rename tag #gym to #fitness", {"intent": "rename_tag", "old": "gym", "new": "fitness"}),
    ("Rename the label \"gym\" to \"fitness\"", {"intent": "rename_tag", "old": "gym", "new": "fitness"}),
    ("rename the category Work to Job", {"intent": "rename_category", "old": "Work", "new": "Job"}),
    ("rename my folder Work to Job", {"intent": "rename_category", "old": "Work", "new": "Job"}),
    ("rename the note passport to Travel ID", {"intent": "rename", "about": "passport", "title": "Travel ID"}),
    ("rename the note about the boiler to Heating", {"intent": "rename", "about": "boiler", "title": "Heating"}),
    ("can you rename the tag gym to fitness", {"intent": "rename_tag", "old": "gym", "new": "fitness"}),
])
def test_rename_is_read_by_its_kind_word(said, expect):
    got = commands.read_typed(said, NOW)
    assert got and {k: got[k] for k in expect} == expect


@pytest.mark.parametrize("said", [
    "how do I rename a tag", "how do I rename the tag gym to fitness", "rename a tag", "rename my tags", "rename the tag gym",
    "Rename the tag gym to fitness?", "what is a tag", "rename the category to Job", "rename the thing to the other thing",
])
def test_a_question_or_a_gap_is_not_a_rename(said):
    got = commands.read_typed(said, NOW)
    assert got is None or got["intent"] not in ("rename_tag", "rename_category")


def test_rename_a_tag_waits_for_confirm_then_renames_and_undoes(client):
    ids = _tagged(client, "gym")
    card, events = _card(client, "rename the tag gym to fitness")
    assert card and not card.get("done") and card["label"] == "Rename the tag “gym” to “fitness” on 2 notes"
    assert "Confirm" in _text(events)
    assert all(client.get(f"/entries/{i}").json()["tags"] == ["gym"] for i in ids), "nothing writes on read"
    done = _confirm(client, card)
    assert done["ok"] and all(client.get(f"/entries/{i}").json()["tags"] == ["fitness"] for i in ids)
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert all(client.get(f"/entries/{i}").json()["tags"] == ["gym"] for i in ids)


def test_an_unknown_tag_says_which_are_close(client):
    _tagged(client, "gym")
    _tagged(client, "gym-plan", 1)
    card, events = _card(client, "rename the tag gymm to fitness")
    assert card is None
    assert "I found no tag called “gymm”. Close: “gym”" in _text(events)


def test_a_rename_onto_a_tag_that_exists_is_left_to_the_tag_manager(client):
    _tagged(client, "gym")
    _tagged(client, "fitness", 1)
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "merge" in _text(events)


def test_rename_a_category_waits_for_confirm_then_renames_and_undoes(client):
    note = client.post("/entries", json={"content": "# Standup\n\nNotes.", "category": "Work"}).json()["id"]
    card, _ = _card(client, "rename the category Work to Job")
    assert card and card["steps"] == [{"name": "rename_category", "arguments": {"old": "Work", "new": "Job"}}]
    assert client.get(f"/entries/{note}").json()["category"] == "Work", "nothing writes on read"
    done = _confirm(client, card)
    assert done["ok"] and client.get(f"/entries/{note}").json()["category"] == "Job"
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert client.get(f"/entries/{note}").json()["category"] == "Work"


def test_an_unknown_category_says_which_are_close(client):
    client.post("/entries", json={"content": "# Standup\n\nNotes.", "category": "Work"})
    card, events = _card(client, "rename the category Wrk to Job")
    assert card is None and "I found no category called “Wrk”. Close: “Work”" in _text(events)


def test_rename_a_note_by_its_kind_word_is_a_confirm_card(client):
    note = client.post("/entries", json={"content": "# Passport\n\nRenew in May."}).json()["id"]
    card, _ = _card(client, "rename the note Passport to Travel ID")
    assert card and not card.get("done") and card["steps"][0]["name"] == "edit_note"
    assert client.get(f"/entries/{note}").json()["content"].startswith("# Passport")
    _confirm(client, card)
    assert client.get(f"/entries/{note}").json()["content"].startswith("# Travel ID")


# --- X8: restore from the bin, delete always to the bin -----------------------------------------------


@pytest.mark.parametrize("said, expect", [
    ("restore the passport note", {"intent": "restore", "about": "passport"}),
    ("restore my passport note from the bin", {"intent": "restore", "about": "passport"}),
    ("restore the Passport renewal from the bin", {"intent": "restore", "about": "Passport renewal"}),
    ("undelete the passport note", {"intent": "restore", "about": "passport"}),
    ("bring back the passport note", {"intent": "restore", "about": "passport"}),
    ("restore note 12", {"intent": "restore", "note_id": 12}),
])
def test_restore_is_read(said, expect):
    got = commands.read_typed(said, NOW)
    assert got and {k: got[k] for k in expect} == expect


@pytest.mark.parametrize("said", [
    "how do I restore a note", "restore the default settings", "restore the tag gym", "restore my passport", "what did I restore",
    "restore from backup",
])
def test_a_question_or_another_thing_is_not_a_restore(said):
    got = commands.read_typed(said, NOW)
    assert got is None or got["intent"] != "restore"


def test_restore_waits_for_confirm_and_undo_bins_it_again(client):
    note = client.post("/entries", json={"content": "# Passport\n\nRenew in May."}).json()["id"]
    client.delete(f"/entries/{note}")
    card, events = _card(client, "restore the passport note")
    assert card and not card.get("done") and card["label"] == "Restore the note “Passport” from the bin"
    assert "Confirm" in _text(events)
    assert note not in _listed(client), "nothing writes on read"
    done = _confirm(client, card)
    assert done["ok"] and note in _listed(client)
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert note not in _listed(client)


def test_restore_finds_nothing_or_asks_which(client):
    first = client.post("/entries", json={"content": "# Passport renewal\n\nMay."}).json()["id"]
    second = client.post("/entries", json={"content": "# Passport photos\n\nBooth."}).json()["id"]
    card, events = _card(client, "restore the passport note")
    assert card is None and "found nothing in the bin about “passport”" in _text(events)
    client.delete(f"/entries/{first}")
    client.delete(f"/entries/{second}")
    card, events = _card(client, "restore the passport note")
    assert card is None and "Which note in the bin about “passport”" in _text(events)


def test_delete_is_always_a_card_to_the_bin_and_undo_restores(client):
    note = client.post("/entries", json={"content": "# Passport\n\nRenew in May."}).json()["id"]
    card, _ = _card(client, "delete the passport note")
    assert card and not card.get("done") and card["steps"] == [{"name": "delete_note", "arguments": {"note_id": note}}]
    assert note in _listed(client)
    done = _confirm(client, card)
    assert [s["name"] for s in done["undo"]] == ["restore_note"]
    assert note not in _listed(client)
    client.post("/chat/command/run", json={"steps": done["undo"]})
    assert note in _listed(client)


def test_a_locked_vault_refuses_a_tag_a_private_note_holds(client, session):
    from tessellate.core.database import Entry

    _tagged(client, "gym", 1)
    secret = client.post("/entries", json={"content": "# Secret\n\nbody", "tags": ["gym"]}).json()["id"]
    session.get(Entry, secret).is_private = True
    session.commit()
    card, events = _card(client, "rename the tag gym to fitness")
    assert card is None and "also on private notes" in _text(events)
    assert "Unlock the vault" in _text(events)


def test_restore_never_brings_back_a_private_note(client, session):
    from tessellate.core.database import Entry

    note = client.post("/entries", json={"content": "# Passport\n\nRenew in May."}).json()["id"]
    client.delete(f"/entries/{note}")
    session.get(Entry, note).is_private = True
    session.commit()
    card, events = _card(client, "restore the passport note")
    assert card is None and "private" in _text(events)
