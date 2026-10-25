"""dog1 item 13: a reminder's day with no time is 09:00 and says so, an empty
Add and a missing day are said in the status line, and a far date is read as
weeks or a dated word, never "11/3/2026"."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_day_without_time_defaults_to_nine_and_says_so():
    text = (JS / "quickadd.js").read_text(encoding="utf-8")
    assert 'slots.time = "09:00";' in text and "slots.defaultTime = true" in text
    assert "No time was given, so it is set for 09:00." in text


def test_empty_add_and_missing_day_give_feedback():
    text = (JS / "quickadd.js").read_text(encoding="utf-8")
    assert "Type what to remind you of first" in text
    assert "status.textContent = qaMissing(qaFields.get(input));" in text


def test_far_dates_are_not_the_ambiguous_locale_short_form():
    text = (JS / "shell-reminders.js").read_text(encoding="utf-8")
    body = text[text.index("function relativeWhen"):text.index("function relativeWhen") + 1400]
    assert 'unit = "week"' in body and "when.toLocaleDateString()" not in body
