"""R9-4 and R9-5 (composer audit round 9): a quotation is the note's own text, and a
value is never split or re-dated while a line is said. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import re

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def say(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda q: go(q)[0]


def _contents() -> str:
    return " ".join(body for _t, body, _a in sd.NOTES)


@pytest.mark.parametrize("question", ["what do I know about python", "what have I noted about the doctor", "tell me about my mum", "how many notes mention Raj", "everything about Marek"])
def test_every_quotation_is_the_notes_own_text(say, question):
    held = re.sub(r"\s+", " ", _contents()).lower()
    for quote in re.findall(r"“([^”]+)”", say(question)):
        assert re.sub(r"\s+", " ", quote).lower().rstrip(".") in held, quote  # R9-4


def test_a_table_row_is_not_quoted_raw(say):
    text = say("everything about Marek")
    assert "|" not in text and "Marek at £7,200" in text  # R9-4


def test_a_remark_with_a_comma_is_not_made_a_list(say):
    assert "nothing, he's your boss" in say("how many notes mention Raj")  # R9-4: not "nothing and he's"


def test_a_comma_inside_a_figure_is_not_a_split(say):
    text = say("what do I know about Japan")
    assert "£2,400" in text and "£2, 400" not in text  # R9-5


def test_a_book_title_is_not_a_date(say):
    text = say("what am I reading")
    assert "Tomorrow and Tomorrow and Tomorrow" in text and "ago, on" not in text  # R9-5
