"""Three review findings on composer code (composer4-1031).

1. `is_only_claim` matches only the closings the composer says, not any line
   with "only" in it (it swapped or dropped real lines).
2. The composer's own pool for a ranking, an order or a counted request is
   read only on the composer's path (CHAT_PLAN decision 75): a model reads
   the search's notes as before.
3. A run of blanks is squeezed out of the copy the readers scan, never out of
   the question the model and the saved turn read.
"""

from __future__ import annotations

import pytest

import tests._seed_1030 as seed_1030
from tessellate.ai import composer_digest, intent
from tessellate.api import bounds, routes_chat


@pytest.mark.parametrize("line", [
    "Only one reminder is due on Friday.",
    "This is the only time you ran 10k.",
    "It's the only week you've written down.",
    "This is the only week recorded.",
    "That's the only week you've jotted down so far.",
    "Only one week is written down.",
    "Only one thing is left on the list.",
    "It's your only plan so far.",
    "This is the only lecture.",
])
def test_a_line_with_only_in_it_is_not_the_closing_claim(line):
    assert not composer_digest.is_only_claim(line), line


@pytest.mark.parametrize("line", [
    "It's your only note on that so far.",
    "It's your only film review so far.",
    "It's your only book review so far.",
    "This is the only album review.",
    "Only one game review.",
    "This is the only note on that.",
    "Only one note on that.",
    "It's your only note on Lisbon so far.",
])
def test_the_closings_the_composer_says_are_claims(line):
    assert composer_digest.is_only_claim(line), line


def test_the_words_only_swap_keeps_a_real_line():
    text = "You ran 10k twice.\n\nThis is the only time you ran 10k.\n\nIt's your only note on that so far."
    said = routes_chat._with_words_only(text, {"search_mode": "keyword"}, {"grounding": True})
    assert "This is the only time you ran 10k." in said and "It's your only note on that so far." not in said, said


@pytest.fixture
def notes(session):
    seed_1030.seed(session)
    return session


@pytest.mark.parametrize("question", ["what is my latest note about baking", "which is the newest baking note", "which is the oldest baking note"])
def test_a_model_reads_the_searchs_notes_for_a_ranking(notes, question):
    on_model = routes_chat._Found(detected=intent.NOTES, stats=None)
    routes_chat._search_notes(notes, question, on_model, [], None, None, composed=False)
    on_composer = routes_chat._Found(detected=intent.NOTES, stats=None)
    routes_chat._search_notes(notes, question, on_composer, [], None, None, composed=True)
    assert len(on_model.entries) <= 1 or "oldest" in question, [e.id for e in on_model.entries]
    assert len(on_composer.entries) >= 3, [e.id for e in on_composer.entries]


@pytest.mark.parametrize("pasted", ["def f():\n" + " " * 40 + "return 1", "\n" + " " * 60 + "print(x)", "a" + " " * 100 + "b"])
def test_the_model_and_the_saved_turn_keep_their_blanks(notes, pasted):
    body = routes_chat.ChatRequest(question=pasted)
    assert body.question == bounds.squeeze_blanks(pasted) and len(body.question) < len(pasted)
    question, _, whole = routes_chat._asked(body, notes, None)
    assert whole == pasted and len(question) < len(pasted)


def test_an_ordinary_question_has_no_raw_copy(notes):
    body = routes_chat.ChatRequest(question="what is my newest note")
    assert body.raw_question is None
    assert routes_chat._asked(body, notes, None)[2] is None


def test_a_client_cannot_send_a_raw_copy(notes):
    body = routes_chat.ChatRequest(question="hello", raw_question="something else")
    assert body.raw_question is None
