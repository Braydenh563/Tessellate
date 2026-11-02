"""The notebook is asked about itself (audit 1029 C32, rank 31): "what is
new", "what changed", "what is my longest streak" and the phrasings kin to
them are answered from the app's own counts (notes made and edited in a
window, the longest run of consecutive days with a note), never as a search
and never as the assistant's intro. The class, not the case: many phrasings,
Ask and Chat, a model off and on (CHAT_PLAN decision 75: with a model on the
shape still answers, its figures the model's facts). Dates only when the
question asks about time (INBOX 1441).

Fixed clock: Thursday 29 October 2026, 10:00. Notes are made on 5 to 9 October
(five days running), 20 to 22 (three), and 28 and 29 (two, the run now); an old
note was edited on the 27th.
"""

from __future__ import annotations

import datetime as dt
import json
import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Entry

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)

_MONTH = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(
    rf"\b\d{{1,2}} (?:{_MONTH})\b|\b(?:{_MONTH}) \d{{1,2}}\b|\b(?:yesterday|today|a week ago)\b|\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{{1,2}}\b", re.I)
_INTRO = re.compile(r"assistant|Connecting a model|couldn't find|None of your notes|mention", re.I)

#: Made and edited, in the last seven days, no time asked.
NEW = ["what is new", "what's new", "whats new", "anything new", "is there anything new", "what's new in my notes", "show me what's new"]
NEW_TIMED = ["what is new this week", "what changed this week", "what changed since last week",
             "anything changed", "what have I been working on lately", "what's new lately"]
#: The bare "what changed" is Chat's starter (`starter_acts._changed`, since this
#: time yesterday); in Ask it is the same shape over the last seven days.
BARE = ["what changed", "what has changed", "anything changed"]
#: Made only.
ADDED = ["what have I added lately", "what have I added recently", "what have I added this week", "what new notes do I have",
         "what notes did I make recently", "any new notes", "what did I add lately"]
#: Edited only.
EDITED = ["what did I change this week", "what have I changed lately", "what did I edit this week", "what did I update recently",
          "what notes have I edited lately"]
STREAK = ["what's my longest streak", "what is my longest streak", "my longest streak", "my writing streak",
          "what is my writing streak", "how many days in a row have I written", "how many days in a row did I write a note",
          "what's the most days in a row I've written", "how many consecutive days have I written",
          "what is my best streak", "longest run of days with a note", "how long is my streak", "what's my current streak",
          "have I got a streak"]


def _seed(session, notes: dict[int, str] | None = None) -> None:
    days = {d: f"# Chess opening {d}\n\nStudy line {d}." for d in range(5, 10)}
    days |= {20: "# Lentil soup\n\nSimmer.", 21: "# Pasta night\n\nBoil.", 22: "# Bread rota\n\nBake."}
    days |= {28: "# Harbor launch plan\n\nShip the app.", 29: "# Dentist visit\n\nAsk about the guard."}
    for day, text in (notes if notes is not None else days).items():
        at = dt.datetime(2026, 10, day, 9, 0)
        session.add(Entry(content=text, created_at=at, updated_at=at))
    session.flush()
    if notes is None:
        old = session.query(Entry).filter(Entry.content.like("# Chess opening 5%")).one()
        old.edited_at = dt.datetime(2026, 10, 27, 10, 0)
    session.commit()


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)


def _stream(client, question: str, **body) -> tuple[list, str]:
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, **body}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events, "".join(e.get("delta", "") for e in events if e["type"] == "answer")


ASK = {"notes_only": True, "answer_from": "notes"}
CHAT = {"use_tools": False}
SURFACES = pytest.mark.parametrize("body", [ASK, CHAT], ids=["ask", "chat"])


@SURFACES
@pytest.mark.parametrize("question", NEW)
def test_what_is_new_is_what_was_made_and_edited(client, session, clock, body, question):
    _seed(session)
    _, text = _stream(client, question, **body)
    assert "Harbor launch plan" in text and "Dentist visit" in text, text
    assert "Chess opening 5" in text, text  # edited on the 27th
    assert "Lentil" not in text and "Chess opening 7" not in text, text
    assert not _INTRO.search(text), text
    assert re.search(r"\b(?:two|2) notes\b", text), text
    assert not _DATE.search(text), f"a date where the question is not about time: {text}"


@SURFACES
@pytest.mark.parametrize("question", NEW_TIMED)
def test_a_question_about_time_is_answered_with_the_window(client, session, clock, body, question):
    _seed(session)
    _, text = _stream(client, question, **body)
    assert "Harbor launch plan" in text and "Chess opening 5" in text, text
    assert "Chess opening 7" not in text, text
    assert not _INTRO.search(text), text


@pytest.mark.parametrize("question", BARE)
def test_a_bare_what_changed_is_counted(client, session, clock, question):
    _seed(session)
    _, ask = _stream(client, question, **ASK)
    assert "Harbor launch plan" in ask and "Chess opening 5" in ask, ask
    _, chat = _stream(client, question, **CHAT)
    assert re.search(r"\bedited\b", chat) and not _INTRO.search(chat), chat


@SURFACES
@pytest.mark.parametrize("question", ADDED)
def test_what_was_added_is_what_was_made(client, session, clock, body, question):
    _seed(session)
    _, text = _stream(client, question, **body)
    assert "Harbor launch plan" in text and "Dentist visit" in text, text
    assert "Chess opening 5" not in text and "edited" not in text, text
    assert not _INTRO.search(text), text


@SURFACES
@pytest.mark.parametrize("question", EDITED)
def test_what_i_changed_is_what_was_edited(client, session, clock, body, question):
    _seed(session)
    _, text = _stream(client, question, **body)
    assert "Chess opening 5" in text, text
    assert "Harbor launch plan" not in text, text
    assert not _INTRO.search(text), text


@SURFACES
@pytest.mark.parametrize("question", STREAK)
def test_a_streak_is_the_longest_run_of_days_with_a_note(client, session, clock, body, question):
    _seed(session)
    _, text = _stream(client, question, **body)
    assert re.search(r"\b(?:5|five) days\b", text), text
    assert not _INTRO.search(text), text
    assert not re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d", text), text


def test_a_streak_names_its_dates_only_when_asked_about_time(client, session, clock):
    _seed(session)
    plain = _stream(client, "what is my longest streak", **ASK)[1]
    timed = _stream(client, "when was my longest streak", **ASK)[1]
    assert not _DATE.search(plain), plain
    assert "5 to 9 October" in timed, timed


def test_the_run_now_is_said(client, session, clock):
    _seed(session)
    text = _stream(client, "what's my current streak", **ASK)[1]
    assert re.search(r"\b(?:2|two) days\b", text), text


def test_a_quiet_window_says_so(client, session, clock):
    _seed(session, {5: "# Old note\n\nx", 6: "# Older note\n\ny"})
    text = _stream(client, "what is new", **ASK)[1]
    assert re.search(r"nothing (?:new|was)", text, re.I), text
    assert not _INTRO.search(text), text


def test_no_notes_is_no_streak(client, session, clock):
    text = _stream(client, "what is my longest streak", **ASK)[1]
    assert "no notes yet" in text.lower() or "not written" in text.lower(), text


@pytest.mark.parametrize("question", ["what is new", "what changed since last week"])
@pytest.mark.parametrize("chat_body", [CHAT, {"use_tools": True}], ids=["chat", "popup-agent"])
def test_with_a_model_up_the_shape_hands_its_facts_to_the_model(ai_client, fake_ollama, session, clock, question, chat_body):
    _seed(session)
    fake_ollama.librarian_reply = "You made two notes and edited one."
    _, text = _stream(ai_client, question, **chat_body)
    assert fake_ollama.chat_calls, "the model was never asked"
    assert "Harbor launch plan" in "\n".join(str(m.get("content") or "") for m in fake_ollama.chat_calls[-1])
    assert not _INTRO.search(text), text


@pytest.mark.parametrize("question", ["what's my longest streak", "how many days in a row have I written"])
@pytest.mark.parametrize("chat_body", [CHAT, {"use_tools": True}], ids=["chat", "popup-agent"])
def test_with_a_model_up_a_streak_is_checked_against_the_figure(ai_client, fake_ollama, session, clock, question, chat_body):
    _seed(session)
    fake_ollama.librarian_reply = "Your longest streak is 9 days."
    _, wrong = _stream(ai_client, question, **chat_body)
    assert re.search(r"\b(?:5|five) days\b", wrong) and "9 days" not in wrong, wrong
    fake_ollama.librarian_reply = "Your longest streak is 5 days."
    _, right = _stream(ai_client, question, **chat_body)
    assert "5 days" in right, right


@pytest.mark.parametrize(
    "question",
    ["what is the new year's resolution note", "how do I make a streak widget", "what is a streak", "tell me about the new kitchen",
     "what changed in the harbor launch plan", "when did the dentist change my appointment", "new", "what's the newest note",
     "what is a new note", "how do I write a new note", "any updates", "what did I write", "what's new with the dentist",
     "show me what I wrote last week", "what did I write between the 24th and the 30th of September"],
)
def test_a_subject_question_is_not_the_shape(question):
    from tessellate.ai import activity_new

    assert activity_new.read(question) is None, question
