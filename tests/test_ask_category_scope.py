"""A question that names a category is answered from that category (found
driving a real model, 2026-10-05).

The app suggests "Summarise my notes in Health." itself (routes_chat.py's
suggested questions), and Ask answered it from whatever matched the words:
measured on the seeded notebook with Qwen2.5 1.5B, the summary of Health
cited "Notes as a map" (Ideas) and "A photo book of the trip" (Travel). The
same retrieval feeds the no-model answer, so it quoted the same strays. A
category the notebook has, named as where the notes are ("notes in Health",
"my Health notes"), now narrows the candidates to it.
"""

from __future__ import annotations

from tessellate.entry import manager
from tessellate.search import search_manager


def _note(session, content, category):
    return manager.create_entry(session, content, category_name=category)


def _seed(session):
    health = [
        _note(session, "Slept badly, back pain again, booked a physio appointment", "Health"),
        _note(session, "Half marathon plan: three runs a week, long run grows a kilometre", "Health"),
    ]
    _note(session, "Notes as a map: a summary of the trip in a photo book", "Ideas")
    _note(session, "Summarise the launch notes for the team in one page", "Work")
    return health


def test_summarise_my_notes_in_a_category_reads_that_category(session, fake_embeddings):
    health = _seed(session)
    found, _mode = search_manager.retrieve(session, "Summarise my notes in Health.", fake_embeddings)
    names = {manager.category_name_for(session, e) for e in found}
    assert names == {"Health"}, [(e.content[:30], manager.category_name_for(session, e)) for e in found]
    assert {e.id for e in found} == {e.id for e in health}


def test_my_category_notes_is_the_same_scope(session, fake_embeddings):
    _seed(session)
    found, _mode = search_manager.retrieve(session, "What do my Health notes say about sleep?", fake_embeddings)
    assert found and {manager.category_name_for(session, e) for e in found} == {"Health"}


def test_a_word_that_is_only_a_word_does_not_scope(session, fake_embeddings):
    """"work" in "how does the physio work" is a verb, not the Work category."""
    _seed(session)
    found, _mode = search_manager.retrieve(session, "how does the physio appointment work", fake_embeddings)
    assert any("physio" in e.content for e in found)


def test_widening_a_scoped_question_stays_in_the_category(session, fake_embeddings):
    """The route widens retrieval by keyword and by tag ("notes in Health" is
    read as the topic "notes in Health", which matched a note in Ideas that
    only says "notes"); a question scoped to a category keeps its answer there
    (tests-e2e/specs/ask-search.spec.js, Ask's own suggestion)."""
    from tessellate.api import chat_pool

    health = _seed(session)
    stray = _note(session, "Notes about notes: keep each note small", "Ideas")
    question = "Summarise my notes in Health."
    found = search_manager.retrieve_detailed(session, question, fake_embeddings, limit=5)
    assert found.category == "Health"
    widened = chat_pool._widened(session, question, found.entries, scope=found.category)
    assert stray.id not in {e.id for e in widened}
    assert {e.id for e in health} <= {e.id for e in widened}
    # No scope, no change: an unscoped topic still widens.
    assert stray.id in {e.id for e in chat_pool._widened(session, "notes about notes", [])}
