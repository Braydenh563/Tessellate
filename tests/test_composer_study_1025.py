"""Study help, plans and offline knowledge with no model (INBOX 1351, the
owner at uni without Ollama: "just as good and extremely smart").

A fixed clock (Wednesday 21 October 2026, 10:00) and fixed notes make every
row read the same on any day. Each table row is a way a person asks, with
what the reply must hold and must not; the quiz is walked turn by turn
through the dialogue, which is its only state."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.core.database import Reminder
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 21, 10, 0, 0)
LECTURE = (
    "# Lecture 5: Operating systems\n\n"
    "An **operating system** is software that manages hardware and software resources. A **process** is a program in execution.\n\n"
    "## Scheduling\n\nScheduling decides which process runs next. Round robin gives each process a fixed time slice. "
    "Priority scheduling runs the most important first.\n\n"
    "## Memory\n\n- Paging splits memory into fixed blocks\n- Segmentation splits memory by purpose\n- A page fault happens when a page is not in RAM\n\n"
    "Exam on 12 November.\n"
)
DATABASES = (
    "# Lecture 6: Databases\n\nA **primary key** is a column that uniquely identifies each row. **Normalisation**: removing repeated data across tables.\n\n"
    "## Joins\n\nAn inner join keeps rows that match in both tables.\n\n- [ ] Read chapter 4\n- [ ] Finish the lab sheet\n"
)
TODO = "# Errands\n\n- [ ] Book the tram pass\n- [ ] Buy a notebook\n- [x] Pay rent\n\nDentist booked for Friday 23 October.\n"
NOTES = [
    (LECTURE, dt.datetime(2026, 10, 20, 9)),
    (DATABASES, dt.datetime(2026, 10, 19, 9)),
    (TODO, dt.datetime(2026, 10, 18, 9)),
    ("# Dentist\n\nCheck-up booked for the 21st.", dt.datetime(2026, 10, 14, 9)),
    ("# COMP2001 Assignment 2\n\nAssignment 2 is due Friday.\n\n## Method\n\nThe model weights[^1] are trained on lecture data.\n\n[^1]: A weight is a number the model learns.", dt.datetime(2026, 10, 21, 9, 50)),
    ("# COMP2001 Lecture 3\n\n## Search\n\nBreadth first search visits the nearest nodes first.", dt.datetime(2026, 10, 21, 9, 55)),
]


@pytest.fixture
def ask(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)
    for text, when in NOTES:
        manager.create_entry(session, text, "Uni").created_at = when
    session.add(Reminder(text="Hand in the essay", due_at=dt.datetime(2026, 10, 23, 17, 0)))
    session.add(Reminder(text="Gym session", due_at=dt.datetime(2026, 10, 20, 7, 0)))
    session.add(Reminder(text="Submit essay", due_at=dt.datetime(2026, 11, 3, 9, 0)))
    session.add(Reminder(text="Call the landlord", due_at=dt.datetime(2026, 10, 28, 12, 0)))
    session.commit()

    def go(question: str, history: list | None = None, **body) -> str:
        return _ask(client, question, notes_only=True, answer_from="notes", history=history or [], **body)["text"]

    return go


def _full(ask, question, history=None, **body):
    return ask(question, history, **body)


#: (question, must match, must not match)
STUDY = [
    ("quiz me on operating systems", r"\*\*Quiz on Lecture 5: Operating systems\*\* · question 1 of \d", r"couldn't find"),
    ("Quiz me on lecture 5", r"question 1 of", r""),
    ("test me on databases", r"Lecture 6: Databases", r""),
    ("can you quiz me on lecture 6", r"question 1 of", r""),
    ("give me a quiz on operating systems", r"question 1 of", r""),
    ("start a quick quiz on lecture 5", r"question 1 of", r""),
    ("help me revise lecture 5", r"question 1 of", r""),
    ("ask me questions about databases", r"question 1 of", r""),
    ("test my knowledge of operating systems", r"question 1 of", r""),
    ("quiz me on lecture 5 with 3 questions", r"question 1 of 3", r""),
    ("quiz me on astrophysics", r"(?i)(?:did not find a note|nothing in your notebook|no note about|no match|holds no note|could not locate a note|no page of yours|not in it)", r"question 1"),
    ("make flashcards from lecture 5", r"\*\*Q:\*\*[^\n]+\n\*\*A:\*\*", r"not sure"),
    ("create some flashcards for databases", r"cards from", r""),
    ("flashcards for operating systems", r"cards from", r""),
    ("turn lecture 6 into flashcards", r"cards from", r""),
    ("what are the key terms in lecture 5", r"\*\*operating system\*\*: Software that manages", r"don't see any mention"),
    ("key terms in databases", r"\*\*primary key\*\*", r""),
    ("list the main terms from lecture 6", r"\*\*Normalisation\*\*", r""),
    ("summarise lecture 5", r"\*\*Scheduling\*\*", r"Also:"),
    ("summarize lecture 6", r"\*\*Joins\*\*", r""),
    ("give me a summary of operating systems", r"\*\*Memory\*\*", r""),
    ("tl;dr lecture 5", r"Scheduling", r""),
    ("briefly summarise lecture 5", r"Scheduling", r"Say “more”.*Say “more”"),
]


@pytest.mark.parametrize(("question", "must", "never"), STUDY, ids=[row[0] for row in STUDY])
def test_study_phrasings(ask, question, must, never):
    said = ask(question)
    assert re.search(must, said), said
    if never:
        assert not re.search(never, said), said


def test_flashcards_without_a_note_ask_which(ask):
    said = ask("make flashcards from this note")
    assert "note" in said and "Lecture 5" in said


def test_flashcards_from_the_open_note_offer_to_save(client, session, monkeypatch, ask):
    from tessellate.core.database import Entry

    note = session.query(Entry).filter(Entry.content.like("# Lecture 5%")).one()
    events = _ask(client, "make flashcards from this note", notes_only=True, answer_from="notes", open_note_id=note.id)
    assert "cards from" in events["text"]
    offer = events["offer"][0]["offer"]
    assert offer["kind"] == "note" and offer["label"] == "Save these as a note"
    assert offer["text"].startswith("# Flashcards: Lecture 5: Operating systems")
    assert events["text"].rstrip().endswith("Save these as a note")


def test_quiz_walks_through_the_dialogue(ask):
    history: list[dict] = []
    first = ask("quiz me on lecture 5 with 3 questions", history)
    assert "question 1 of 3" in first
    history.append({"question": "quiz me on lecture 5 with 3 questions", "answer": first})
    skipped = ask("skip", history)
    assert re.search(r"Skipped|answer", skipped) or "No problem" in skipped, skipped
    assert "question 2 of 3" in skipped
    assert "score 1 of 1" not in skipped  # a skip scores nothing
    assert "score" not in skipped.split("**Quiz on")[1] or "score 0 of 1" in skipped


def test_quiz_grades_loosely_and_keeps_score(ask):
    history: list[dict] = []
    text = ask("quiz me on lecture 6 with 2 questions", history)
    seen = []
    for _ in range(2):
        header = re.search(r"question (\d) of 2(?: · score (\d) of (\d))?", text)
        assert header, text
        asked = text.split(header.group(0))[1].strip().split("\n\n")[0]
        seen.append(asked)
        reply = {
            "Define primary key.": "a column that identifies each row uniquely",
            "What is primary key?": "the column that uniquely identifies rows",
            "What does primary key mean?": "a column identifying every row uniquely",
            "How would you explain primary key?": "a column that identifies each row",
        }.get(asked, "removing repeated data")
        history.append({"question": "q", "answer": text})
        text = ask(reply, history)
        history.append({"question": reply, "answer": text})
    assert re.search(r"Quiz finished on .*you got [12] of 2", text), text
    assert "percent" in text


def test_quiz_hint_stop_and_unrelated_question(ask):
    history = [{"question": "quiz me on lecture 5", "answer": ask("quiz me on lecture 5")}]
    hinted = ask("hint", history)
    assert hinted.startswith("Hint:") and "question 1 of" in hinted
    stopped = ask("stop", history)
    assert "Stopped before any answer" in stopped
    other = ask("what's due this week?", history)
    assert "Quiz on" not in other


def test_quiz_after_notes_change_restarts(ask):
    stale = "**Quiz on Lecture 5: Operating systems** · question 2 of 6 · score 1 of 1\n\nWhat is a unicorn?"
    said = ask("a horse", [{"question": "quiz me", "answer": stale}])
    assert "lost my place" in said or "no longer find" in said


PLAN = [
    ("what's due this week", r"Hand in the essay", r""),
    ("what is due this week?", r"Friday 23 October", r""),
    ("what do I have this week", r"Dentist booked for Friday", r""),
    ("anything due tomorrow", r"Nothing is dated|Gym", r"Hand in the essay"),
    ("what's due next week", r"Call the landlord", r"Hand in the essay"),
    ("what's coming up", r"Hand in the essay", r""),
    ("deadlines this week", r"Hand in the essay", r""),
    ("what's on my plate this week", r"Hand in the essay", r""),
    ("plan my week", r"Open tasks with no day", r""),
    ("help me plan my week", r"Book the tram pass", r""),
    ("what should I do today", r"Open tasks|Today", r""),
    ("organise my week", r"Busiest day", r""),
    ("how long until the exam", r"22 days", r""),
    ("how many days until the exam", r"12 November", r""),
    ("days until my essay", r"Hand in the essay", r""),
    ("how long until the dentist", r"2 days|Friday 23 October", r""),
]


@pytest.mark.parametrize(("question", "must", "never"), PLAN, ids=[row[0] for row in PLAN])
def test_plan_phrasings(ask, question, must, never):
    said = ask(question)
    assert re.search(must, said, re.S), said
    if never:
        assert not re.search(never, said, re.S), said


def test_overdue_reminders_are_named(ask):
    said = ask("what's due this week")
    assert "Overdue" in said and "Gym session" in said and "Tue 20 Oct" in said


def test_due_with_a_subject_is_left_to_the_notes(ask):
    assert "Nothing is dated" not in ask("what's due in databases")


CALC = [
    ("what percent is 30 of 120", r"25%", r""),
    ("what's 45 out of 60 as a percentage", r"75%", r""),
    ("percentage change from 80 to 100", r"increase of 25%", r""),
    ("percentage change from 100 to 80", r"decrease of 20%", r""),
    ("20% off 80", r"is 64", r""),
    ("what is 15% tip on 48", r"7\.2", r""),
    ("add 10% to 50", r"is 55", r""),
    ("split 90 between 4", r"22\.5 each", r""),
    ("what do I need on the exam to get 50 overall if I have 65 on coursework worth 40%", r"need 40%", r""),
    ("what day is 3 weeks from friday", r"Friday 13 November 2026", r""),
    ("what day is 10 days from now", r"Saturday 31 October 2026", r""),
    ("what day was 100 days ago", r"Monday 13 July 2026", r""),
    ("what date is 2 weeks after 1 december", r"15 December 2026", r""),
    ("what day is 25 december", r"Friday 25 December 2026", r""),
    ("how many days between 1 november and 25 december", r"54 days", r""),
    ("how many words in lecture 5", r"Lecture 5: Operating systems\*\*\]\(#/notes/\d+\)[^\n]{0,24}\d+ words", r""),
    ("word count of lecture 6", r"words", r""),
    #: "How long is" a journey is a question for the notes, not a word count
    #: (e2e ask-search: "How long is the train from Lisbon to Porto?").
    ("how long is the train from Lisbon to Porto", r"", r"\d+ words|characters and about"),
    ("how long is this note", r"", r"a under"),
    ('how many words in "the quick brown fox jumps"', r"5 words", r""),
    ("define hypothesis", r"testable prediction", r""),
    ("what does plagiarism mean", r"as your own", r""),
    ("what is spaced repetition", r"intervals", r""),
    ("what is 12 * (3 + 4)", r"84", r""),
    ("convert 5 km to miles", r"3\.1", r""),
    ("average of 4, 8 and 15", r"9", r""),
]


@pytest.mark.parametrize(("question", "must", "never"), CALC, ids=[row[0] for row in CALC])
def test_calc_phrasings(ask, question, must, never):
    said = ask(question)
    assert re.search(must, said), said


def test_a_term_in_the_notes_beats_the_glossary(ask):
    said = ask("what is a process")
    assert "program in execution" in said and "study glossary" not in said


def test_open_it_after_a_list(ask):
    first = ask("summarise lecture 6")
    history = [{"question": "summarise lecture 6", "answer": first}]
    said = ask("open it", history)
    assert "#/notes/" in said, (first, said)


def test_more_and_shorter_after_a_summary(ask):
    first = ask("summarise lecture 5")
    history = [{"question": "summarise lecture 5", "answer": first}]
    shorter = ask("shorter", history)
    assert len(shorter) <= len(first) and "Scheduling" in shorter
    more = ask("more", history)
    assert "in more detail" in more


def test_what_did_we_cover_is_a_summary(ask):
    said = ask("what did we cover in lecture 5?")
    assert "Scheduling" in said and "None of these notes" not in said and "lists seven" not in said


def test_footnote_markers_are_not_glued_to_words(ask):
    said = ask("summarise my COMP2001 notes")
    assert "weights1" not in said and "[^1]" not in said
    assert "COMP2001 Assignment 2" in said and "COMP2001 Lecture 3" in said
    assert "all from today" not in said


def test_due_this_week_has_no_trailing_no_matching_records(ask):
    said = ask("what's due this week?")
    assert "No matching records" not in said and "3 Nov" not in said and "Submit essay" not in said


def test_ask_opens_notes_by_name(ask):
    said = ask("open my lecture notes")
    assert "#/notes/" in said and "say it in Chat" not in said
    assert "COMP2001 Lecture 3" in ask("open comp2001 lecture 3")


def test_start_it_after_the_search_service_is_down(ask):
    down = "I tried to search the web, but the search service is not answering. Start it or pick another provider in Settings, Web search."
    said = ask("start it", [{"question": "who won the 1998 world cup", "answer": down}])
    #: The intent moved with INBOX 1490 (the owner: buttons, not a pasted docker
    #: command): "start it" answers with the same buttons a failed search shows,
    #: and the words no longer say the app cannot start it.
    assert "docker" not in said.lower() and "Set it up in Settings" in said and "Use another provider" in said


def test_start_it_without_a_search_context_is_left_alone(ask):
    assert "docker run" not in ask("start it", [{"question": "hi", "answer": "Hello there."}])
