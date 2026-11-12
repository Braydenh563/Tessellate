"""G12 (second composer audit): the Patterns sentence is "Harbor has come up five times since
September", not "You have written about harbor 5 times"; the same hedge is said once in a list."""

from __future__ import annotations

from datetime import date

from tessellate.ai import insights

TODAY = date(2026, 11, 10)


def _note(i: int, content: str, day: str, tags: tuple = ()) -> dict:
    return {"id": i, "content": content, "created_at": day, "tags": list(tags)}


def _boiler_and_tap() -> list[dict]:
    days = ("2026-09-01", "2026-09-10", "2026-09-20", "2026-10-01")
    return [
        *(_note(i, "# Boiler\n\nThe boiler pressure dropped again.", d) for i, d in enumerate(days, 1)),
        *(_note(10 + i, "# Tap\n\nThe kitchen tap drips again.", d) for i, d in enumerate(days, 1)),
    ]


def test_a_recurrence_says_the_subject_with_its_capital_and_the_count_in_words():
    found = insights.recurrence("boiler", _boiler_and_tap(), TODAY)
    assert found.text == "Boiler has come up four times since 1 September; that keeps coming up."
    assert found.slots["count"] == 4 and found.slots["subject"] == "boiler"  # the slots stay typed


def test_a_count_over_twelve_stays_a_figure():
    days = [f"2026-09-{d:02d}" for d in range(1, 14)] + ["2026-10-05"]
    notes = [_note(i, "# Boiler\n\nBoiler pressure dropped.", d) for i, d in enumerate(days, 1)]
    assert insights.recurrence("boiler", notes, TODAY).text.startswith("Boiler has come up 14 times")


def test_the_hedge_is_said_once_in_a_list():
    notes = _boiler_and_tap()
    both = [insights.recurrence("boiler", notes, TODAY), insights.recurrence("tap", notes, TODAY)]
    lines = insights.listed(both)
    assert lines[0].endswith("that keeps coming up.")
    assert lines[1] == "Tap has come up four times since 1 September."
    assert "keeps coming up" not in lines[1]


def test_a_different_hedge_is_still_said():
    golf = [_note(30 + i, "# Golf\n\nGolf round after work.", d) for i, d in enumerate(("2026-09-02", "2026-09-12", "2026-09-22"))]
    notes = _boiler_and_tap() + golf
    lines = insights.listed([insights.recurrence("boiler", notes, TODAY), insights.recurrence("golf", notes, TODAY)])
    assert lines[0].endswith("keeps coming up.") and lines[1].endswith("hobby forming."), lines
