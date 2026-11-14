"""L225: Not right stores (question, note id) on this device only; the first
mark says so in one line, and Settings has a row that clears every one."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mark(client, session_note_id, question="sourdough notes"):
    return client.post("/learned/answer-verdict", json={"question": question, "entry_ids": [session_note_id]})


def test_the_marks_are_counted_and_cleared_together(client):
    one = client.post("/entries", json={"content": "sourdough starter schedule"}).json()["id"]
    two = client.post("/entries", json={"content": "sourdough loaf shaping"}).json()["id"]
    assert client.get("/learned/answer-verdicts").json() == {"count": 0}
    assert _mark(client, one).status_code == 201 and _mark(client, two, "loaf").status_code == 201
    assert client.get("/learned/answer-verdicts").json() == {"count": 2}
    assert client.delete("/learned/answer-verdicts").json() == {"removed": 2}
    assert client.get("/learned/answer-verdicts").json() == {"count": 0}


def test_clearing_leaves_other_corrections_alone(client):
    note = client.post("/entries", json={"content": "sourdough starter schedule"}).json()["id"]
    _mark(client, note)
    other = client.post("/learned/corrections", json={"kind": "open_after_ask", "subject": {"question": "q", "entry_id": note}})
    client.delete("/learned/answer-verdicts")
    kinds = [row["kind"] for row in client.get("/learned/corrections").json()]
    assert "wrong_answer" not in kinds
    assert other.status_code != 201 or "open_after_ask" in kinds


def test_the_first_mark_says_it_stays_on_this_device_and_where_to_clear_it():
    chat = (ROOT / "frontend/js/chat-turn.js").read_text()
    assert "Stored only on this device. Clear it in Settings, What it learned." in chat
    assert "notRightNoted" in chat, "said once, not on every mark"


def test_settings_has_a_row_that_clears_the_marks():
    js = (ROOT / "frontend/js/settings-controls.js").read_text()
    assert "/learned/answer-verdicts" in js and "Clear answers marked not right" in js
