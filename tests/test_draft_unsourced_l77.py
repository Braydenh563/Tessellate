"""L-documents-77: a real 1.5B model wrote "meet at the lake at 9 AM" from
thoughts that held no time, though the prompt forbids invented details
(drafter.py:62). A prompt cannot make a small model obey, so the finished pass
names the times, numbers and placeholders the thoughts, the old draft and the
notes do not hold, and the Writing room shows them before the draft is sent.
"""

from __future__ import annotations

import json
from pathlib import Path

from tessellate.ai.drafter import unsourced_specifics


def test_a_time_or_number_nobody_wrote_is_named():
    got = unsourced_specifics(
        "Meet at the lake at 9 AM. We leave Friday at 4 pm with 2 tents. [Your Name]",
        "leave friday at 4pm, bring 2 tents",
    )
    assert got == ["9 AM", "[Your Name]"]


def test_a_number_in_a_note_or_the_old_draft_counts_as_written():
    assert unsourced_specifics("Budget is 1,200 and the date is 3 March.", "", "budget 1,200", "on 3 March") == []


def test_nothing_is_named_for_a_draft_with_no_specifics():
    assert unsourced_specifics("Bring the tent and the stove.", "tent, stove") == []


def _lines(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_the_stream_carries_the_unsourced_specifics(ai_client, fake_ollama):
    fake_ollama.librarian_reply = "See you at 9 AM by the lake."
    done = _lines(ai_client.post("/drafts/compose/stream", json={"thoughts": "lake trip friday"}))[-1]
    assert done["type"] == "done" and done["unsourced"] == ["9 AM"]


def test_the_writing_room_shows_them_in_the_status_line():
    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "writing-desk.js").read_text(encoding="utf-8")
    assert "done?.unsourced" in js and "not in your thoughts or notes" in js
