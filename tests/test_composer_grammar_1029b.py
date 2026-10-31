"""Frame grammar (audit 1029 rank 54; C6, C7, C11, C12, C13, C14).

The class: a frame was filled with whatever the facts held, so a zero read
"no of three", a hedge doubled ("about one every about three months"), a list
said more than it showed, a sentence said "it" with nothing before it, a
quote that ends a question took a stop after its mark, and a greeting was
answered in another part of the day. Each rule runs over the shapes of its
class, in Ask (`notes_only`) and in Chat, with no model.

Fixed clock: Thursday 29 October 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import re

import pytest

from tessellate.ai import activity, composer, composer_compose, composer_digest, realise
from tessellate.api import routes_chat
from tessellate.core import config
from tessellate.entry import manager
from tests.test_composer_frames_1029 import FAMILIES, _notes
from tests.test_composer_route_688 import _ask

NOW = dt.datetime(2026, 10, 29, 10, 0, 0)
D = dt.datetime

MODES = pytest.mark.parametrize("chat", [False, True], ids=["ask", "chat"])


@pytest.fixture
def book(client, session, monkeypatch):
    """A notebook with `_notes` of a family plus the extra notes, and a way to ask."""
    monkeypatch.setattr(config, "user_now", lambda _c: NOW)
    monkeypatch.setattr(routes_chat, "user_now", lambda _c: NOW)

    def build(extra: list[tuple[str, dt.datetime]] = (), fam=FAMILIES[0]):  # noqa: ANN001
        for text, when in [*_notes(fam), *extra]:
            entry = manager.create_entry(session, text, "Personal")
            entry.created_at = entry.updated_at = when
        session.commit()

        def ask(question: str, chat: bool) -> str:
            kw = {} if chat else {"notes_only": True, "answer_from": "notes"}
            return _ask(client, question, **kw)["text"]

        return ask

    return build


# --- C6: a zero is never "no" before "of" ------------------------------------------------

CHECKLISTS = [
    ("# Gear\n\n- [ ] tent\n- [ ] stove\n- [ ] torch", ["what is in my gear list", "tell me about gear", "what is left on gear"]),
    ("# Chores\n\n- [ ] sweep\n- [ ] mop\n- [x] bins\n- [ ] dust", ["what is in my chores list", "tell me about chores", "what is left on chores"]),
    ("# Errand\n\n- [ ] post the parcel", ["what is in my errand list", "tell me about errand", "what is left on errand"]),
]


@MODES
@pytest.mark.parametrize(("text", "questions"), CHECKLISTS, ids=["none-ticked", "one-ticked", "single-open"])
def test_a_zero_is_never_no_before_of(book, text, questions, chat):
    ask = book([(text, D(2026, 10, 14, 9))])
    found = []
    for q in questions:
        said = ask(q, chat)
        if re.search(r"\bno of\b|\bno (?:one )?of (?:one|two|three|four)\b", said, re.I):
            found.append(f"{q}\n{said}")
    assert not found, "\n\n".join(found)


@pytest.mark.parametrize(("ticked", "total", "lead", "said"), [
    (0, 3, "opening", "has none of its three checklist items done:"),
    (0, 3, "other", "Its checklist has none of its three done:"),
    (0, 1, "other", "Its checklist has one item, not done:"),
    (2, 3, "other", "Its checklist has two of three done:"),
    (1, 4, "opening", "has one of four checklist items done:"),
])
def test_a_checklist_count_reads_whatever_is_ticked(ticked, total, lead, said):
    items = "\n".join(f"- [{'x' if i < ticked else ' '}] item {i}" for i in range(total))
    view = composer.read_note({"id": 1, "content": f"# Gear\n\n{items}", "created_at": "2026-10-14T09:00:00", "category": "Personal", "tags": []}, 0)
    tasks = [s for s in view.sentences if s.kind == "task"]
    assert len(tasks) == total
    out = composer._Answer({1: view}, dt.date(2026, 10, 29))
    composer._checklist_count(out, view, tasks, lead)
    assert said in out.text, out.text


# --- C7: a hedge is said once --------------------------------------------------------------


def _frames() -> list[str]:
    found = []
    for key in ("stale", "burst", "cadence", "fresh"):
        said = composer_digest.PHRASES[key]
        found += [said] if isinstance(said, str) else list(said)
    return found


@pytest.mark.parametrize("days", [1, 2, 3, 5, 6, 10, 11, 14, 20, 24, 25, 30, 45, 46, 60, 75, 90, 150, 200, 364, 365, 400])
def test_no_gap_frame_doubles_about_or_every(days):
    gap, bare = composer_digest._gap(days), composer_digest._bare_gap(composer_digest._gap(days))
    for frame in _frames():
        said = frame.format(age=gap, span=gap, every=bare, count="three", all_of="All three")
        assert not re.search(r"\babout\b[^.,;]*\babout\b", said, re.I), said
        assert not re.search(r"\bevery (?:a|an|about|nearly|over)\b", said, re.I), said
        assert "about it about" not in said


@pytest.mark.parametrize(("gap", "bare"), [
    ("about three months", "three months"), ("about a month", "month"), ("a week", "week"), ("three weeks", "three weeks"),
    ("a few days", "few days"), ("over a year", "year"), ("two days", "two days"), ("nearly two months", "two months"),
])
def test_a_bare_gap_has_no_hedge_or_article(gap, bare):
    assert composer_digest._bare_gap(gap) == bare


# --- C11: a list says how many it left out ---------------------------------------------


@MODES
def test_a_day_list_that_is_cut_says_how_many_more(book, chat):
    cats = [(f"Note {i} about cats", D(2026, 10, 28, 8 + i % 3)) for i in range(12)]
    said = book(cats)("what did I write yesterday", chat)
    shown = len(re.findall(r"^- ", said, re.M))
    #: The twelve cats and the family's "Reading list" note, also written on the 28th.
    total = 13
    assert shown < total
    left = re.search(r"\bAnd (\w+) more\b", said)
    assert left, said
    words = {realise.count_word(n): n for n in range(1, 30)}
    more = int(left.group(1)) if left.group(1).isdigit() else words[left.group(1).lower()]
    assert shown + more == total, said


def test_a_busy_day_is_not_one_endless_bullet():
    clauses = [f"made the note Note {i}" for i in range(12)]
    lines = activity._day_lines({dt.date(2026, 10, 28): clauses}, dt.date(2026, 10, 29))
    assert len(lines) == 1 and lines[0].count("made the note") == activity._PER_DAY
    assert "and seven more" in lines[0], lines


# --- C12: a day with nothing in it does not say "it" -----------------------------------


@pytest.mark.parametrize(("question", "only_time"), [
    ("what did I write today", True), ("what did I write yesterday", True), ("what did I write last week", True),
    ("what did I write about atlas today", False), ("tell me about atlas", False),
])
def test_only_a_bare_day_question_drops_the_related_line(question, only_time):
    assert routes_chat._asks_only_a_time(question) is only_time


@MODES
@pytest.mark.parametrize("question", ["what did I write today", "what did I write today?", "anything written today"])
def test_an_empty_day_names_the_newest_note_and_no_it(book, question, chat):
    said = book()(question, chat)
    assert "other item" not in said and "mention it" not in said, said
    if "Nothing" in said or "nothing" in said:
        assert "starts on" not in said and "earliest" not in said.lower(), said


def test_a_window_after_the_newest_note_names_the_newest_note():
    said = composer.empty_window("today", dt.date(2026, 1, 5), dt.date(2026, 10, 28), today=dt.date(2026, 10, 29),
                                 window=(dt.date(2026, 10, 29), dt.date(2026, 10, 29)))
    assert "yesterday" in said and "5 January" not in said, said
    older = composer.empty_window("last month", dt.date(2026, 1, 5), dt.date(2026, 10, 28), today=dt.date(2026, 10, 29),
                                  window=(dt.date(2026, 3, 1), dt.date(2026, 3, 31)))
    assert "yesterday" not in older, older


# --- C13: punctuation and clauses ----------------------------------------------------------


@pytest.mark.parametrize(("text", "said"), [
    ("you noted what if the graph clustered by theme?.", "you noted what if the graph clustered by theme?"),
    ("**Also:** what happened next? What made you pick that?.", "**Also:** what happened next? What made you pick that?"),
    ("What happened next?, from your Mind map note.", "What happened next? From your Mind map note."),
    ("Wow!. Done.", "Wow! Done."),
    ("Left alone... really.", "Left alone... really."),
    ("A plain sentence, with a comma.", "A plain sentence, with a comma."),
])
def test_a_stop_is_not_added_after_a_question_or_an_exclamation(text, said):
    assert realise.mend_stops(text) == said


@MODES
def test_no_answer_has_double_punctuation_or_a_need_for_an_object(book, chat):
    extra = [
        ("what if the graph clustered by theme?", D(2026, 10, 20, 9)),
        ("# Mind map ideas\n\nwhat happened next? What made you pick that?", D(2026, 10, 19, 9)),
        ("# Money plan\n\nneed to cut eating out", D(2026, 10, 3, 9)),
        ("# Money log\n\nspent 40 on lunch. need to cut coffee", D(2026, 10, 4, 9)),
    ]
    ask = book(extra)
    found = []
    for q in ["what did I note about the graph", "tell me about mind map ideas", "tell me about money", "what did I note about money",
              "what is on my money plan", "what are my ideas", "tell me about the mind map"]:
        said = ask(q, chat)
        if re.search(r"[?!][.,]|\bit has need\b|\bwrote down need\b|\bnoted need\b|\bhas need to\b", said):
            found.append(f"{q}\n{said}")
    assert not found, "\n\n".join(found)


# --- C14: a greeting is answered in kind ---------------------------------------------------


@pytest.mark.parametrize(("question", "hour", "part"), [
    ("good morning", 15, "morning"), ("good afternoon", 9, "afternoon"), ("good evening", 9, "evening"),
    ("Good Morning!", 23, "morning"), ("morning", 14, "morning"), ("hello", 9, "morning"), ("hi there", 19, "evening"),
    ("what did I do this morning", 15, "afternoon"),
])
def test_a_greeting_is_answered_in_the_part_of_the_day_it_named(question, hour, part):
    assert composer_compose.greeted_as(question, hour) == part


@MODES
@pytest.mark.parametrize(("question", "word"), [("good afternoon", "afternoon"), ("good evening", "evening"), ("good morning", "morning")])
def test_a_named_greeting_is_never_answered_with_another(book, question, word, chat):
    said = book()(question, chat)
    others = {"morning", "afternoon", "evening", "night"} - {word}
    heard = [o for o in others if re.search(rf"\bgood {o}\b", said, re.I)]
    assert not heard, said


@pytest.mark.parametrize("hour", [0, 3, 23])
def test_good_morning_at_night_is_still_morning(hour):
    mood = composer_compose.mood_of("good morning", voice="natural", seed="s", said=[], intent="welcome")
    said = composer_compose.welcome(mood, hour=hour, notes=3, question="good morning")
    assert "good night" not in said.lower(), said

