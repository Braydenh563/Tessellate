"""The owner's gym notes (INBOX 1767), as they were on Wednesday 11 November 2026: a routine written in July,
a Tuesday session in August, a line written "just now", a weekend note a week old (it says "now") and two
notes on conversation that are linked to it. Each row is
(content, category, tags, written, edited, links {index: reason})."""

from __future__ import annotations

NOW = "2026-11-11T10:30:00"

NOTES = [
    (
        "# Gym Routine Overview\n\nGo to the gym 4-5 days a week, depending on whether legs are skipped. Training usually takes place from "
        "9:10–9:30 PM at night, extending until around 10:45–11:30 PM on Sundays, Mondays, Tuesdays, Thursdays, and Fridays.\n\n"
        "The split follows this structure: Pull, Push, Legs, Rest Day, Pull, Push, Rest Day.",
        "Health", ["gym"], "2026-07-27T20:00:00", "2026-09-02T20:00:00", {1: "Shared Tuesday 9pm legs training", 4: "Both are about people and habits"},
    ),
    ("I go to gym at 9pm on tuesday for legs", "Health", ["gym"], "2026-08-03T21:00:00", "2026-08-03T21:00:00", {}),
    ("I've actually done legs the past two weeks for gym lol 😂", "Health", ["gym"], "2026-11-11T10:25:00", "2026-11-11T10:25:00", {}),
    (
        "Now I am spending the weekend relaxing and picking up gym properly again since I havent been much in the last couple weeks "
        "because of how busy with assignments I've been relaxing",
        "Personal", [], "2026-11-01T14:00:00", "2026-11-04T09:00:00", {},
    ),
    ("# The Complete Social Skills Guide\n\nHow to hold a conversation: ask open questions, listen, follow up.", "Personal", ["social"],
     "2026-10-05T12:00:00", "2026-10-05T12:00:00", {5: "Both give ways to start a conversation"}),
    ("# Ice Breakers\n\nTwo steps for a first chat: a question about their week, then a story of your own.", "Personal", ["social"],
     "2026-10-06T12:00:00", "2026-10-06T12:00:00", {}),
]
