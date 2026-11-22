"""The editing service, called directly (decision 55, L-world-class-632)."""

from __future__ import annotations

from tessellate.api.schemas import EntryUpdate
from tessellate.entry import editing, manager, manager_wiki


def _note(session, text: str):
    entry = manager.create_entry(session, text, category_name=manager.UNCATEGORISED)
    session.commit()
    return entry


def test_an_edit_writes_the_new_text_and_offers_no_rename_for_an_unlinked_note(session):
    entry = _note(session, "# Bread\nflour")
    rename = editing.update(session, entry, EntryUpdate(content="# Bread\nflour and water"))
    assert rename is None and entry.content == "# Bread\nflour and water"


def test_a_pin_and_a_draft_flag_are_saved_with_the_edit(session):
    entry = _note(session, "a thought")
    editing.update(session, entry, EntryUpdate(pinned=True, is_draft=True))
    assert entry.pinned is True and entry.is_draft is True


def test_renaming_the_opening_line_offers_the_rename_to_notes_that_link_it(session):
    target = _note(session, "# Old name\nbody")
    _note(session, "see [[Old name]] for more")
    manager_wiki.sync_wiki_links(session, target)
    rename = editing.update(session, target, EntryUpdate(content="# New name\nbody"))
    assert rename is not None and rename["new"] == "New name" and rename["notes"] == 1
