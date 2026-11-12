"""L-chat-29 (L223 remainder), both ways (decision 75): "similar to X", rename and move undone by a
sentence, "untag the note about boiler", "summarise note 12" carrying its note id. Clock: Thursday
12 November 2026, 10:00."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from tessellate.ai import commands
from tessellate.core.database import Entry
from tessellate.entry import manager
from tests.test_parity_acts_1110 import _fixed_now, card_of, confirm, stream, undo  # noqa: F401

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def notebook(session):
    manager.create_entry(session, "# Boiler service\n\nAnnual service is due in March.", category_name="Home", tags=["boiler", "home"])
    manager.create_entry(session, "# Heating notes\n\nRadiators need bleeding.", category_name="Home", tags=["home"])
    session.commit()
    return session


def _id(session, title: str) -> int:
    return next(e.id for e in session.scalars(select(Entry)) if (e.content or "").startswith(f"# {title}"))


def test_untag_the_note_about_boiler_asks_which_tag_and_never_reads_about_as_the_note():
    got = commands.read_typed("untag the note about boiler", NOW)
    assert got and got["intent"] == "untag" and got["about"] == "boiler" and got["tags"] == [], got


def test_untag_without_a_tag_asks_which(client, notebook):
    out = stream(client, "untag the note about boiler")
    assert "which tag" in out["text"].lower(), out["text"]
    assert not out.get("act"), "nothing to confirm until a tag is named"


def test_summarise_note_12_carries_its_note_id():
    got = commands.read_typed("summarise note 12", NOW)
    assert got["intent"] == "summarise" and got["note_id"] == 12, got


def test_summarise_a_numbered_note_reads_that_note_not_a_search_for_its_number(client, notebook):
    target = _id(notebook, "Boiler service")
    out = stream(client, f"summarise note {target}")
    assert "boiler service" in out["text"].lower(), out["text"]


def test_similar_to_is_a_read_act_with_the_note_named():
    for said in ("find notes similar to the boiler note", "similar to the boiler note", "show notes like the boiler note"):
        got = commands.read_typed(said, NOW)
        assert got and got["intent"] == "similar" and got["about"] == "boiler", (said, got)
    assert commands.read_typed("similar to note 12", NOW)["note_id"] == 12


def test_similar_to_answers_with_the_notes_the_tool_finds(client, notebook, monkeypatch):
    from tessellate.ai.tools import tool_read

    other = _id(notebook, "Heating notes")
    monkeypatch.setattr(tool_read, "_suggested_neighbours", lambda _s, _e, exclude: [{"id": other, "title": "Heating notes", "content": "# Heating notes\n\nRadiators."}])
    out = stream(client, "find notes similar to the boiler note")
    assert not out.get("act"), "a read waits for no Confirm"
    assert "heating notes" in out["text"].lower() and "boiler service" in out["text"].lower(), out["text"]
    assert any(e.get("name") == "find_similar_notes" for e in out.get("tool", [])), out.keys()


def test_similar_to_with_no_neighbour_says_so(client, notebook):
    out = stream(client, "find notes similar to the boiler note")
    assert "no note similar to" in out["text"].lower(), out["text"]


def test_similar_to_is_in_the_registry_as_a_read(client):
    from tessellate.ai import act_registry

    act = act_registry.ACTS["similar"]
    assert act.writes is False and act_registry.ACT_TOOLS["similar"] == "find_similar_notes"


@pytest.mark.parametrize(("ask", "check"), [("rename the boiler service note to Boiler", "title"), ("move the boiler service note to Garage", "category")])
def test_a_rename_or_move_is_taken_back_by_saying_undo(client, notebook, ask, check):
    """The old title or category is not in the sentence; the sentence that undoes it is made from what the run kept."""
    before = notebook.scalars(select(Entry).where(Entry.content.like("# Boiler service%"))).one()
    old_category = manager.category_name_for(notebook, before)
    first = stream(client, ask)  # nothing runs before Confirm: the card is pressed
    confirm(client, card_of(first))
    notebook.expire_all()
    out = stream(client, "undo that", history=[{"question": ask, "answer": "ok"}])
    assert out.get("act"), out["text"]
    confirm(client, card_of(out))
    notebook.expire_all()
    entry = notebook.get(Entry, before.id)
    assert (entry.content or "").startswith("# Boiler service") and manager.category_name_for(notebook, entry) == old_category


def test_undo_with_nothing_run_still_says_the_keys(client, notebook):
    out = stream(client, "undo that")
    assert not out.get("act")
