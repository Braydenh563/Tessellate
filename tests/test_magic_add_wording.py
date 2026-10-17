"""Magic add, read and worded through the composer (O8; INBOX 904 B03, the
owner: "Use composer to refine magic add on reminders like with bad sentence
grammar and spelling mistakes and intent etc"). Measured 2026-10-17 on
/reminders/parse with no model, before: "remnd me to cal mum tmrw at 5pm"
was saved as "Remnd me to cal mum tmrw" due today (the day unread), "dont
forget to water the plants every sunday" as "Dont forget to water the
plants", "pay the rent friday plz" as "Pay the rent plz"."""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import reminder_parser


@pytest.mark.parametrize(
    ("typed", "text", "day"),
    [
        ("remnd me to cal mum tmrw at 5pm", "Call mum", 1),
        ("i need too buy milk tomorow morning", "Buy milk", 1),
        ("pay the rent friday plz", "Pay the rent", None),
        ("dentist appointmnt next tuesday 3pm", "Dentist appointment", None),
        ("remind me that i have to finish the essay by thursday", "Finish the essay", None),
        ("dont forget to water the plants every sunday", "Water the plants", None),
        ("ring Sarah abt the budget on mon", "Ring Sarah about the budget", None),
        ("call mum tomorrow evening", "Call mum", 1),
    ],
)
def test_magic_add_reads_the_slips_and_saves_the_task(client, typed, text, day):
    made = client.post("/reminders/parse", json={"text": typed, "tz_offset_minutes": 0})
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["text"] == text, body
    if day is not None:
        due = datetime.fromisoformat(body["due_at"].replace("Z", "+00:00"))
        assert (due.date() - datetime.now(due.tzinfo).date()).days == day, body["due_at"]


@pytest.mark.parametrize("kept", ["Call Sam", "Sam's birthday party", "Book the MOT for the Golf", "Renew passport"])
def test_a_reminder_that_is_already_a_task_is_kept(kept):
    assert reminder_parser.worded(kept) == kept
