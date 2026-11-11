"""R9-2/3 leftovers (composer audit round 9, c12): plot 14, why is my bread dense, the Q4 report due date, and the new
readers stay linear on a 50,000 character question. Seed: `tests/_seed_r9_1109.py`."""

from __future__ import annotations

import pytest

import tests._seed_r9_1109 as sd


@pytest.fixture
def ask(client, session, monkeypatch):
    sd.seed(session)
    go = sd.asker(client, monkeypatch)
    return lambda question: go(question)[0]


@pytest.mark.parametrize("question", ["what is plot 14", "what's my allotment plot number"])
def test_plot_14_is_the_plot_not_the_garlic(ask, question):  # R9-3
    assert ask(question).lstrip().startswith("Plot 14"), ask(question)


def test_why_is_my_bread_dense_is_the_note_that_says_dense(ask):  # R9-2
    assert ask("why is my bread dense").startswith("Too dense again"), ask("why is my bread dense")


def test_the_q4_report_due_date_is_the_q4_note(ask):  # R9-3
    text = ask("q4 report due date?")
    assert "20 November" in text.split("\n\n")[0] or "20 November" in text[:200], text
    assert not text.lstrip().startswith(("Four weeks ago", "You have four notes")), text


def test_new_readers_stay_linear_on_a_50k_question():
    import time

    from tessellate.ai import composer_label, composer_likeness, recognise
    from tessellate.ai import composer_digest_lines

    out = type("O", (), {"lines": [], "parts": [], "grounding": [], "rows": []})()
    for text in ("what is " + "a " * 25_000, "what's my " + " " * 50_000 + "plot number", "why is my " + "x" * 50_000, "q4 " * 17_000, "apples" * 8_000):
        start = time.perf_counter()
        composer_label.answer(out, text, [])
        composer_likeness.set_aside([], text)
        composer_digest_lines._predicate_stems(text)  # noqa: SLF001
        recognise.a_topic_phrase(text, "q4")
        assert time.perf_counter() - start < 0.5, text[:20]
