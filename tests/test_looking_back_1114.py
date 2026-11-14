"""The reading tools behind the looking-back skills (L-chat-51 to 53): untouched notes, a month in
numbers, and one person's page. Clock: Tuesday 10 November 2026, 09:00."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import tools
from tessellate.core import config
from tessellate.core.database import Entity, EntityMention, EntryLink, Reminder
from tessellate.entry import manager

NOW = datetime(2026, 11, 10, 9, 0)


@pytest.fixture(autouse=True)
def _fixed_now(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)


def _note(session, content, when, **kw):
    entry = manager.create_entry(session, content, **kw)
    entry.created_at = when
    entry.edited_at = None
    session.commit()
    return entry


def test_stale_notes_lists_only_what_is_untouched_past_the_span(session):
    old = _note(session, "# Old plan\n\nx", datetime(2026, 6, 1, 9))
    _note(session, "# Fresh\n\ny", datetime(2026, 11, 5, 9))
    pinned = _note(session, "# Kept\n\nz", datetime(2026, 1, 1, 9))
    pinned.pinned = True
    opened = _note(session, "# Read lately\n\nw", datetime(2026, 1, 2, 9))
    opened.last_opened_at = datetime(2026, 11, 1, 9)
    session.commit()
    out = tools.execute_tool(session, "find_stale_notes", {"days": 90})
    assert [n["id"] for n in out["notes"]] == [old.id] and out["total_stale"] == 1
    assert "error" in tools.execute_tool(session, "find_stale_notes", {"days": "soon"})


def test_stale_notes_never_lists_private_or_archived_notes(session):
    secret = _note(session, "# Diary\n\nq", datetime(2026, 1, 1, 9))
    secret.is_private = True
    shelved = _note(session, "# Shelved\n\nq", datetime(2026, 1, 1, 9))
    manager.archive_entry(session, shelved)
    session.commit()
    assert tools.execute_tool(session, "find_stale_notes", {"days": 30})["notes"] == []


def test_month_figures_counts_what_was_written_and_finished(session):
    _note(session, "# Groceries\n\nSpent $45 on groceries.", datetime(2026, 10, 5, 9))
    _note(session, "# Fuel\n\nSpent $60 on fuel.", datetime(2026, 10, 9, 9))
    _note(session, "# November\n\nlater", datetime(2026, 11, 2, 9))
    session.add(Reminder(text="Send the form", due_at=datetime(2026, 10, 12, 9), done=True, done_at=datetime(2026, 10, 12, 10)))
    session.add(Reminder(text="Book the vet", due_at=datetime(2026, 10, 20, 9)))
    session.commit()
    out = tools.execute_tool(session, "count_month_figures", {"month": "October"})
    assert out["notes_written"] == 2 and out["reminders_finished"] == 1 and out["reminders_still_open_from_then"] == 1
    assert out["from"] == "2026-10-01" and out["to"] == "2026-10-31"
    assert out["spent"]["source_notes"], out["spent"]
    assert "error" in tools.execute_tool(session, "count_month_figures", {"month": "the zorgblat era"})


def test_month_figures_says_nothing_was_spent_when_nothing_is_recorded(session):
    _note(session, "# Walk\n\nA long walk.", datetime(2026, 10, 5, 9))
    assert tools.execute_tool(session, "count_month_figures", {})["spent"] == {"text": "", "source_notes": []}


def test_person_page_gathers_notes_links_and_open_reminders(session):
    a = _note(session, "# Call with Sam\n\nSam wants the report.", datetime(2026, 10, 5, 9))
    b = _note(session, "# Report\n\nDraft.", datetime(2026, 10, 6, 9))
    session.add(EntryLink(source_entry_id=a.id, target_entry_id=b.id))
    sam = Entity(name="Sam Lee", kind="person", aliases=["Sam"])
    session.add(sam)
    session.flush()
    session.add(EntityMention(entity_id=sam.id, entry_id=a.id))
    session.add(Reminder(text="Email Sam the report", due_at=datetime(2026, 11, 12, 9)))
    session.add(Reminder(text="Buy milk", due_at=datetime(2026, 11, 12, 9)))
    session.commit()
    out = tools.execute_tool(session, "get_person_page", {"name": "sam"})
    assert [n["id"] for n in out["linked_notes"]] == [b.id]
    assert out["name"] == "Sam Lee" and [n["id"] for n in out["mentioned_in"]] == [a.id]
    assert [r["text"] for r in out["open_reminders"]] == ["Email Sam the report"]
    assert "No one called" in tools.execute_tool(session, "get_person_page", {"name": "Zed"})["error"]


def test_the_four_looking_back_skills_are_built_in_and_each_writes_last():
    from tessellate.ai import skills

    wanted = {"Prepare for a meeting": "create_note", "Monthly look back": "create_note", "Archive stale notes": "archive_note", "Everything about a person": "create_note"}
    by_name = {s["name"]: s for s in skills.BUILTIN_SKILLS}
    for name, writer in wanted.items():
        steps = skills._step_specs(by_name[name], None, by_name[name]["tools"])
        assert writer in by_name[name]["tools"], name
        writes = [i for i, s in enumerate(steps) if writer in s["text"] and s["expects"] != "answer_only"]
        assert writes and all(not s.get("tool") or s["tool"] != writer for s in steps[: writes[0]]), name


def test_archive_stale_notes_only_archives_what_the_person_names():
    from tessellate.ai import skills

    skill = next(s for s in skills.BUILTIN_SKILLS if s["name"] == "Archive stale notes")
    archive = next(s for s in skills._step_specs(skill, None, skill["tools"]) if "archive_note" in s["text"])
    assert archive["expects"] == "tool_optional" and "named in my reply" in archive["text"]
