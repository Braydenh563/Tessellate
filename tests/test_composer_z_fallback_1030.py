"""Composer audit 2026-10-30, class 6 (Z34 to Z36): a fallback says it is one,
a count is said once, and questions about the notebook's structure are
answered from the notebook."""

from __future__ import annotations

import pytest

from tests import _seed_1030 as seed_1030


@pytest.fixture
def ask(client, session, monkeypatch):
    seed_1030.seed(session)
    return seed_1030.asker(client, monkeypatch)


@pytest.mark.parametrize("question", ["who do I know", "where have I been", "what do you think I should do", "how much did I save"])
def test_z34_a_question_that_names_nothing_says_the_newest_notes_are_a_fallback(ask, question):
    said = ask(question)[0]
    assert said.startswith("I could not tell what that asks about, so here are your"), said
    assert "From yesterday: Coffee" not in said and "[From yesterday](#/notes/" in said, said


@pytest.mark.parametrize("question", ["what have I saved recently", "show my newest notes"])
def test_z34_a_recency_ask_is_not_called_a_guess(ask, question):
    assert "could not tell" not in ask(question)[0]


@pytest.mark.parametrize("question", ["find the note about chess", "search for oatmeal", "find the note about sailing"])
def test_z35_the_count_of_the_fallback_is_said_once(ask, question):
    said = ask(question)[0].split("\n")[0]
    assert said.startswith("Nothing matched") and "instead" not in said, said
    assert "first eight" not in ask(question)[0], said


@pytest.mark.parametrize("question", ["which notes have no title", "how many notes have no title"])
def test_z36_untitled_notes_are_counted(ask, question):
    said = ask(question)[0]
    assert "no title" in said and "I found no mention" not in said, said


@pytest.mark.parametrize("question", ["do I have duplicate notes", "are there duplicate notes"])
def test_z36_duplicates_are_answered_not_searched_for(ask, question):
    said = ask(question)[0]
    assert "same text" in said or "more than once" in said, said
    assert "no mention of" not in said, said


@pytest.mark.parametrize("question", ["untick bread", "please uncheck the milk", "can you untick the passport"])
def test_z37_an_untick_is_said_not_searched_for(ask, question):
    said = ask(question)[0]
    assert "cannot untick" in said and "mention" not in said, said


@pytest.mark.parametrize("text", ["mark the charger as packed", "mark the passport packed", "mark bread as bought"])
def test_z37_a_mark_as_done_reads_as_a_tick(text):
    from tessellate.ai import task_acts

    assert task_acts.read_complete(text)["intent"] == "complete"


@pytest.mark.parametrize("question", ["who is Anna", "what did I write about the wifi", "who is Tom"])
def test_z38_a_title_less_note_is_never_named_by_its_cut_first_words(ask, question):
    said = ask(question)[0]
    assert "…”" not in said.split("\n")[-1] and "…”" not in said, said


@pytest.mark.parametrize("said,plain", [
    ("The packing list is for the **Lisbon trip**", "The packing list is for the Lisbon trip"),
    ("Both are about [[Atlas]] and `beta`", "Both are about Atlas and beta"),
    ("See [the plan](#/notes/4) and #lisbon", "See the plan and lisbon"),
])
def test_z42_a_link_reason_reads_as_plain_text(said, plain):
    from tessellate.ai import links
    from tessellate.core.database import plain_reason

    assert plain_reason(said) == plain
    assert links._clean_reason(f"“{said}.”") == plain


def test_z41_the_word_that_introduces_the_subject_is_not_searched_for():
    from tessellate.search import query

    assert query.search_terms("what do I know about Lisbon") == ["know", "lisbon"]
    assert query.search_terms("tell me about the plan") == ["tell", "plan"]
    assert query.search_terms("about") == ["about"]


@pytest.mark.parametrize("question", ["what do I know about Lisbon", "what do I know about Sara"])
def test_z41_the_sources_hold_no_note_that_only_says_about(client, session, monkeypatch, question):
    seed_1030.seed(session)
    _text, events = seed_1030.asker(client, monkeypatch, chat=True)(question)
    meta = next(e for e in events if e.get("type") == "meta")
    shown = " ".join(str(r.get("content") or "") for r in meta.get("raw_results") or [])
    assert "Need to call the bank about the card" not in shown, shown[:300]


@pytest.mark.parametrize("question", ["notes from october", "show notes from October", "list my notes from august"])
def test_z28_notes_from_a_month_are_that_months_notes(ask, question):
    said = ask(question)[0]
    assert said.startswith("You wrote") and " from " in said.split("\n")[0], said
    assert "Open it from here" not in said and "notes about" not in said, said
