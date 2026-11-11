"""Review findings on INBOX 1749 (hub, 2026-11-11): a hello that leads a real
question was answered as a hello and never searched, keyword searches with a
weather or home word were read as small talk, "can you read pdfs" as Atlas's
tastes, and the pattern list backtracked on repeated "im ". Each phrase is a
turn that must reach the notes, or the act, it was asking for."""

from __future__ import annotations

import time

import pytest

import tests._seed_1031c as seed_c
from tessellate.ai import composer_remark, intent

#: A greeting in front of a real request: the request is the turn.
LED = [
    "hey, what did I write about pasta", "hi can you find my pasta note", "yo open my last note",
    "morning, show my reminders", "hey remind me to call mum at 5pm", "hello, what is on tomorrow", "hiya how many notes do I have",
]
#: A bare hello, with or without the "how are you" that follows it.
BARE = ["heyy", "yo", "hey how are you", "hi there", "morning", "hey atlas", "hi how are you doing today"]
#: Keyword searches that carry a weather, holiday or home word.
SEARCHES = ["rainy day ideas", "snow day plans", "heat pump", "heat map ideas", "hot sauce recipes today", "christmas gift ideas", "winter coat"]
#: Questions and requests put to Atlas that are not about its tastes.
ASKS = ["can you read pdfs", "could you read this aloud", "can you play music", "could you eat a pizza note"]
#: An order that contains a remark ("remember its so hot today").
ORDERS = ["remember its so hot today", "save that it is raining", "log that i had pizza for dinner", "put it in my notes that it was freezing"]


@pytest.mark.parametrize("message", LED)
def test_a_hello_in_front_of_a_request_is_not_a_bare_hello(message):
    assert not composer_remark.bare_hello(message), message


@pytest.mark.parametrize("message", BARE)
def test_a_bare_hello_stays_one(message):
    assert composer_remark.bare_hello(message), message


@pytest.mark.parametrize("message", SEARCHES)
def test_a_keyword_search_is_not_small_talk(message):
    assert composer_remark.reply(message) is None, message
    assert intent.classify(message) != intent.SMALLTALK, message


@pytest.mark.parametrize("message", ASKS)
def test_a_can_you_request_is_not_read_as_a_taste(message):
    assert composer_remark.reply(message) is None, message


@pytest.mark.parametrize("message", ORDERS)
def test_an_order_is_not_a_remark(message):
    assert composer_remark.reply(message) is None, message


@pytest.mark.parametrize("message", ["it's so hot today", "its been really hot today", "so cold outside", "it is raining again"])
def test_a_statement_of_weather_is_still_a_remark(message):
    assert composer_remark.reply(message) is not None, message


def test_a_remark_pattern_does_not_backtrack_on_repeats():
    for text in ("im " * 5000 + "x", "ive " * 5000 + "x", "i " * 5000 + "ate" + " the" * 2000, "ugh " * 5000, "so really " * 3000 + "hot"):
        started = time.perf_counter()
        composer_remark.reply(text)
        composer_remark.bare_hello(text)
        assert time.perf_counter() - started < 0.05, text[:12]


@pytest.fixture
def go(client, session, monkeypatch):
    seed_c.seed(session)
    return seed_c.asker(client, monkeypatch)


@pytest.mark.parametrize("message", ["hey, what did I write about pasta", "hi can you find my pasta note", "morning, show my reminders", "hey remind me to call mum at 5pm"])
def test_a_request_behind_a_hello_is_answered_not_greeted(go, message):
    said, events = go(message)
    assert said.strip() or events, message
    assert not said.strip().startswith(("Hey.", "Hi.", "Morning.", "Hello.")) or len(said) > 80, said
    assert said.strip() != composer_remark.casual_hello(message, "natural", [], "s").strip(), said
