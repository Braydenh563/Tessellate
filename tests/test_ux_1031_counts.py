"""Audit 1031 class 25 (SH6, SH8, SH9, SH15): the lock says the throttle, and
the notebook's counts say what they count.

SH6: a 429 from /auth/unlock is shown with its wait, Unlock is off until it
passes (it kept "That password is wrong." for a right password typed early).
SH8: an export marks a board's companion entry, so a count of the file and a
count of the list can be told apart. SH9: a one-word reply is not a greeting.
SH15: the Timeline's "230 items" says which kinds make it."""

from __future__ import annotations

from pathlib import Path

from tessellate.api import routes_insights

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_a_throttled_unlock_shows_its_wait_and_turns_unlock_off():
    text = _js("settings-wiring.js")
    body = text.split("function lockFailed(error)", 1)[1].split("\nasync function submitLockForm", 1)[0]
    assert "error.status !== 429" in body
    assert "submit.disabled = true;" in body and "submit.disabled = false;" in body
    assert "setTimeout(tick, 1000)" in body and "setInterval" not in body
    # Both the password and the prompt path read the throttle.
    assert text.count("lockFailed(error);") == 2


def test_the_unlock_throttle_names_its_wait_in_a_header_too():
    text = (ROOT / "src" / "tessellate" / "api" / "routes_auth.py").read_text(encoding="utf-8")
    assert 'headers={"Retry-After": str(int(remaining) + 1)},' in text


def test_a_one_word_reply_is_not_a_greeting():
    assert routes_insights._clean_greeting("Ok.") is None
    assert routes_insights._clean_greeting("good morning") == ("Good morning", ".")


def test_the_timeline_count_line_names_its_kinds():
    text = _js("timeline.js")
    assert "function timelineKindsText(rows)" in text
    assert "${timelineKindsText(rows)} · ${tail}" in text
    # The feed (appended), the grid and the table all hand their rows over.
    assert text.count("timelineCountLine(") == 4 and text.count(", rows)") >= 2 and "    shownRows);" in text


def test_an_export_says_which_entries_are_a_boards_companion(client, session):
    from tessellate.core.database import Entry

    note = client.post("/entries", json={"content": "a plain note about harbours"})
    assert note.status_code == 201, note.text
    session.add(Entry(content="Harbor launch board", is_board=True))
    session.commit()
    rows = client.get("/export/json").json()["entries"]
    marks = {row["content"]: row["is_board"] for row in rows}
    assert marks["a plain note about harbours"] is False
    assert marks["Harbor launch board"] is True
