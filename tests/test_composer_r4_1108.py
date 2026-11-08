"""Composer round 4, 2026-11-08: the rows of audits 1107 (D, E, R3) that were
still open or partly open when the answers were re-asked on the head. Every
question runs through the digest then the composer, as the route does; no
model, fixed clock (`_seed_r2_1107.TODAY`)."""

from __future__ import annotations

from datetime import date

from tests._seed_r2_1107 import TODAY, _route_answer, ask

assert TODAY == date(2026, 11, 7)


def _pool(*texts: str, ago: int = 0) -> list[dict]:
    day = date.fromordinal(TODAY.toordinal() - ago).isoformat()
    return [{"id": i, "content": t, "category": "Uncategorised", "tags": [], "created_at": f"{day}T10:00:00Z"} for i, t in enumerate(texts, 1)]


def say(question: str, *texts: str, ago: int = 0) -> str:
    return _route_answer(question, _pool(*texts, ago=ago))["text"]


def test_e6_a_limit_in_another_note_is_not_the_budget():
    said = ask("how much is left in my budget", only=("Budget", "Bank", "Car", "Dentist bill"))
    assert said.startswith("I found no budget figure in your notes."), said
    assert "over your" not in said and "$" not in said, said


SARA = (
    "# Sara\n\nSara is my sister. Her birthday is on 14 March.",
    "# Gift ideas\n\nSara wants a jazz record.",
    "Sara likes jazz",
)


def test_r3_4_the_first_note_about_a_subject_is_the_oldest_of_them():
    pool = _pool(*SARA)
    for note, ago in zip(pool, (30, 20, 3), strict=True):
        note["created_at"] = f"{date.fromordinal(TODAY.toordinal() - ago).isoformat()}T10:00:00Z"
    said = _route_answer("what is the first note I wrote about Sara", pool)["text"]
    assert said.startswith("Your first note about Sara is **Sara**, written "), said
    assert "Sara is your sister" in said, said


def test_r3_4_the_last_note_about_a_subject_is_the_newest_of_them():
    pool = _pool(*SARA)
    for note, ago in zip(pool, (30, 20, 3), strict=True):
        note["created_at"] = f"{date.fromordinal(TODAY.toordinal() - ago).isoformat()}T10:00:00Z"
    said = _route_answer("what is the last note about Sara", pool)["text"]
    assert said.startswith("Your latest note about Sara is "), said
    assert "likes jazz" in said, said


def test_r3_4_the_ordinal_reader_is_linear_on_long_runs():
    import time

    from tessellate.ai import composer_small

    for run in ("first note " * 4500, "the first note about " + "a " * 25_000, " " * 50_000, "last note about the " * 2500):
        t0 = time.perf_counter()
        composer_small.ordinal_about(run, [])
        assert time.perf_counter() - t0 < 2.0, run[:30]
