"""composer4: "turn it on" offers, follow-ups, the date-event cache and the
new study abilities, all with no model. Same fixed clock and notes as
test_composer_study_1025."""

from __future__ import annotations

import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask
from tests.test_composer_study_1025 import NOTES, NOW


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when in NOTES:
        manager.create_entry(session, text, "Uni").created_at = when
    for text, due in (("Hand in the essay", (23, 17)), ("Gym session", (20, 7)), ("Submit essay", (None, 0)), ("Call the landlord", (28, 12))):
        if due[0]:
            session.add(Reminder(text=text, due_at=NOW.replace(day=due[0], hour=due[1], minute=0)))
    session.commit()

    def go(question: str, history: list | None = None, **body) -> str:
        return _ask(client, question, notes_only=True, answer_from="notes", history=history or [], **body)["text"]

    return go


OFF_AGENT = "Agent mode is off, so I can only read your notes. Turn it on beside the chat box."
OFF_DICT = "Dictation is not set up yet: the Voice notes add-on is not installed."
OFF_WEB = "I tried to search the web, but the search service is not answering. Start it or pick another provider in Settings, Web search."


@pytest.mark.parametrize("last,said,must,surface", [
    (OFF_AGENT, "turn it on", r"Agent mode", "reveal:chat-agent-mode"),
    (OFF_AGENT, "enable that", r"Agent mode", "reveal:chat-agent-mode"),
    (OFF_DICT, "turn it on please", r"Dictation", "reveal:notes-dictation"),
    ("Memory is off, so nothing is remembered.", "switch it on", r"Memory", "settings:memory"),
    ("Skills are off for this chat.", "can you turn them on", r"Skills", "settings:skills"),
    ("The OCR workspace is not enabled.", "turn on ocr", r"OCR workspace", "reveal:page-reader"),
])
def test_turn_it_on_offers_the_switch_and_never_flips_it(client, ask, last, said, must, surface):
    out = _ask(client, said, notes_only=True, answer_from="notes", history=[{"question": "x", "answer": last}])
    text = out["text"]
    assert re.search(must, text) and any(w in text for w in ("can not switch", "your call", "yours to flip"))
    offers = [e["offer"] for e in out.get("offer", [])]
    assert offers and offers[0]["kind"] == "open" and offers[0]["surface"] == surface


def test_turn_it_on_after_the_search_service_is_down_gives_the_docker_line(ask):
    said = ask("turn it on", [{"question": "who won", "answer": OFF_WEB}])
    assert "docker run" in said and "not start it for you" in said


def test_turn_it_on_with_nothing_off_is_left_alone(ask):
    assert "can not switch" not in ask("turn it on", [{"question": "hi", "answer": "Hello there."}])


def test_turn_on_dark_mode_is_not_a_tool_here(ask):
    assert "your call" not in ask("turn on dark mode")


def test_turn_it_on_wordings_vary_with_the_question():
    from tessellate.ai import composer_study, composer_switch
    seen = set()
    for i in range(40):
        ctx = composer_study.Ctx(question="turn it on", notes=[], now=NOW, history=[{"answer": OFF_AGENT}], seed=f"s{i}")
        seen.add(composer_switch.answer(ctx).text.split("\n")[0])
    assert len(seen) >= 6


def _due(ask):
    said = ask("what's due this week")
    return [{"question": "what's due this week", "answer": said}]


@pytest.mark.parametrize("q,must", [
    ("the second one", r"Item 2|Number 2|item 2|That one is"),
    ("tell me more about the second one", r"\*\*"),
    ("what about the first", r"Check-up booked for the 21st"),
    ("the 3rd", r"COMP2001 Assignment 2|Hand in the essay"),
    ("the last one", r"Gym session"),
])
def test_the_nth_one_after_a_due_list(ask, q, must):
    said = ask(q, _due(ask))
    assert re.search(must, said), said
    assert "couldn't find" not in said


def test_a_reminder_item_says_it_is_a_reminder(ask):
    said = ask("the second one", _due(ask))
    assert "reminder" in said and "Hand in the essay" in said


def test_a_note_item_names_its_note_and_how_its_day_was_read(ask):
    said = ask("the third one", _due(ask))
    assert "[COMP2001 Assignment 2](#/notes/5)" in said and "21 October" in said and "Friday" in said


def test_an_ordinal_past_the_list_says_how_long_it_was(ask):
    assert "listed 5 items" in ask("the sixth one", _due(ask))


def test_the_nth_without_a_list_is_left_alone(ask):
    said = ask("the second one", [{"question": "hi", "answer": "Hello there."}])
    assert "Item 2" not in said and "listed" not in said


def test_why_after_a_due_list_names_the_sources(ask):
    said = ask("why", _due(ask))
    assert "reminder" in said and "[COMP2001 Assignment 2](#/notes/5)" in said and "written" in said
    assert "Here is what is due" not in said


@pytest.mark.parametrize("q", ["why is that on there", "how come", "where did that come from", "why those"])
def test_why_wordings(ask, q):
    assert "Here is what is due" not in ask(q, _due(ask))


def test_why_after_a_countdown_quotes_the_note(ask):
    first = ask("how long until the exam")
    said = ask("why", [{"question": "how long until the exam", "answer": first}])
    assert "Exam on 12 November" in said and "[Lecture 5: Operating systems](#/notes/1)" in said


def test_flashcards_from_a_category_pool_its_notes(ask):
    said = ask("make flashcards from Uni")
    assert "Uni notes" in said or "from Uni" in said
    assert said.count("**Q:**") == 4 and said.count("(#/notes/") >= 2
    assert "Save these as a note" in said


def test_flashcards_from_one_note_are_unchanged(ask):
    said = ask("make flashcards from lecture 5")
    assert "Lecture 5: Operating systems" in said and "Uni notes" not in said


@pytest.mark.parametrize("q", ["flashcards from my Uni notes", "turn the uni notes into flashcards", "flash cards from uni"])
def test_category_flashcard_wordings(ask, q):
    assert "(#/notes/" in ask(q) and "**Q:**" in ask(q)
