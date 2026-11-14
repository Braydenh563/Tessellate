"""The companion's remarks (INBOX 743): the composer's words outside an answer
reach the page through `GET /insights/remarks`, from the notebook and no model."""

from __future__ import annotations

from datetime import datetime

from tessellate.api import routes_insights
from tessellate.core.database import Reminder
from tessellate.entry import manager

NOW = datetime(2026, 11, 1, 9, 0)


def _clock(monkeypatch) -> None:
    monkeypatch.setattr(routes_insights, "user_now", lambda _config: NOW)


def test_a_reminder_due_today_and_a_note_from_this_day_last_year_are_remarks(client, session, monkeypatch):
    _clock(monkeypatch)
    old = manager.create_entry(session, "# Lisbon\n\nBooked the hotel in Alfama for the first week.")
    old.created_at = datetime(2025, 11, 1, 10, 0)
    session.add(Reminder(text="Ring the landlord", due_at=NOW))
    session.commit()
    body = client.get("/insights/remarks").json()["remarks"]
    said = " ".join(r["text"] for r in body)
    assert "Ring the landlord" in said
    assert "Lisbon" in said or "hotel" in said
    assert all(r["key"] and "**" not in r["text"] for r in body)
    assert len({r["key"] for r in body}) == len(body)


def test_a_private_note_is_never_read_and_an_empty_notebook_says_nothing(client, session, monkeypatch):
    _clock(monkeypatch)
    assert client.get("/insights/remarks").json() == {"remarks": []}
    secret = manager.create_entry(session, "# Diary\n\nThe locksmith code is 4417.")
    secret.is_private = True
    secret.created_at = datetime(2025, 11, 1, 10, 0)
    session.commit()
    assert "4417" not in client.get("/insights/remarks").text


def test_the_page_says_a_remark_once_through_a_lazy_file_and_a_switch():
    from tests.test_ui_recipes import ROOT

    boot = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
    lazy = (ROOT / "frontend" / "js" / "companion-remark.js").read_text(encoding="utf-8")
    entries = (ROOT / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    # Boot carries a stand-in, not the code: the file is fetched on the first ask.
    assert 'companionRemark: ["/js/companion-remark.js"]' in entries
    assert 'companionRemark: ["nameMarkBuddyRemark"]' in entries
    assert "async function nameMarkBuddyRemark" not in boot
    # Asked from the mood tick, rarely, behind its own switch and the reaction gates.
    assert 'nameMarkBuddyActOff("remark") && nameMarkBuddyReact("remark")' in boot
    assert "remark: { cool: 3 * 60 * 60 * 1000" in boot
    assert '["remark", "Say something from your notes now and then", ["remark"]]' in boot
    # Never one it has said (by its fact, for 7 days, L-chat-54), and held as long as it takes to read.
    assert "said[r.fact || r.key]" in lazy and "nameMarkSay(buddy, next.text, Math.min(12000" in lazy
