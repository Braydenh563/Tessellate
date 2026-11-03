"""INBOX 1590: "recent notes I've made" answered "You have two notes about ve"
and offered "When did I write about ve?". The class: a contraction is never a
subject (its halves "ve", "re", "ll" included), no follow-on chip is built from
a stop word, a pronoun or a fragment under three letters, and the recent-notes
phrasings are one listing (newest first, dated, linked), model up or down."""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from tessellate.ai import composer, composer_dialogue, note_recency
from tessellate.ai.composer_ask import subject_terms
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tessellate.search import query as query_understanding
from tessellate.search.search_manager import is_recency_ask

NOW = datetime(2026, 11, 3, 12, 0)

#: Every contraction, straight and curly, and the halves the apostrophe leaves.
CONTRACTIONS = [
    "I've", "I’ve", "you're", "you’re", "don't", "don’t", "it's", "it’s", "we'll", "we’ll", "they've", "she's", "he'd",
    "I'm", "I’m", "isn't", "won't", "can't", "couldn't", "that's", "what's", "who's", "there's", "let's", "I'd", "you'll",
]
FRAGMENTS = ["ve", "re", "ll", "s", "t", "d", "m"]


@pytest.mark.parametrize("word", CONTRACTIONS)
def test_a_contraction_alone_names_no_subject(word):
    assert subject_terms(word) == [], word
    assert query_understanding.search_terms(word) == [], word


@pytest.mark.parametrize("word", CONTRACTIONS)
def test_a_contraction_beside_a_subject_leaves_the_subject(word):
    for ask in (f"notes {word} made about the dentist", f"{word} written about the dentist"):
        terms = subject_terms(ask)
        assert "dentist" in terms, (ask, terms)
        assert not set(terms) & set(FRAGMENTS), (ask, terms)
        assert not any("'" in t or "’" in t for t in terms), (ask, terms)


@pytest.mark.parametrize("fragment", FRAGMENTS)
def test_a_split_half_is_not_a_subject(fragment):
    assert query_understanding.search_terms(fragment) == []
    assert not query_understanding.is_chip_subject(fragment)


@pytest.mark.parametrize("subject", ["ve", "I've", "i", "you", "it", "the", "they", "she", "re", "ai", "uk", "", "  ", "ive", "dont", "my", "this", "IT", "IS", "RE", "VE"])
def test_no_chip_subject_from_a_stop_word_pronoun_or_fragment(subject):
    assert not query_understanding.is_chip_subject(subject), subject


@pytest.mark.parametrize("subject", ["dentist", "uni", "Ice Breakers", "my uni friend", "boiler repair", "AI", "the UK trip", "UK"])
def test_a_real_subject_is_a_chip_subject(subject):
    assert query_understanding.is_chip_subject(subject), subject


def test_the_subject_chip_is_not_built_from_a_fragment():
    assert composer_dialogue._subject_pick("I've", "overview", ["ve"]) is None  # noqa: SLF001
    assert composer_dialogue._subject_pick("the dentist", "overview", ["dentist"]) is not None  # noqa: SLF001


# --- the recent-notes phrasings ---------------------------------------------------------

RECENT = [
    "recent notes",
    "recent notes I've made",
    "recent notes I’ve made",
    "recent notes I made",
    "notes I've made",
    "notes I’ve made",
    "the notes I've made",
    "my latest notes",
    "my newest notes",
    "newest notes I've written",
    "what have I written lately",
    "what have I written recently",
    "what did I write lately",
    "show my newest notes",
    "show me my newest notes",
    "show my recent notes",
    "list my latest notes",
]


@pytest.mark.parametrize("ask", RECENT)
def test_every_recent_notes_phrasing_is_a_recency_ask(ask):
    assert is_recency_ask(ask), ask
    assert note_recency.recency(ask) is None or not note_recency.recency(ask).subject, ask


@pytest.mark.parametrize("ask", ["notes I've made about golf", "what have I written about golf lately", "the notes I've made on the boiler"])
def test_a_topic_in_the_ask_is_still_a_search(ask):
    assert not is_recency_ask(ask), ask


@pytest.fixture
def notes(session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for title, day in (("Ice Breakers", "2026-08-03"), ("Dentist", "2026-10-01"), ("Boiler", "2026-11-03")):
        entry = manager.create_entry(session, f"# {title}\n\nA line about {title.lower()}.")
        entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
    session.commit()


def _ask(client, question: str) -> tuple[str, list[str]]:
    text, chips = "", []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": False}) as response:
        for line in response.iter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event["type"] == "answer":
                text += event["delta"]
            elif event["type"] == "grounding":
                chips = list(event.get("next") or chips)
    return text, chips


@pytest.mark.parametrize("ask", RECENT)
def test_model_off_lists_the_newest_notes_newest_first_with_dates_and_links(client, notes, ask):
    text, chips = _ask(client, ask)
    assert re.search(r"\(#/notes/\d+\)", text), text
    assert text.index("Boiler") < text.index("Dentist") < text.index("Ice Breakers"), text
    assert "(today)" in text or "November" in text, text
    assert not re.search(r"\b(?:ve|about i've|about ve)\b", text, re.I), text
    for chip in chips:
        assert not re.search(r"\b(?:ve|i've|re|ll)\b[?]?$", chip, re.I), chip


@pytest.mark.parametrize("ask", RECENT)
def test_model_on_is_handed_the_same_newest_notes(ai_client, fake_ollama, session, monkeypatch, ask):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for title, day in (("Ice Breakers", "2026-08-03"), ("Dentist", "2026-10-01"), ("Boiler", "2026-11-03")):
        entry = manager.create_entry(session, f"# {title}\n\nA line about {title.lower()}.")
        entry.created_at = entry.updated_at = datetime.fromisoformat(day + "T09:00:00")
    session.commit()
    fake_ollama.librarian_reply = "Your newest note is Boiler."
    with ai_client.stream("POST", "/chat/stream", json={"question": ask, "use_tools": False}) as response:
        for _ in response.iter_lines():
            pass
    prompt = "\n".join(str(m.get("content") or "") for m in fake_ollama.chat_calls[-1])
    assert "Boiler" in prompt and "Dentist" in prompt and "Ice Breakers" in prompt, prompt
    assert prompt.index("Boiler") < prompt.index("Dentist"), prompt


def test_an_answer_that_names_a_contraction_builds_no_chip_from_it(client, notes):
    _text, chips = _ask(client, "what about I've")
    assert not any(re.search(r"\b(?:ve|i've)\b", c, re.I) for c in chips), chips
    assert composer.compose("what about I've", [], today=NOW.date())["next"] == []


@pytest.mark.parametrize("ask", ["notes I've made lately", "notes I made recently", "notes I’ve made recently"])
def test_with_a_window_word_the_window_answers_dated_and_linked_and_never_about_ve(client, notes, ask):
    text, chips = _ask(client, ask)
    assert re.search(r"\(#/notes/\d+\)", text) and "Boiler" in text, text
    assert not re.search(r"\b(?:ve|about i've)\b", text, re.I), text
    assert not any(re.search(r"\b(?:ve|i've)\b", c, re.I) for c in chips), chips

