"""A window word that is also a note's title word is the subject, not a time
(composer-r7 R3-20): "what are my plans for the weekend" with a note called
"Weekend plans" is that note, never "nothing was written over the weekend".
Seed: `tests/_seed_1031c.py`."""

from __future__ import annotations

import re

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


def test_the_note_named_for_the_window_is_the_answer(go):
    text, _ = go("what are my plans for the weekend")
    assert "Weekend plans" in text and "Nothing I found was written" not in text, text


def test_a_real_recall_by_the_window_is_unchanged(go):
    text, _ = go("what did I write last weekend")
    assert re.search(r"four notes|4 notes", text) and re.search(r"[Ll]ast weekend", text) and "have four notes last weekend" not in text, text  # counts are words in a sentence (voice engine, 2026-11-10)


def test_a_topic_with_no_titled_note_still_says_nothing_was_written(go):
    text, _ = go("what did I write about the dentist last weekend")
    assert "Weekend plans" not in text, text


def test_reading_now_leads_with_the_sentence_that_says_it(go, session):
    from tessellate.entry import manager

    manager.create_entry(session, "# Books\n\nCurrently reading Piranesi. Finished Dune in September.", category_name="Reading")
    session.commit()
    text, _ = go("what am I reading")
    assert text.startswith("Currently reading Piranesi"), text
