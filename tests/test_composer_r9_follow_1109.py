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
    assert now.startswith("Too dense again"), now  # the newest note titled sourdough, not the first one


def test_who_wrote_it_says_the_notes_do_not_when_none_does(chain):
    _first, who = chain("what do I know about Wolf Hall", "who wrote it")
    assert who.startswith("Your notes do not say who wrote Wolf Hall"), who
    assert "tool by that name" not in who


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
