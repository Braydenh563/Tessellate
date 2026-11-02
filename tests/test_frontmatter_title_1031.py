"""Audit 1031 N12: a frontmatter `title:` is the note's title.

The reader that already knows where the block ends lifts the `title:` line
out of it at save and writes it as the note's heading; the other properties
stay as they were, and a note that names itself keeps its own heading.
"""

from __future__ import annotations

import pytest

from tessellate.entry import manager, properties


@pytest.mark.parametrize(
    "text, lifted",
    [
        (
            "---\ntitle: Front matter note\ntype: Book\n---\nSome body text.\n",
            "---\ntype: Book\n---\n# Front matter note\n\nSome body text.\n",
        ),
        ("---\ntitle: Only a title\n---\nBody.\n", "# Only a title\n\nBody.\n"),
        ("---\nTitle: \"Quoted: yes\"\n---\nBody.\n", "# Quoted: yes\n\nBody.\n"),
        # The note names itself: its heading wins, the property stays.
        ("---\ntitle: Other\n---\n# Mine\nBody.\n", "---\ntitle: Other\n---\n# Mine\nBody.\n"),
        # Already the first line: no second copy.
        ("---\ntitle: Same\n---\nSame\nmore\n", "---\ntitle: Same\n---\nSame\nmore\n"),
        # No block, no title, an empty title: nothing to lift.
        ("Plain note", "Plain note"),
        ("---\ntype: Book\n---\nBody", "---\ntype: Book\n---\nBody"),
        ("---\ntitle:\n---\nBody", "---\ntitle:\n---\nBody"),
    ],
)
def test_lift_title(text, lifted):
    assert properties.lift_title(text) == lifted


def test_a_saved_note_is_titled_by_its_frontmatter(session):
    entry = manager.create_entry(session, "---\ntitle: Front matter note\n---\nBody text.\n")
    assert manager.extract_title(entry.content) == "Front matter note"
    assert "title:" not in entry.content


def test_an_edit_lifts_it_too(session):
    entry = manager.create_entry(session, "First")
    manager.update_entry(session, entry, content="---\ntitle: Renamed\n---\nBody\n")
    session.refresh(entry)
    assert manager.extract_title(entry.content) == "Renamed"
