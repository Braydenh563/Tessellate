"""Reminders magic add on hard phrasings (22-10 bug doc).

"remind me to do my tax return when I get home tonight, probably around 7pm"
failed: the title kept "when I get home , probably around" and the time came
out as 20:00 ("tonight") instead of 19:00. The table below is the phrasings a
person actually types: hedges ("probably", "around", "say"), a condition that
cannot be a clock ("when I get home"), a day part and a clock together, the
asking in front or behind. Read by rule, with no model, at a fixed clock:
Sunday 25 October 2026, 15:20.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from tessellate.ai import reminder_parser

NOW = datetime(2026, 10, 25, 15, 20)


def D(day: int, hour: int, minute: int = 0, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, minute)


CASES = [
    ("remind me to do my tax return when I get home tonight, probably around 7pm", "Do my tax return", D(25, 19)),
    ("remind me to call mum tomorrow at 9", "Call mum", D(26, 9)),
    ("remind me tonight at 7 to take the bins out", "Take the bins out", D(25, 19)),
    ("remind me to pay the electric bill on Friday around 5pm", "Pay the electric bill", D(30, 17)),
    ("remind me to water the plants this evening, maybe 6:30", "Water the plants", D(25, 18, 30)),
    ("tonight at about 8 remind me to ring the dentist", "Ring the dentist", D(25, 20)),
    ("remind me to email Sam in about 2 hours", "Email Sam", D(25, 17, 20)),
    ("remind me to book the car service on Monday at 10am", "Book the car service", D(26, 10)),
    ("don't let me forget to submit the form by 5pm tomorrow", "Submit the form", D(26, 17)),
    ("remind me to feed the cat when I'm home at around 6", "Feed the cat", D(25, 18)),
    ("remind me to join the meeting at 4pm", "Join the meeting", D(25, 16)),
    ("remind me to buy milk at 5:30pm", "Buy milk", D(25, 17, 30)),
    ("please remind me to stretch at half past 4", "Stretch", D(25, 16, 30)),
    ("remind me to call the bank on the 28th at 11am", "Call the bank", D(28, 11)),
    ("remind me to switch the oven off in 45 minutes", "Switch the oven off", D(25, 16, 5)),
    ("tomorrow, around noon, remind me to pick up the parcel", "Pick up the parcel", D(26, 12)),
    ("remind me to do laundry tonight, probably 9pm", "Do laundry", D(25, 21)),
    ("remind me to check the oven at 4", "Check the oven", D(25, 16)),
    ("remind me to walk the dog around 6 this evening", "Walk the dog", D(25, 18)),
    ("remind me to take out the recycling tonight when I get back, say 7:30pm", "Take out the recycling", D(25, 19, 30)),
    ("remind me to ring Ana later tonight, roughly 10pm", "Ring Ana", D(25, 22)),
    ("remind me to finish the report once I'm in tomorrow, about 9:30am", "Finish the report", D(26, 9, 30)),
    ("remind me to pack my bag tonight before bed, probably 8pm", "Pack my bag", D(25, 20)),
    ("remind me to send the invoice tomorrow morning at 8", "Send the invoice", D(26, 8)),
    ("remind me when I get home to take the washing out, around 6pm", "Take the washing out", D(25, 18)),
]


@pytest.mark.parametrize(("text", "title", "due"), CASES, ids=[c[0][:48] for c in CASES])
def test_magic_add_reads_the_hard_phrasing(text, title, due):
    parsed = reminder_parser.read_by_rule(text, NOW)
    assert parsed is not None, text
    assert parsed["text"] == title
    assert parsed["due_at"].replace(tzinfo=None) == due


def test_the_table_is_at_least_twenty_phrasings():
    assert len(CASES) >= 20


def test_a_condition_with_no_clock_still_gets_a_time_or_none():
    # "when I get home" alone names no time: the rules do not invent one.
    assert reminder_parser.read_by_rule("remind me to water the plants when I get home", NOW) is None


def test_the_plain_forms_still_read_as_before():
    parsed = reminder_parser.read_by_rule("remind me to call mum tomorrow at 9", NOW)
    assert parsed["priority"] == "normal"
    assert parsed["source"] == "rule"


def test_the_edit_form_controls_share_one_height_and_no_margin():
    """Measured at 1000px (scratchpad remform.js): the time input sat at
    top 323.75 and 32px high, the three selects at 324.5 and 36.9px, because
    `.inline-action input` kept its bottom margin and the shells were taller
    than the input (the opener was padded to 36.9px; it is now `--control-h`). Save and Cancel were already 32px with a 9.6px gap."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "frontend" / "css" / "02-chat-graph.css").read_text(encoding="utf-8")
    block = css.split(".inline-action .row > input {", 1)[1].split("}", 1)[0]
    assert "height: var(--control-h);" in css.split(".inline-action .select-opener {", 1)[1].split("}", 1)[0]
    assert "margin: 0;" in block
