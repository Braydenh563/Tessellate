"""Answers that join their facts (INBOX 870, the owner: "one or two words
between directly giving me what I can see from the notes on the right ...
feels like the response is completely useless"). Each clause tested here
is one no single note says: where the person has got to, the time between
two notes, a gap between prices, a month's distance, an aim met, how the
notes sit in time. The share of sentences that only restate one note is a
ratchet (42% before; `scratchpad/restate_share.py` prints it per answer).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scratchpad"))
import restate_share  # noqa: E402

from tessellate.ai import composer_digest  # noqa: E402

#: Measured 2026-10-11: 33/82 before INBOX 870 was 42%; after, 33%.
RESTATE_CEILING = 0.35


def _text(n: int) -> str:
    item = next(a for a in restate_share.FIXTURE["answers"] if a["n"] == n)
    return composer_digest.answer(item["question"], restate_share.NOTES, today=restate_share.TODAY)["text"]


@pytest.mark.parametrize(("n", "clause"), [
    (2, "you're leaning towards the Logitech"),
    (2, "a gap of about $30 between them"),
    #: The time between two notes is said only for a question about time
    #: (INBOX 1441, the owner, 2026-10-29, over 2026-10-11's "a week later").
    (2, "You tried the Viper at JB Hi-Fi"),
    #: Said as then, as the gold has it (atlas narration, the owner 2026-10-11).
    (1, "though you were still shaky on big O"),
    #: The staleness line only for a question about now (INBOX 1441).
    (1, "Nothing yet on assessments or due dates"),
    (12, "with one thing still open"),
    (12, "May, which is seven months from now"),
    (15, "under your aim of $100 a week"),
    (10, "a mixed 7"),
])
def test_each_answer_says_what_no_one_note_says(n, clause):
    assert clause in _text(n)


def test_the_decision_is_said_once_up_front():
    text = _text(2)
    assert text.count("leaning towards the Logitech") == 1
    assert "**Where you landed:**" not in text


def test_jokes_get_no_staleness_line():
    assert "moved on" not in _text(13) and "fresh note" not in _text(13)


def test_the_wording_varies_with_the_question():
    from tessellate.ai.composer_digest import _BASE

    assert all(isinstance(_BASE[k], tuple) and len(_BASE[k]) >= 2 for k in ("gap", "stale", "burst", "cadence", "landed"))


def test_fewer_sentences_only_restate_a_note():
    total = restated = 0
    for item in restate_share.FIXTURE["answers"]:
        if item["kind"] != "notes":
            continue
        result = composer_digest.answer(item["question"], restate_share.NOTES, today=restate_share.TODAY)
        if not result:
            continue
        said = restate_share.sentences(result["text"])
        total += len(said)
        restated += sum(restate_share.restates(s) for s in said)
    assert restated / total <= RESTATE_CEILING, f"{restated}/{total}"
