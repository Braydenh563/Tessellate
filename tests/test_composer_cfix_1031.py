"""The composer audit of 2026-10-31 (docs/roadmap/agent-remaining/audit-1031-composer.md),
one class per test group, each over many phrasings. Notebook and fixed clock:
`tests/_seed_1031c.py` (Saturday 31 October 2026, 11:30)."""

from __future__ import annotations

import pytest

import tests._seed_1031c as seed_c


@pytest.fixture
def notebook(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.fixture
def big_notebook(client, session, monkeypatch):
    seed_c.seed(session, filler=150)
    return seed_c.asker(client, monkeypatch)


# C1. A note titled with the name is a member of "who is X", whatever its body says.

@pytest.mark.parametrize("question", [
    "who is Tom", "who's Tom", "tell me about Tom", "what do I know about Tom", "what have I written about Tom",
    "what do my notes say about Tom", "who is tom?", "WHO IS TOM",
])
def test_the_note_titled_with_the_name_is_said_for_a_who_ask(notebook, question):
    said, _ = notebook(question)
    assert "data team at Vireo" in said, said
    assert "three notes" in said, said


@pytest.mark.parametrize("question", ["where does Tom work", "what does Tom do", "what does Tom do for work", "where does Tom work again"])
def test_a_pronoun_line_in_the_note_titled_with_the_name_answers_a_slot(notebook, question):
    said, _ = notebook(question)
    assert "data team at Vireo" in said, said


# C2. A list item is not a newer value of a relation.

@pytest.mark.parametrize("question", [
    "who is Sara", "what have I written about Sara", "what is in the Sara note", "what does Sara want for her birthday",
    "what should I get Sara", "tell me about Sara", "when is Sara's birthday",
])
def test_a_gift_list_does_not_replace_the_sara_note(notebook, question):
    said, _ = notebook(question)
    assert "used to be" not in said and "my sister" not in said, said
    assert "an older note" not in said.lower() and "earlier, on" not in said.lower(), said


def test_a_real_replacement_is_still_reported_in_the_second_person():
    from tessellate.ai import supersede

    notes = [
        {"content": "Uni days this semester: Tuesday and Thursday", "created_at": "2026-02-20T10:00:00"},
        {"content": "Uni days this semester are Monday and Wednesday", "created_at": "2026-07-20T10:00:00"},
    ]
    kept, replaced = supersede.current("what are my uni days", notes)
    assert len(kept) == 1 and replaced
    first_person = [{"content": "My favourite colour is blue", "created_at": "2026-01-01"}, {"content": "My favourite colour is now green", "created_at": "2026-06-01"}]
    kept, replaced = supersede.current("what is my favourite colour", first_person)
    assert len(kept) == 1
    assert "your" not in supersede.older_line(replaced) or "my" not in supersede.older_line(replaced)


@pytest.mark.parametrize("old, new", [("Sara is my sister", "Sara: a jazz record"), ("Tom is my brother", "Tom: coffee beans"), ("Sara is my sister", "Sara is a runner")])
def test_a_relation_is_never_a_stale_value(old, new):
    from tessellate.ai import supersede

    notes = [{"content": old, "created_at": "2026-01-01"}, {"content": new, "created_at": "2026-06-01"}]
    kept, replaced = supersede.current("who is " + old.split()[0], notes)
    assert len(kept) == 2 and not replaced


# C3. A holiday or month word in a topic question is searched for, not read as a day of writing.

@pytest.mark.parametrize("question", [
    "what do I know about Christmas", "tell me about Christmas", "anything about Christmas", "what have I written about Christmas",
    "what do I know about christmas", "who is coming for Christmas", "who's coming for Christmas", "what do my notes say about Christmas",
])
def test_a_holiday_in_a_topic_question_finds_the_notes_that_hold_it(notebook, question):
    said, _ = notebook(question)
    assert "coming for Christmas" in said, said
    assert "Nothing went" not in said and "can't find" not in said and "couldn't find" not in said, said


@pytest.mark.parametrize("question", ["how much did I save in October", "how much have I saved in October", "how much did I save in October?"])
def test_a_verb_and_a_month_read_the_months_notes_that_hold_the_verb(big_notebook, question):
    said, _ = big_notebook(question)
    assert "$500" in said and "can't find" not in said, said


@pytest.mark.parametrize("phrase, said", [
    ("Christmas", "at Christmas"), ("christmas", "at Christmas"), ("Easter", "at Easter"), ("the weekend", "over the weekend"),
    ("in October", "in October"), ("last week", "last week"), ("20 October", "on 20 October"), ("Halloween", "on Halloween"),
])
def test_a_time_phrase_carries_its_preposition(phrase, said):
    from tessellate.ai import composer

    assert composer.window_said(phrase) == said


@pytest.mark.parametrize("question, kept", [
    ("what did I write in October", True), ("what did I write last week", True), ("what did I do at Christmas", True),
    ("what do I know about last week", True), ("what do I know about Christmas", False), ("who is coming for Christmas", False),
    ("what do I know about the weekend", False), ("what do I know about October", False),
])
def test_only_a_writing_question_keeps_the_window(question, kept):
    from datetime import date

    from tessellate.ai import composer

    assert bool(composer.plan(question, date(2026, 10, 31)).window) is kept


def test_the_search_does_not_read_a_topic_holiday_as_a_range():
    from datetime import date

    from tessellate.search import query

    for question in ("who is coming for Christmas", "what do I know about Christmas", "tell me about Easter"):
        understood = query.understand(question, date(2026, 10, 31))
        assert not understood.has_range and understood.subject, question
    assert query.understand("what did I do at Christmas", date(2026, 10, 31)).has_range


# C12. A follow-on keeps its subject: a pronoun, a person, a total, "the last one".

@pytest.mark.parametrize("question, previous, said", [
    ("how much does it cost", "tell me about the Lisbon trip", "how much does the Lisbon trip cost"),
    ("when is it", "tell me about the Lisbon trip", "when is the Lisbon trip"),
    ("what should I get her", "who is Sara", "what should I get Sara"),
    ("when is her birthday", "who is Sara", "when is Sara's birthday"),
    ("what else do I know about her", "who is Sara", "what else do I know about Sara"),
    ("where does she live", "who is Sara", "where does Sara live"),
    ("what does he do", "who is Tom", "what does Tom do"),
    ("how far in total", "what do I know about running", "how far in total for running?"),
    ("what's the total", "what do I know about running", "what's the total for running?"),
    ("when was the last one", "what do I know about running", "when was the last one for running?"),
])
def test_a_follow_on_names_what_it_leans_on(question, previous, said):
    from tessellate.ai import composer

    got = composer.follow_on(question, [{"question": previous, "answer": "x"}])
    assert got is not None and got.question == said, got


@pytest.mark.parametrize("question", [
    "how far did I run in total", "when was the last one with Tom", "what time", "what is the weather", "who is Sara",
])
def test_a_question_with_its_own_subject_stands_alone(question):
    from tessellate.ai import composer

    got = composer.follow_on(question, [{"question": "what do I know about running", "answer": "x"}])
    assert got is None or got.kind != "pronoun", got


# C9. A day a preposition of aim leads is where something is headed, not the day it happened.

@pytest.mark.parametrize("question", ["when did I call mum", "when did I last call mum", "when did I phone mum"])
def test_a_day_the_sentence_aims_at_is_not_the_day_of_the_event(notebook, question):
    said, _ = notebook(question)
    assert "26 October" in said and "2025" not in said and "25 December" not in said, said
    assert "coming for Christmas" in said, said
