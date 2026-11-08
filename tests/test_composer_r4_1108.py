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
