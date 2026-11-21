"""A "notes mentioning X" ask answers from every note the notes search finds
(INBOX 1487, the owner, 2026-10-31).

"what do My notes mentioning test saY??" was answered from one note, with
Sources: 1 note, while the Notes search listed three and the greeting had said
"four notes mention test". Any ask for the notes that mention, contain or hold
a word is the listing of every note found for it, one line each with its link,
said with the count the greeting offers: the count, the list and the answer
agree.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import commands
from tessellate.core import deps
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = datetime(2026, 10, 31, 15, 45)
TITLES = ("Party Thoughts", "Test Document", "Test-driven development", "Leafeon Pokemon image test")
NOTES = (
    "# Party Thoughts\n\nA test of the party games before Saturday.",
    "# Test Document\n\nThis is a test of the quiet garden plan.",
    "# Test-driven development\n\nWrite the test first, then the code.",
    "# Leafeon Pokemon image test\n\nPicture caption: a leafeon in the grass.",
    "# Dentist\n\nCheck-up booked for the 21st.",
)

#: Every way of asking for the notes that hold a word, with and without the
#: question around it, a head ("show me"), a plural or the words "the word".
MENTIONING = [
    "what do my notes mentioning test say", "what do My notes mentioning test saY??", "My notes mentioning test", "notes mentioning test",
    "notes containing test", "notes with test in them", "notes that mention test", "which notes mention test", "what notes contain test",
    "show me notes mentioning test", "list notes containing test", "what do the notes containing test say",
    "what do my notes that mention test say", "all my notes with test in them", "any notes with the word test", "notes with the word test in them",
    "notes that have test in them", "what do my notes with test in them say", "notes where I mention test", "notes that say test",
    "tell me what my notes mentioning test say", "what's in my notes mentioning test", "find notes mentioning test",
    "my notes containing the word test", "what do my notes containing test have in them", "show all my notes that mention test",
    "Which of my notes mention test?", "what do my notes including test say", "give me the notes containing test",
]


@pytest.fixture()
def notebook(session, monkeypatch):
    from tessellate.api import routes_chat
    from tessellate.core import config

    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text in NOTES:
        manager.create_entry(session, text)
    session.commit()
    deps.get_config().set_preference("web_search_enabled", False)
    return session


@pytest.mark.parametrize("said", MENTIONING)
def test_every_phrasing_reads_as_a_find_for_the_word(said):
    found = commands.read(said, NOW)
    assert found and found["intent"] == "find" and found["about"].lower() == "test", (said, found)


@pytest.mark.parametrize("said", ["what do my notes say about test", "notes about test", "what notes are there with a checklist", "notes with a checklist in them",
                                  "notes with images", "what do my notes say about the word test"])
def test_other_asks_are_not_read_as_a_word_find(said):
    found = commands.read(said, NOW)
    assert not (found and found.get("about", "").lower() in ("test", "the word test", "images")), (said, found)


@pytest.mark.parametrize("tools", [False, True])
def test_the_answer_lists_every_note_found_with_its_link_and_says_the_count(client, notebook, tools):
    for said in MENTIONING:
        text = _ask(client, said, use_tools=tools)["text"]
        assert "four notes" in text.lower(), (said, text)
        for title in TITLES:
            assert title in text, (said, title, text)
        assert text.count("](#/notes/") == 4 and "Dentist" not in text, (said, text)


def test_the_count_the_ping_offers_is_the_count_the_list_gives(client, notebook):
    greeting = _ask(client, "testing", use_tools=False)["text"]
    listed = _ask(client, "what do my notes mentioning test say", use_tools=False)["text"]
    assert "Four notes mention" in greeting and "four notes" in listed.lower()
    assert listed.count("](#/notes/") == 4


def test_a_word_no_note_holds_says_so_and_lists_nothing(client, notebook):
    text = _ask(client, "what do my notes mentioning banana say", use_tools=False)["text"]
    assert "banana" in text and "](#/notes/" not in text and "I found no notes" in text or "nothing" in text.lower(), text
