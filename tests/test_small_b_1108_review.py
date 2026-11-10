"""Review fixes for batch B of small-rows-1108 (privacy of the old pick, A22 choice, U17 narrowing, U16 commands)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete

from tessellate.ai import list_pool, resurface
from tessellate.core.database import NoteScore
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask


def _flagged(session):
    """One note fit to show and five that must never be: scored first, flagged after (scores lag up to a day)."""
    fine = manager.create_entry(session, "# Fine harbor\n\nThe harbor note anyone may see.")
    others = {
        name: manager.create_entry(session, f"# Hidden {name}\n\nA {name} sentence nobody should be shown.")
        for name in ("private", "binned", "board", "draft", "archived")
    }
    session.commit()
    resurface.compute_scores(session)
    others["private"].is_private = True
    others["binned"].is_deleted = True
    others["board"].is_board = True
    others["draft"].is_draft = True
    others["archived"].archived_at = datetime.now(timezone.utc)
    session.commit()
    return fine


def test_ranked_leaves_out_private_binned_board_draft_and_archived_notes(session):
    fine = _flagged(session)
    assert [e.id for e in resurface.ranked(session, limit=20)] == [fine.id]


def test_show_me_something_old_never_quotes_a_hidden_note(client, session):
    _flagged(session)
    text = _ask(client, "show me something old", notes_only=True, use_tools=False)["text"]
    assert "Fine harbor" in text and "Hidden" not in text


def test_the_fallback_pool_leaves_out_drafts_and_archived_notes(session):
    fine = _flagged(session)
    session.execute(delete(NoteScore))  # no scores kept: the fallback reads the live notes, oldest first
    session.commit()
    assert [e.id for e in list_pool._faded(session)] == [fine.id]


# --- A22: which note, and what it says -------------------------------------------------

NOTES = [
    {"id": 2, "content": "# Gym plan\n\nSquats on Monday and deadlifts on Friday.", "created_at": "2026-11-01", "category": "Fitness",
     "written": "Sunday 1 November 2026, 09:00"},
    {"id": 3, "content": "Squats shoes buy tomorrow", "created_at": "2026-10-01", "written": "Thursday 1 October 2026, 09:00"},
]


def test_where_prefers_the_titled_note_over_an_untitled_one_that_says_it_too():
    from datetime import date, datetime

    from tessellate.ai import composer

    out = composer.compose("where did I write about squats", NOTES, today=date(2026, 11, 8), now=datetime(2026, 11, 8, 12))
    assert out["text"].startswith("It is in **Gym plan**, in Fitness, written seven days ago. It is in one other note too. It reads: Squats on Monday")


def test_where_names_an_untitled_note_by_its_day_once():
    from datetime import date

    from tessellate.ai import composer_small

    out = composer_small.where_written("where did I write about shoes", NOTES, today=date(2026, 11, 8))
    assert out["text"] == "It is in your note from 1 October. It reads: Squats shoes buy tomorrow"


def test_where_did_i_write_down_the_habits_over_the_route(client, session):
    manager.create_entry(session, "# Seven habits\n\nBe proactive. Begin with the end in mind.")
    session.commit()
    text = _ask(client, "where did I write down the habits", notes_only=True, use_tools=False)["text"]
    assert text.startswith("It is in **Seven habits**") and "down" not in text


# --- U16: a command is not a what-if ---------------------------------------------------

def test_a_what_if_that_is_a_command_or_a_plan_is_left_to_the_ordinary_answer():
    from tessellate.ai import composer_small

    for ask in ("what if I translate hello", "imagine that I buy a car", "what if I write a poem"):
        assert composer_small.what_if(ask, NOTES) is None


def test_a_what_if_with_a_quoted_note_is_kept_even_for_a_plan():
    from tessellate.ai import composer_small

    notes = [{"id": 9, "content": "# Car\n\nI want to buy a car in spring.", "created_at": "2026-10-01"}]
    assert composer_small.what_if("what if I buy a car", notes)["text"].endswith("Your notes do not say what would happen.")
