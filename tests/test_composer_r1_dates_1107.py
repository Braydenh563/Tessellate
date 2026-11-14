"""Composer round 1, 2026-11-07, D9 and D8: a line that carries its own date is
never led by "Today,", and a quotation is copied as written. Driven through the
chat route with no model (fake transport); the clock is `_seed_1031c.NOW`."""

from __future__ import annotations

import pytest
from sqlalchemy import select

import tests._seed_1031c as seed_c
from tessellate.core.database import Entry
from tessellate.entry import manager


@pytest.fixture
def notebook(client, session, monkeypatch):
    def make(*contents):
        for content in contents:
            entry = manager.create_entry(session, content)
            entry.created_at = entry.updated_at = seed_c.NOW
        session.commit()
        return seed_c.asker(client, monkeypatch)

    return make


RUNNING = (
    "# Running log\n\nRan 6 km on 25 October. Ran 5 km on 17 October. Ran 8 km on 3 October. Knee felt fine.",
    "# Running shoes\n\nBrooks Ghost, size 9, about £120. I need new running shoes.",
    "Park run was good, felt strong running the last mile.",
)


@pytest.mark.parametrize("question", ["the latest on running"])
def test_d9_a_line_with_its_own_date_is_not_led_by_today(notebook, session, question):
    go = notebook(*RUNNING)
    #: "The latest on running" answers with the newest note (W7b B7); the notes are stamped one instant, so the other two
    #: are made a day older here, and this test stays about how its own-dated line is worded.
    from datetime import timedelta

    for entry in session.scalars(select(Entry).where(~Entry.content.like("# Running log%"))):
        entry.created_at = entry.updated_at = seed_c.NOW - timedelta(days=1)
    session.commit()
    said, _ = go(question)
    assert "ran 6 km" in said.lower(), said
    assert "Today, you ran" not in said and "today, you ran" not in said.lower(), said


# --- D8: a quotation is the note's bytes -----------------------------------------------------

import re  # noqa: E402


def _quoted(said):
    return re.findall(r"“([^”]*)”", said)


def test_d8_a_weekday_in_a_note_is_not_turned_into_today(notebook):
    go = notebook("# Weekend plans\n\nSaturday: farmers market at 10am. Sunday: call Mum and meet Sara for lunch at 1pm.")
    said, _ = go("when did I last write about Sara")
    assert "today: call Mum" not in said, said
    assert "Sunday: call Mum" in said, said


def test_d8_a_quotation_does_not_skip_a_sentence_inside_the_marks(notebook):
    note = "# Books\n\nCurrently reading Piranesi by Susanna Clarke. Next: The Dispossessed. Finished Dune in September."
    #: The second note is about books too ("Book club" is the noun); "book a table" is the verb and no longer counts (W7b B10).
    go = notebook(note, "# Book club\n\nBook club meets on the first Tuesday. Next book is The Remains of the Day.")
    said, _ = go("what do I know about books")
    for quoted in _quoted(said):
        if "Piranesi" in quoted and "Dune" in quoted:
            assert "The Dispossessed" in quoted or "…" in quoted or "..." in quoted, said




@pytest.mark.parametrize(("line", "dated"), [("Ran 6 km on 25 October", True), ("Ran on 25th october", True), ("Flights leave May 5", True),
                                              ("we may 5 of us go to the match", False), ("I may 3 times a week go running", False)])
def test_review7_only_a_real_date_in_a_line_is_its_own_date(line, dated):
    from tessellate.ai import composer_digest_lines

    assert bool(composer_digest_lines._OWN_DATE.search(line)) is dated  # noqa: SLF001
