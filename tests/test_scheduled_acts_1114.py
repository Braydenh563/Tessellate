"""L-chat-106 (CHAT_PLAN X15, decision 28): "every day <act>" is a daily reminder carrying the act, and
when it falls due the companion says one line a day from the notes."""

from __future__ import annotations

from datetime import datetime, timedelta

from tessellate.ai import commands, composer_voice, scheduled_acts

NOW = datetime(2026, 10, 31, 11, 30)
TODAY = NOW.date()


def _note(i, content, days_ago=1):
    return {"id": i, "content": content, "created_at": (TODAY - timedelta(days=days_ago)).isoformat(), "category": "", "tags": []}


def test_every_day_and_every_morning_act_is_a_daily_reminder():
    for phrase in ("every day list what is open", "every morning list what is open"):
        got = commands.read(phrase, NOW)
        assert got and got["intent"] == "reminder" and got["recurring"] == "daily" and got["said"] == "list what is open", phrase
    assert commands.read("every day is a good day", NOW) is None
    assert commands.read("every weekday review my inbox", NOW)["recurring"].startswith("FREQ=WEEKLY")


def _reminder(text="List what is open", recurring="daily", due=TODAY, rid=7):
    return {"id": rid, "text": text, "due_at": due.isoformat(), "done": False, "entry_id": None, "recurring": recurring}


NOTES = [_note(1, "# Todo\n\n- [ ] Book the dentist\n- [ ] Call the bank\n- [x] Pay rent")]


def test_a_due_act_reminder_is_answered_once_a_day_from_the_notes():
    got = [r for r in composer_voice.remarks(NOTES, today=TODAY, reminders=[_reminder()]) if r["kind"] == "scheduled_act"]
    assert len(got) == 1 and got[0]["text"].startswith("Your repeating reminder, “List what is open”: ")
    assert "two unticked checklist items are still open" in got[0]["text"].lower()
    #: Said in place of the plain due line, not beside it.
    assert not [r for r in composer_voice.remarks(NOTES, today=TODAY, reminders=[_reminder()]) if r["kind"] == "due"]
    again = [r for r in composer_voice.remarks(NOTES, today=TODAY, reminders=[_reminder()]) if r["kind"] == "scheduled_act"]
    assert again[0]["key"] == got[0]["key"], "the same day, the same key: the page says it once"
    tomorrow = [r for r in composer_voice.remarks(NOTES, today=TODAY + timedelta(days=1), reminders=[_reminder(due=TODAY + timedelta(days=1))]) if r["kind"] == "scheduled_act"]
    assert tomorrow and tomorrow[0]["key"] != got[0]["key"]


def test_a_plain_or_one_off_or_future_reminder_has_no_act_line():
    assert scheduled_acts.lines([_reminder("Call the bank")], NOTES, TODAY) == []
    assert scheduled_acts.lines([_reminder(recurring="none")], NOTES, TODAY) == []
    assert scheduled_acts.lines([_reminder(due=TODAY + timedelta(days=2))], NOTES, TODAY) == []
    assert scheduled_acts.lines([{**_reminder(), "done": True}], NOTES, TODAY) == []
