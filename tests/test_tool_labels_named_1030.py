"""Audit 1029 C47: a tool's label and its confirm button name a note by its
title, never its id ("Done: added to Favourites: note #29")."""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import tools
from tessellate.entry import manager

SOURCE = Path(tools.__file__).read_text(encoding="utf-8")


def test_no_result_label_shows_a_note_id():
    labels = re.findall(r'"label"\]? ?=? ?f"ph:[^"\n]*"|"label": f"ph:[^"\n]*"', SOURCE)
    assert labels
    assert not [lab for lab in labels if "note #{" in lab], labels


def test_the_confirm_button_names_the_note(session):
    entry = manager.create_entry(session, "# Gym plan\n\nSquats on Monday.")
    session.commit()
    assert tools.confirm_label("delete_note", {"note_id": entry.id}, session) == "Move “Gym plan” to the recycle bin"
    assert tools.confirm_label("edit_note", {"note_id": entry.id}, session) == "Change “Gym plan”"


def test_a_private_or_missing_note_keeps_the_plain_label(session):
    secret = manager.create_entry(session, "# Diary\n\nPrivate words.")
    secret.is_private = True
    session.commit()
    assert "Diary" not in tools.confirm_label("delete_note", {"note_id": secret.id}, session)
    assert tools.confirm_label("delete_note", {"note_id": 99999}, session).startswith("Move note #99999")
