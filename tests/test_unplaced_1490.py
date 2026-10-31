"""A message the composer cannot place is never sent to the web (INBOX 1490).

The owner, 2026-10-31: "ur mum" and "japanese", with Web search on and no
model, answered "I tried to search the web, but the search service at
127.0.0.1 is not answering ... docker run ...". The web is searched only when
it was asked for or the message is a question about the world; anything else
with no note to answer it is asked about, with two chips. With a model on the
model still does its job (CHAT_PLAN decision 75).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import composer_unplaced
from tessellate.core import deps
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 10, 31, 15, 45)

#: Banter, slang, single words, names, emoji, fragments: nothing in them asks
#: for the web, and no note holds them.
UNPLACED = [
    "ur mum", "your mum", "ur mom lol", "ur mum is fat", "japanese", "french", "banana", "bruh moment", "no cap", "skibidi", "rizz", "slay",
    "fr fr", "bet", "that was funny", "you smell", "ur dumb", "shut up", "pog", "ok boomer", "yeet", "L + ratio", "sheesh", "mid", "cringe",
    "🔥", "😂😂", "👍", "???", "...", "ratio", "gg", "ez", "touch grass", "big mood", "same", "lmaooo", "xyz", "purple monkey dishwasher",
    "oi mate", "your face", "ligma", "sus", "vibes", "asdf", "qwerty", "hmmmmm yes",
    "cheese", "blue", "monday", "tomorrow", "he said she said", "ahh", "nah", "idk",
]
#: Said to the app: answered by the app's own readers, never the web.
TO_THE_APP = ["are you stupid", "do you like me", "what do you think", "do you dream", "are you ok with that"]
#: A question about the world, or the web asked for outright.
WORTHY = [
    "what is the capital of France", "what's the capital of france", "who won the 2022 world cup", "weather in Brisbane", "weather brisbane tomorrow",
    "how do I descale a kettle", "how to boil an egg", "where is Machu Picchu", "when did the Berlin wall fall", "why is the sky blue",
    "who is Taylor Swift", "what is photosynthesis", "population of Tokyo", "price of bitcoin", "bitcoin price today", "translate hello to french",
    "define serendipity", "explain quantum computing", "tell me about Mars", "search the web for japanese", "look it up online: ur mum", "google japanese",
    "search online for banana bread", "is it going to rain tomorrow", "how many people live in Japan", "capital of Peru", "news about the election",
    "what does ephemeral mean", "who invented the telephone", "how tall is mount everest", "convert 10 miles to km", "meaning of life",
]
#: Said about the person's own record: the notes first, never the web.
OWN = ["my notes on golf", "japanese note", "the note in japanese", "notes about banana", "my japanese notes", "show me my banana notes"]

_NOTES = (
    "# Golf practice\n\nHit a bucket of balls after work and fixed my grip.",
    "# Dentist\n\nCheck-up booked for the 21st.",
)


@pytest.fixture()
def notebook(session, monkeypatch):
    from tessellate.api import routes_chat
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text in _NOTES:
        manager.create_entry(session, text)
    session.commit()
    deps.get_config().set_preference("web_search_enabled", True)
    return session


@pytest.fixture()
def web(monkeypatch):
    """Every web search made (the service is down, as on the owner's machine)."""
    from tessellate.search import websearch

    seen: list[str] = []

    def search(q, *a, **k):  # noqa: ANN001, ANN002, ANN003
        seen.append(q)
        raise websearch.WebSearchError("Connection refused")

    monkeypatch.setattr(websearch, "search_web", search)
    return seen


def _asks(out: dict) -> list[str]:
    return [a for e in out.get("offer", []) if e["offer"].get("kind") == "ask" for a in e["offer"]["asks"]]


@pytest.mark.parametrize("said", UNPLACED + TO_THE_APP)
def test_banter_slang_and_single_words_are_unplaced(said):
    assert composer_unplaced.unplaced(said), said
    assert not composer_unplaced.worthy(said), said


@pytest.mark.parametrize("said", WORTHY)
def test_a_question_about_the_world_or_a_web_ask_is_worthy(said):
    assert composer_unplaced.worthy(said), said
    assert not composer_unplaced.unplaced(said), said


@pytest.mark.parametrize("said", OWN)
def test_a_message_naming_notes_is_never_unplaced(said):
    assert not composer_unplaced.unplaced(said), said


@pytest.mark.parametrize("tools", [False, True])
def test_an_unplaced_message_is_never_searched_on_the_web(client, notebook, web, tools):
    for said in UNPLACED:
        out = _ask(client, said, use_tools=tools)
        text = out["text"]
        assert "search service" not in text and "docker" not in text.lower() and "Settings" not in text, (said, text)
        assert not out.get("grounding") and "#/notes/" not in text, (said, text)
        assert "!" not in text and chr(0x2014) not in text and "the assistant" not in text.lower(), (said, text)
    for said in TO_THE_APP:
        assert "search service" not in _ask(client, said, use_tools=tools)["text"], said
    assert web == []


#: The ones no other reader owns: the question back, with both chips.
ASKED_BACK = ["ur mum", "your mum", "ur mom lol", "banana", "purple monkey dishwasher", "cheese", "blue", "touch grass", "xyz", "monday", "big mood"]


@pytest.mark.parametrize("tools", [False, True])
def test_the_ones_nothing_else_reads_ask_notes_or_web_with_both_as_chips(client, notebook, web, tools):
    for said in ASKED_BACK:
        out = _ask(client, said, use_tools=tools)
        asks = _asks(out)
        assert "?" in out["text"] and len(out["text"]) <= 120, (said, out["text"])
        assert len(asks) == 2 and asks[0].startswith("Search my notes for") and asks[1].startswith("Search the web for"), (said, asks)
    assert web == []


def test_with_web_off_the_second_chip_is_what_it_can_do(client, notebook, web):
    deps.get_config().set_preference("web_search_enabled", False)
    out = _ask(client, "ur mum", use_tools=True)
    assert _asks(out) == ["Search my notes for ur mum", "What can you do?"], out
    assert "web" not in out["text"].lower() or "notes on it" in out["text"], out["text"]
    assert web == []


@pytest.mark.parametrize("tools", [False, True])
def test_a_bare_word_the_notes_hold_is_answered_from_them(client, notebook, web, tools):
    for said in ("golf", "dentist", "Golf?", "golf practice"):
        out = _ask(client, said, use_tools=tools)
        assert "Golf practice" in out["text"] or "Dentist" in out["text"] or "bucket of balls" in out["text"] or "Check-up" in out["text"], (said, out["text"])
        assert "search service" not in out["text"], (said, out["text"])
    assert web == []


@pytest.mark.parametrize("tools", [False, True])
def test_a_question_about_the_world_still_goes_to_the_web(client, notebook, web, tools):
    said = ("what is the capital of France", "weather in Brisbane", "how do I descale a kettle", "search the web for japanese", "who won the 2022 world cup")
    for text in said:
        out = _ask(client, text, use_tools=tools)
        assert "docker" in out["text"].lower() if tools else "search service" not in out["text"], (text, out["text"])
    #: Only Agent mode runs the search (Chat without it says so).
    assert len(web) == (len(said) if tools else 0)


def test_the_chip_that_asks_for_the_web_searches_it(client, notebook, web):
    out = _ask(client, "Search the web for ur mum", use_tools=True)
    assert web and "ur mum" in web[0]
    assert "search service" in out["text"] or "web" in out["text"].lower()


def test_the_chip_that_asks_for_the_notes_is_a_notes_search_not_another_question(client, notebook, web):
    out = _ask(client, "Search my notes for ur mum", use_tools=True)
    assert "nothing" in out["text"].lower() or "no notes" in out["text"].lower() or "couldn't" in out["text"].lower(), out["text"]
    assert not out.get("offer") or "Search my notes for" not in str(out["offer"]), out
    assert web == []


def test_with_a_model_on_the_composer_does_not_override_it(ai_client, fake_ollama, session, monkeypatch):
    from tessellate.search import websearch

    seen: list[str] = []
    monkeypatch.setattr(websearch, "search_web", lambda q, *a, **k: seen.append(q) or [])
    deps.get_config().set_preference("web_search_enabled", True)
    out = _ask(ai_client, "ur mum", use_tools=False)
    assert "Not sure what you mean" not in out["text"] and "notes on it" not in out["text"], out["text"]
    assert seen == []
