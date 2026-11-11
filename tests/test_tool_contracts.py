"""Per-tool pre and post conditions, checked in Python (WORLD_CLASS_PLAN B5,
row 19). `ai/tools/contracts.py` says why each exists."""

from __future__ import annotations

import dataclasses

from tessellate.ai import tools
from tessellate.entry import manager_categories
from tessellate.ai.tools import contracts


def _note(session, content, **extra):
    return tools.execute_tool(session, "create_note", {"content": content, "category": extra.pop("category", "Inbox"), **extra})


def test_link_to_a_missing_note_is_refused_before_anything_links(ai_client, session):
    a = _note(session, "dentist on friday")
    b = _note(session, "insurance card")
    out = tools.execute_tool(session, "link_notes", {"note_id": a["id"], "other_note_ids": [b["id"], 9999]})
    assert "error" in out and "#9999" in out["error"]
    # Nothing half-done: the live target was not linked either.
    assert not contracts._linked(session, a["id"], b["id"])


def test_link_to_itself_is_refused(ai_client, session):
    a = _note(session, "dentist on friday")
    out = tools.execute_tool(session, "link_notes", {"note_id": a["id"], "other_note_id": a["id"]})
    assert "itself" in out["error"]


def test_tag_note_with_nothing_to_change_is_refused(ai_client, session):
    a = _note(session, "dentist on friday")
    out = tools.execute_tool(session, "tag_note", {"note_id": a["id"]})
    assert "error" in out and '"add"' in out["error"]


def test_a_misspelt_category_is_refused_naming_the_real_one(ai_client, session):
    a = _note(session, "dentist on friday", category="Health")
    out = tools.execute_tool(session, "edit_note", {"note_id": a["id"], "category": "Heath"})
    assert "error" in out and "“Health”" in out["error"]
    names = [c["name"] for c in manager_categories.all_categories(session)]
    assert "Heath" not in names


def test_a_category_in_another_case_files_under_the_existing_one(ai_client, session):
    a = _note(session, "dentist on friday", category="Health")
    b = _note(session, "physio tuesday", category="Inbox")
    out = tools.execute_tool(session, "edit_note", {"note_id": b["id"], "category": "health"})
    assert out["category"] == "Health"
    names = [c["name"] for c in manager_categories.all_categories(session)]
    assert names.count("Health") == 1 and "health" not in names
    assert a["category"] == "Health"


def test_a_genuinely_new_category_is_still_allowed(ai_client, session):
    out = _note(session, "flights to Lisbon", category="Travel")
    assert out["category"] == "Travel"


def test_restore_of_a_live_note_is_refused(ai_client, session):
    a = _note(session, "dentist on friday")
    out = tools.execute_tool(session, "restore_note", {"note_id": a["id"]})
    assert "not in the recycle bin" in out["error"]


def test_rename_tag_needs_a_tag_that_exists_and_allows_a_case_rename(ai_client, session):
    a = _note(session, "dentist on friday", tags=["health"])
    missing = tools.execute_tool(session, "rename_tag", {"old": "nope", "new": "x"})
    assert "No note has the tag" in missing["error"] and "health" in missing["error"]
    same = tools.execute_tool(session, "rename_tag", {"old": "health", "new": "health"})
    assert "same" in same["error"]
    ok = tools.execute_tool(session, "rename_tag", {"old": "health", "new": "medical"})
    assert "error" not in ok, ok
    assert a["id"]


def test_a_write_that_did_not_hold_is_reported_as_an_error(ai_client, session, monkeypatch):
    """The postcondition: a handler that returns its label without the change
    reaching the row is caught by re-reading the row."""
    a = _note(session, "dentist on friday")

    def lying_pin(sess, args):
        return {"id": a["id"], "pinned": True, "label": "ph:star Added to Favourites"}

    monkeypatch.setitem(tools.TOOLS, "pin_note", dataclasses.replace(tools.TOOLS["pin_note"], handler=lying_pin))
    out = tools.execute_tool(session, "pin_note", {"note_id": a["id"]})
    assert "did not take effect" in out["error"] and "Favourites" in out["error"]


def test_every_postcondition_passes_on_the_real_handlers(ai_client, session):
    a = _note(session, "dentist on friday", category="Health")
    b = _note(session, "insurance card", category="Health")
    calls = [
        ("tag_note", {"note_id": a["id"], "add": ["Urgent"]}),
        ("tag_note", {"note_id": a["id"], "remove": ["urgent"]}),
        ("pin_note", {"note_id": a["id"]}),
        ("pin_note", {"note_id": a["id"], "pinned": False}),
        ("link_notes", {"note_id": a["id"], "other_note_id": b["id"]}),
        ("unlink_notes", {"note_id": a["id"], "other_note_id": b["id"]}),
        ("edit_note", {"note_id": a["id"], "content": "dentist moved to monday"}),
        ("set_reminder", {"text": "call the dentist", "when": "tomorrow at 9am"}),
        ("create_category", {"name": "Admin"}),
        ("rename_category", {"old": "Admin", "new": "Paperwork"}),
        ("merge_categories", {"from": "Paperwork", "into": "Health"}),
        ("delete_note", {"note_id": b["id"]}),
        ("restore_note", {"note_id": b["id"]}),
    ]
    for name, args in calls:
        out = tools.execute_tool(session, name, args)
        assert "error" not in out, (name, out)
    reminder = tools.execute_tool(session, "list_reminders", {})["reminders"][0]
    done = tools.execute_tool(session, "complete_reminder", {"reminder_id": reminder["id"]})
    assert done["done"] is True


def test_an_edit_says_what_changed_and_what_did_not(ai_client, session):
    """Qwen2.5-3B, 2026-10-05 (`harness_probe.py`): "Move the plumber note to
    Home" called `edit_note {"tags": ["Home"]}` and answered "moved from Work
    to Home". The result said only "Updated note #1"; it now names what
    changed and the category it is still in, so the truth is in front of the
    model when it writes the answer."""
    a = _note(session, "chase up the plumber's invoice", category="Work")
    out = tools.execute_tool(session, "edit_note", {"note_id": a["id"], "tags": ["Home"]})
    assert out["changed"] == ["tags"]
    assert "still in Work" in out["label"] and "tags" in out["label"]
    moved = tools.execute_tool(session, "edit_note", {"note_id": a["id"], "category": "Home"})
    assert moved["changed"] == ["category"] and "Work to Home" in moved["label"]


def test_a_tag_the_store_normalises_is_not_read_as_missing(ai_client, session):
    """An 80-character tag is cut to the store's cap; read raw, the
    postcondition called a real save failed, which invites the duplicate."""
    long_tag = "x" * 80
    out = _note(session, "tag shapes", tags=[long_tag, "  spaced  "])
    assert "error" not in out, out
    again = tools.execute_tool(session, "tag_note", {"note_id": out["id"], "add": [long_tag]})
    assert "error" not in again, again


def test_the_contract_table_names_only_real_tools():
    assert set(contracts.CONTRACTS) <= set(tools.TOOLS)
    assert set(contracts.CONTRACTS) <= tools.WRITE_TOOLS


def test_a_checker_fault_never_costs_the_write(ai_client, session, monkeypatch):
    def broken(sess, args):
        raise RuntimeError("checker bug")

    monkeypatch.setitem(contracts.CONTRACTS, "pin_note", ((broken,), (lambda s, a, r: 1 / 0,)))
    a = _note(session, "dentist on friday")
    out = tools.execute_tool(session, "pin_note", {"note_id": a["id"]})
    assert out.get("pinned") is True
