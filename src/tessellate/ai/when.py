"""A time in the user's words, resolved to an instant by the app (INBOX 527).

AGENT_SKILLS_REFORM, "The harness does the work the model is worst at",
decided 2026-09-21: a tool argument is either intent, which only the model can
supply, or a fact the app can compute. "Remind me two hours before midnight" is
intent; `2026-09-21T22:00+10:00` is arithmetic, and the owner's transcript has
a model getting exactly that a day wrong. So `set_reminder` takes the phrase
and this module does the arithmetic, against the user's own clock, with no
model and no network.

What it reads, all case-insensitive and combinable ("next Friday at 3pm",
"tomorrow evening", "two hours before midnight"):

- an ISO date-time (the escape hatch a model with a real date can still use);
  without an offset it is the user's local time, never UTC;
- "in 20 minutes", "in half an hour", "in 3 days" (`reminder_parser`);
- N minutes/hours before or after another time ("before midnight");
- a day: today, tonight, tomorrow, the day after tomorrow, a weekday (this,
  on, next), next week, an ISO date, "5 October" or "October 5";
- a time: 9am, 9:30 pm, 21:00, "at 9", noon, midday, midnight, and the parts
  of a day (morning 9:00, afternoon 15:00, evening 18:00, night 20:00).

Rules a reader can argue with, written down so they are at least consistent:
a bare hour 1 to 6 is afternoon, 7 to 11 morning (tonight and evening make it
pm); a time with no day that has passed today is tomorrow; a day with no time
is 9:00; midnight belongs to the night of the day it is said with, so
"midnight" on its own is the coming one and "tomorrow at midnight" is the
night of tomorrow; "next Friday" is the Friday of next week, as in
`entry/timewords`; a weekday that is today, at a time already past, is next
week's. Returns None for anything it does not read, never a guess.

The reading itself lives in `ai/recognise.py` since CHAT_PLAN decision 46
(one recogniser suite): this module keeps its names and signatures for the
callers that use them, and reads nothing itself (`tests/test_one_reader.py`).
"""

from __future__ import annotations

from tessellate.ai.recognise import find, resolve, span, window
from tessellate.ai.recognise_questions import days_since
from tessellate.ai.recognise_reminders import parse_reminder_text

#: The names callers import from here; the re-export is deliberate (CodeQL reads an
#: unlisted re-export as an unused import).
__all__ = ["days_since", "find", "parse_reminder_text", "resolve", "span", "window"]
