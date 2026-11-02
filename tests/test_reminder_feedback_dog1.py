"""dog1 item 13: a reminder's day with no time is asked its time (CHAT_PLAN
decision 50: never guessed, so the 09:00 default dog1 asked for is not taken), an empty
Add and a missing day are said in the status line, and a far date is read as
weeks or a dated word, never "11/3/2026"."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_day_without_time_is_asked_not_defaulted():
    text = (JS / "quickadd.js").read_text(encoding="utf-8")
    assert 'slots.time = "09:00";' not in text and "defaultTime" not in text


def test_empty_add_and_missing_day_give_feedback():
    text = (JS / "quickadd.js").read_text(encoding="utf-8")
    assert "Type what to remind you of first" in text
    #: The missing day is asked once, in the chips' own status line (sweep 1028b W28), not again here.
    assert "The question is said once, in the chips' own status line" in text


def test_far_dates_are_not_the_ambiguous_locale_short_form():
    text = (JS / "shell-reminders.js").read_text(encoding="utf-8")
    body = text[text.index("function relativeWhen"):text.index("function relativeWhen") + 1400]
    assert '"week"' in body and "when.toLocaleDateString()" not in body
