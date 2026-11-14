"""R9-9 rest (composer audit round 9, c12), driven as real dialogue chains through /chat/stream with the r9
seed: "and the others", "how is it now", "who wrote it". Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import time

import pytest

import tests._seed_r9_1109 as sd
from tessellate.ai import composer_credit


@pytest.fixture(params=[False, True], ids=["ask", "chat"])
def chain(request, client, session, monkeypatch):
    sd.seed(session)
    sd.fix_clock(monkeypatch)

    def run(*questions):
        history, texts = [], []
        for q in questions:
            text = sd.ask(client, q, history=history or None, notes_only=not request.param)["text"]
            history.append({"question": q, "answer": text})
            texts.append(text)
        return texts

    return run


def test_and_the_others_goes_on_with_the_question_before(chain):
    first, then, again = chain("what do I know about the kitchen", "and the others", "when does it start")
    assert "Not sure what you mean" not in then and "others" not in then.lower(), then
    assert "16 November" in again, again


def test_how_is_it_now_asks_for_the_latest_on_the_subject(chain):
    _first, now = chain("what do I know about sourdough", "how is it now")
    #: The newest note about it, not the first one: the starter note the person's notes call "Doug" is a day old (W7b B7).
    assert now.startswith("Doug the starter is bubbly again"), now


def test_who_wrote_it_says_the_notes_do_not_when_none_does(chain):
    _first, who = chain("what do I know about Wolf Hall", "who wrote it")
    assert who.startswith("Your notes do not say who wrote Wolf Hall"), who
    assert "tool for that too" not in who


def test_who_wrote_a_work_a_note_names_by_author(client, session, monkeypatch):
    from tessellate.entry import manager

    manager.create_entry(session, "# Reading\n\nFinished Piranesi, written by Susanna Clarke. Loved it.", category_name="Uncategorised")
    session.commit()
    sd.fix_clock(monkeypatch)
    text = sd.ask(client, "who wrote Piranesi", notes_only=True)["text"]
    assert "Susanna Clarke" in text and "do not say" not in text, text


def test_a_long_question_is_read_in_bounded_time():
    out = type("O", (), {"lines": [], "parts": [], "grounding": []})()
    for q in ("who wrote " + "a " * 25_000, "who wrote" + " " * 50_000 + "it", "who wrote " + "x" * 50_000):
        start = time.perf_counter()
        composer_credit.answer(out, q, [])
        assert time.perf_counter() - start < 0.5


#: L-chat-249: ten more two-turn follow-ups, each keeping the subject the first turn asked about
#: (the first turn, the follow-up, a phrase the answer must hold, one it must not).
TWO_TURNS = [
    ("what do I know about the kitchen renovation", "how much is it", "£8,000", "Wolf Hall"),
    ("what do I know about the plumber", "when is he coming", "11 November", "Mum"),
    ("what do I know about Mum", "when is her birthday", "2 December", "Plumber is"),
    ("what do I know about the doctor", "when is it", "13 November", "Raj"),
    ("what do I know about the car insurance", "how much is it", "£412", "Aviva"),
    ("what do I know about the concert", "when is it", "5 December", "Hannah"),
    ("what do I know about Pickle", "when is the booster jab", "January", "Marek"),
    ("what do I know about book club", "who hosts it", "Hannah", "Marek"),
    ("what did I write about mum", "what about last month", "Gift ideas", "Running log"),
    ("what did I write about mum", "and the other one", "mum", "Running log"),
]


@pytest.mark.parametrize(("first", "then", "holds", "never"), TWO_TURNS, ids=[t[1] + " / " + t[0][-14:] for t in TWO_TURNS])
def test_a_two_turn_followup_keeps_the_subject(chain, first, then, holds, never):
    _, again = chain(first, then)
    assert holds.lower() in again.lower() and never.lower() not in again.lower(), again
