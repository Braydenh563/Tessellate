"""L493: "every weekday", "every other friday" and "yearly" are read as a repeat
and saved once, as the rule itself, through the `Recurring` model of
`routes_reminders` (one row each, the repeat read back in words)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import reading

NOW = datetime(2026, 10, 7, 10, 0)  # fixed clock for the reading
CASES = [
    ("bins every weekday at 9am", "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", "every weekday"),
    ("gym every other friday at 7am", "FREQ=WEEKLY;INTERVAL=2;BYDAY=FR", "every other Friday"),
    ("renew the passport yearly on 3 march at 9am", "FREQ=YEARLY", "every year"),
]


@pytest.mark.parametrize(("text", "rule", "words"), CASES)
def test_a_repeat_is_read_and_saved_once_as_its_rule(client, text, rule, words):
    got = reading.read(text, now=NOW, context={"surface": "reminder"})
    assert got.slots["recurring"] == rule
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    headers = {"X-Auth-Token": token}
    due = (datetime.now(timezone.utc) + timedelta(days=2)).replace(tzinfo=None).isoformat()
    made = client.post("/reminders", json={"text": got.slots["text"], "due_at": due, "recurring": got.slots["recurring"]}, headers=headers)
    assert made.status_code in (200, 201), made.text
    rows = client.get("/reminders", headers=headers).json()
    assert len(rows) == 1 and rows[0]["recurring"] == rule and rows[0]["repeat_words"] == words, rows
