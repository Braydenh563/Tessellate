"""Proofreading a long, misspelled note costs about 0.3 ms a character (13.8 s
at 40,000), so `/improve` proofreads the start of it, keeps the rest as
typed, and says so; no 4xx for a long note."""

from __future__ import annotations

import time

from tessellate.ai import proofread

LINE = "teh meeting shoud be on mondey, we recieve the pakage and i went to teh shop.\n"


def _note(chars: int) -> str:
    return (LINE * (chars // len(LINE) + 1))[:chars]


def test_a_long_note_is_proofread_in_bounded_time(client):
    text = _note(40_000)
    started = time.perf_counter()
    response = client.post("/entries/improve", json={"text": text, "mode": "proofread"})
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    body = response.json()
    assert elapsed < 8.0, f"proofreading took {elapsed:.1f}s"
    assert body["truncated"] is True
    assert "first" in body["said"] and "proofread" in body["said"]
    # The start is put right, the rest is exactly as typed, none of it lost.
    assert body["improved"].startswith("The meeting")
    assert body["improved"].endswith(text[proofread.covered(text) :])
    assert len(body["improved"]) >= len(text) - 4_000


def test_a_short_note_is_all_proofread_and_not_marked_truncated(client):
    body = client.post("/entries/improve", json={"text": "teh meeting shoud be on monday", "mode": "proofread"}).json()
    assert body["truncated"] is False
    assert "first" not in body["said"]


def test_the_covered_part_ends_at_a_line(client):
    text = _note(10_000)
    covered = proofread.covered(text)
    assert 0 < covered <= proofread.PROOFREAD_CHARS
    assert text[covered - 1] == "\n"
    assert proofread.covered("short") == 5
