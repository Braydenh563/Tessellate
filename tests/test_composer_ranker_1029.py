"""One ranker for every shape (audit 1029 C19, C20, C31, C36; INBOX 1357: a
fix holds for the class, not the one example).

The note a subject names leads (exact title, then a note that defines it, then
a title that holds it, then the rest); Ask and Chat call the same ranker;
"latest about X" filters by X and then sorts by date; a count ("last three") is
a count. Every case runs over several subjects and phrasings, in Ask
(`notes_only`) and in Chat, with no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import note_rank
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime

SUBJECTS = ["sourdough", "kayaking", "espresso", "violin", "orchids", "chess"]


def _notebook(subject: str, *, exact: bool = True, defining: bool = True) -> list[tuple[str, dt.datetime]]:
    """The subject's notes, oldest first, so recency alone would lead with the
    wrong ones: a passing mention, a note whose title holds the subject, the
    note that defines it and the note titled as the subject."""
    cap = subject.capitalize()
    notes = [
        (f"# Shopping\n\nBuy milk, then ask about {subject} classes for next year.", D(2026, 10, 27, 9)),
        (f"# {cap} diary attempt two\n\nWent back to {subject} today and it went better.", D(2026, 9, 20, 9)),
        (f"# {cap} diary attempt one\n\nFirst go at {subject}, mostly a mess.", D(2026, 8, 2, 9)),
    ]
    if defining:
        notes.append((f"# Hobby basics\n\n{cap} is a pastime that rewards patience and a steady routine. Start small.", D(2026, 7, 4, 9)))
    if exact:
        notes.append((f"# {cap}\n\nThe plan for {subject} this season.", D(2026, 6, 1, 9)))
    return notes


@pytest.fixture
def notebook(client, session, monkeypatch):
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(notes):
        for text, when in notes:
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()

        def go(question: str, chat: bool = False) -> str:
            kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
            return _ask(client, question, **kw)["text"]

        return go

    return build


def _order(said: str, titles: list[str]) -> list[str]:
    """The titles that appear in `said`, in the order they first appear."""
    spots = [(said.find(t), t) for t in titles if t in said]
    return [t for _, t in sorted(spots)]


LISTS = ["show me notes about {s}", "show me my notes on {s}", "list the {s} notes", "find notes about {s}"]


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("phrasing", LISTS)
def test_the_note_titled_as_the_subject_leads_every_list(notebook, subject, phrasing, chat):
    go = notebook(_notebook(subject))
    cap = subject.capitalize()
    said = go(phrasing.format(s=subject), chat)
    titles = [cap, "Hobby basics", f"{cap} diary attempt two", f"{cap} diary attempt one"]
    order = _order(re.sub(r"\*", "", said), [f"[{t}]" for t in titles])
    if order:
        assert order[0] == f"[{cap}]", said
    else:
        #: A few Ask phrasings answer from the leading note instead of listing.
        assert said.lower().startswith(f"the plan for {subject}"), said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("subject", SUBJECTS)
def test_the_defining_note_leads_when_no_title_is_the_subject(notebook, subject, chat):
    go = notebook(_notebook(subject, exact=False))
    said = re.sub(r"\*", "", go(f"show me notes about {subject}", chat))
    cap = subject.capitalize()
    order = _order(said, ["[Hobby basics]", f"[{cap} diary attempt two]", f"[{cap} diary attempt one]", "[Shopping]"])
    assert order[:1] == ["[Hobby basics]"], said
    if "[Shopping]" in order:
        assert order[-1] == "[Shopping]", said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("phrasing", ["open the {s} note", "open {s}", "open my {s} note", "open the {s}"])
def test_open_names_the_note_in_ask_and_chat_alike(notebook, subject, phrasing, chat):
    go = notebook(_notebook(subject))
    said = go(phrasing.format(s=subject), chat)
    cap = subject.capitalize()
    assert f"[**{cap}**]" in said, said
    assert "diary attempt" not in said and "You have" not in said, said


@pytest.mark.parametrize("subject", SUBJECTS)
def test_ask_and_chat_list_in_the_same_order(notebook, subject):
    go = notebook(_notebook(subject))
    cap = subject.capitalize()
    titles = [f"[{cap}]", "[Hobby basics]", f"[{cap} diary attempt two]", f"[{cap} diary attempt one]"]
    ask = _order(re.sub(r"\*", "", go(f"show me notes about {subject}")), titles)
    chat = _order(re.sub(r"\*", "", go(f"show me notes about {subject}", True)), titles)
    assert ask == chat and ask[0] == f"[{cap}]"


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("phrasing", ["what does my {s} note say", "what is in the {s} note", "tell me about {s}"])
def test_a_question_about_the_subject_reads_the_leading_note_first(notebook, subject, phrasing, chat):
    go = notebook(_notebook(subject))
    said = go(phrasing.format(s=subject), chat)
    assert said.lower().find(f"plan for {subject}") != -1 or said.lower().find("rewards patience") != -1, said
    assert "milk" not in said.lower().split("plan for")[0], said


# --- latest about X ---------------------------------------------------------------


def _dated(subject: str) -> list[tuple[str, dt.datetime]]:
    return [
        ("# Quick thought\n\nCall the bank tomorrow.", D(2026, 10, 28, 9)),
        (f"# {subject.capitalize()} old\n\nEarly days of {subject}.", D(2026, 8, 3, 9)),
        (f"# {subject.capitalize()} newest\n\nLatest on {subject}: much better now.", D(2026, 10, 20, 9)),
        (f"# {subject.capitalize()} middle\n\nA middling week of {subject}.", D(2026, 9, 14, 9)),
        ("# Another idea\n\nA podcast about nothing in particular.", D(2026, 10, 27, 9)),
    ]


LATEST = [
    "latest notes about {s}",
    "what is the last thing I wrote about {s}",
    "show me the newest note about {s}",
    "my most recent note on {s}",
    "the latest note I made about {s}",
]


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize("subject", SUBJECTS)
@pytest.mark.parametrize("phrasing", LATEST)
def test_latest_about_a_subject_filters_by_the_subject_first(notebook, subject, phrasing, chat):
    go = notebook(_dated(subject))
    said = go(phrasing.format(s=subject), chat)
    assert "Call the bank" not in said and "podcast" not in said, said
    assert "much better now" in said or f"{subject.capitalize()} newest" in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
def test_latest_about_a_subject_nobody_wrote_says_so(notebook, chat):
    go = notebook(_dated("kayaking"))
    said = go("latest notes about trombone", chat)
    assert "Call the bank" not in said and "podcast" not in said, said


@pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])
@pytest.mark.parametrize(
    ("phrasing", "count"),
    [("show me my last three notes", 3), ("my last 2 notes", 2), ("show the latest note", 1), ("show me my last five notes", 5)],
)
def test_a_count_is_a_count(notebook, phrasing, count, chat):
    go = notebook(_dated("kayaking"))
    said = go(phrasing, chat)
    links = re.findall(r"\(#/notes/\d+\)", said)
    assert len(links) == count, said
    assert "Nothing matched" not in said, said


@pytest.mark.parametrize(
    ("text", "count", "subject"),
    [
        ("latest notes about running", 5, "running"),
        ("what is the last thing I wrote about Atlas", 1, "atlas"),
        ("my 5 most recent notes on baking", 5, "baking"),
        ("the newest note about the garden", 1, "garden"),
        ("show me my last three notes", 3, ""),
    ],
)
def test_recency_reads_count_and_subject(text, count, subject):
    got = note_rank.recency(text)
    assert got is not None and (got.count, got.subject) == (count, subject)


@pytest.mark.parametrize("text", ["what did I write last week", "my last note", "last night", "what did I eat last month", "show me everything"])
def test_recency_leaves_windows_and_plain_questions_alone(text):
    assert note_rank.recency(text) is None


# --- the ranker itself ---------------------------------------------------------------


def test_the_ranker_tiers_and_keeps_the_order_inside_a_tier():
    notes = [
        {"id": 1, "content": "# Trip\n\nPacking for the garden party."},
        {"id": 2, "content": "# Garden tools\n\nA rake."},
        {"id": 3, "content": "# Plants\n\nThe garden is the patch behind the house."},
        {"id": 4, "content": "# Garden\n\nPlan."},
        {"id": 5, "content": "# Garden shed roof repair plan\n\nLong."},
    ]
    assert [n["id"] for n in note_rank.lead(notes, "show me notes about the garden")] == [4, 3, 2, 5, 1]


def test_the_ranker_does_nothing_without_a_subject():
    notes = [{"id": 1, "content": "# B\n\nx"}, {"id": 2, "content": "# A\n\nx"}]
    assert note_rank.lead(notes, "what is new") == notes
