"""`ai/when.py`: a reminder's time in the user's words, resolved by the app
(AGENT_SKILLS_REFORM, decided 2026-09-21; built for INBOX 527).

The gate the plan set: the shapes people use, resolved with no model at all.
The clock is the owner's transcript: Monday 21 September 2026, 15:55, UTC+10,
where a model put "two hours before midnight" on the 22nd.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tessellate.ai import when

NOW = datetime(2026, 9, 21, 15, 55, tzinfo=ZoneInfo("Australia/Brisbane"))


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("two hours before midnight", "2026-09-21 22:00"),
        ("midnight", "2026-09-22 00:00"),
        ("tomorrow at midnight", "2026-09-23 00:00"),
        ("in 10 minutes", "2026-09-21 16:05"),
        ("in half an hour", "2026-09-21 16:25"),
        ("tomorrow at 9am", "2026-09-22 09:00"),
        ("tomorrow at 9", "2026-09-22 09:00"),
        ("tomorrow at 3", "2026-09-22 15:00"),
        ("tomorrow morning", "2026-09-22 09:00"),
        ("tomorrow", "2026-09-22 09:00"),
        ("tonight", "2026-09-21 20:00"),
        ("tonight at 9", "2026-09-21 21:00"),
        ("this evening", "2026-09-21 18:00"),
        ("at 8pm", "2026-09-21 20:00"),
        ("8:30 pm", "2026-09-21 20:30"),
        ("21:15", "2026-09-21 21:15"),
        ("at 9", "2026-09-21 21:00"),
        ("at 10am", "2026-09-22 10:00"),
        ("noon", "2026-09-22 12:00"),
        ("Friday night", "2026-09-25 20:00"),
        ("on Friday at 3pm", "2026-09-25 15:00"),
        ("next Friday", "2026-10-02 09:00"),
        ("Monday at 9am", "2026-09-28 09:00"),
        ("next week", "2026-09-28 09:00"),
        ("the day after tomorrow at 7:30am", "2026-09-23 07:30"),
        ("5 October at 2pm", "2026-10-05 14:00"),
        ("October 5th", "2026-10-05 09:00"),
        ("30 minutes before 6pm", "2026-09-21 17:30"),
        ("2026-09-30T09:00", "2026-09-30 09:00"),
        ("2026-09-30", "2026-09-30 09:00"),
    ],
)
def test_the_shapes_people_use(phrase, expected):
    got = when.resolve(phrase, NOW)
    assert got is not None, phrase
    assert got.tzinfo is not None, "always an aware instant"
    assert got.astimezone(NOW.tzinfo).strftime("%Y-%m-%d %H:%M") == expected, phrase


def test_an_iso_time_without_an_offset_is_the_users_clock_not_utc():
    got = when.resolve("2026-09-30T09:00", NOW)
    assert got.utcoffset().total_seconds() == 10 * 3600


@pytest.mark.parametrize("phrase", ["", "whenever", "soon-ish", "the plumber"])
def test_what_it_does_not_read_is_none_never_a_guess(phrase):
    assert when.resolve(phrase, NOW) is None


# --- set_reminder, the tool that takes the words --------------------------------


def _tool(session, **args):
    from tessellate.ai import tools

    return tools.execute_tool(session, "set_reminder", {"text": "call the dentist", **args})


def test_the_tool_takes_the_users_words_with_no_model(app_state, session, monkeypatch):
    """The plan's gate: a fake model that passes only the phrase, no model
    reachable, and the instant is right."""
    from tessellate.ai import tools
    from tessellate.core.database import Reminder

    monkeypatch.setattr("tessellate.core.config.user_now", lambda config: NOW)
    result = _tool(session, when="two hours before midnight")
    assert "error" not in result, result
    stored = session.get(Reminder, result["id"]).due_at
    assert stored.astimezone(NOW.tzinfo).strftime("%Y-%m-%d %H:%M") == "2026-09-21 22:00"
    assert result["due"] == "Monday 21 September 2026, 22:00"
    assert "when" in tools.TOOLS["set_reminder"].parameters["properties"]


def test_an_iso_time_without_an_offset_is_stored_as_the_users_time(app_state, session, monkeypatch):
    """Measured before: "2026-10-05T09:00" was stored as 09:00 UTC, which is
    19:00 for a user at UTC+10."""
    from tessellate.core.database import Reminder

    monkeypatch.setattr("tessellate.core.config.user_now", lambda config: NOW)
    result = _tool(session, due_at="2026-10-05T09:00")
    stored = session.get(Reminder, result["id"]).due_at
    assert stored.astimezone(NOW.tzinfo).strftime("%Y-%m-%d %H:%M") == "2026-10-05 09:00"


def test_a_time_already_past_or_unreadable_is_refused_with_a_reason(app_state, session, monkeypatch):
    monkeypatch.setattr("tessellate.core.config.user_now", lambda config: NOW)
    assert "already passed" in _tool(session, due_at="2026-09-20T09:00")["error"]
    assert "Couldn't read 'whenever'" in _tool(session, when="whenever")["error"]
    assert "`when`" in _tool(session)["error"]


# --- a window in the past, in the user's words (AGENT_SKILLS_REFORM, the audit) ---
#
# `list_notes`, `count_notes` and `summarize_notes` took "the last N days, or
# an ISO date": a model asked about "this week" had to work out the date,
# which is the arithmetic the 2026-09-21 decision took away from it. NOW is
# Monday 21 September 2026.


@pytest.mark.parametrize(
    "phrase, days",
    [
        ("today", 0),
        ("yesterday", 1),
        ("this week", 0),
        ("last week", 7),
        ("the past week", 7),
        ("since Friday", 3),
        ("since last Monday", 7),
        ("this month", 20),
        ("last month", 51),
        ("this year", 263),
        ("3 days ago", 3),
        ("the last 30 days", 30),
        ("past two weeks", 14),
        ("last 2 months", 62),
        ("1 September", 20),
        ("since September 1st", 20),
        ("2026-09-01", 20),
        ("14", 14),
    ],
)
def test_a_window_in_the_users_words_is_counted_in_days(phrase, days):
    assert when.days_since(phrase, NOW) == days


@pytest.mark.parametrize("phrase", ["", "whenever", "next week", "tomorrow"])
def test_a_phrase_that_names_no_past_window_reads_as_none(phrase):
    assert when.days_since(phrase, NOW) is None


def test_the_list_tools_take_since_in_words(app_state, session, monkeypatch):
    from tessellate.ai import tools
    from tessellate.ai.tools import _common

    monkeypatch.setattr("tessellate.core.config.user_now", lambda config: NOW)
    assert _common._since_days("this month") == 20
    assert _common._since_days("7") == 7
    assert _common._since_days("whenever") is None
    spec = tools.TOOLS["list_notes"].parameters["properties"]["since"]["description"]
    assert "this week" in spec


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("half past 4", "2026-09-21 16:30"),
        ("at half past four", "2026-09-21 16:30"),
        ("quarter to 5", "2026-09-21 16:45"),
        ("a quarter past 6pm", "2026-09-21 18:15"),
        ("ten to nine tomorrow", "2026-09-22 08:50"),
        ("twenty past 4", "2026-09-21 16:20"),
        ("5 past 5 on friday", "2026-09-25 17:05"),
        ("half past 12 tomorrow", "2026-09-22 12:30"),
        ("quarter to 1 tomorrow", "2026-09-22 12:45"),
    ],
)
def test_a_clock_said_in_words_resolves(phrase, expected):
    """"Half past four", "quarter to five": how people say a time aloud,
    which neither time reader knew (the digits-only clock read "half past 4"
    as no time at all and asked "Remind you when?")."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected


def test_a_reminder_keeps_its_words_around_a_spoken_clock():
    got = when.parse_reminder_text("call mum at half past 4", NOW)
    assert got["due_at"].strftime("%H:%M") == "16:30"
    assert got["text"].lower().startswith("call mum")
    assert "half" not in got["text"].lower() and "past" not in got["text"].lower()


@pytest.mark.parametrize("phrase", ["half past", "past 4", "quarter to", "the 5 to 7 train", "open from ten to five"])
def test_words_that_are_not_a_clock_stay_unread(phrase):
    assert when.resolve(phrase, NOW) is None


def test_a_repeat_keeps_its_rule_when_the_clock_is_said_aloud():
    """"Every day at half past 7" read as one 19:30 reminder: the repeat was
    dropped because only the digits clock followed it."""
    from tessellate.ai import recognise

    rules = {
        span.value
        for text in ("every day at half past 7", "every monday at quarter to 9")
        for span in recognise.recognise(text, now=NOW.replace(tzinfo=None))
        if span.kind == "recurrence"
    }
    assert rules == {"FREQ=DAILY;BYHOUR=7;BYMINUTE=30", "FREQ=WEEKLY;BYDAY=MO;BYHOUR=8;BYMINUTE=45"}


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("the first monday of november", "2026-11-02 09:00"),
        ("third friday of october", "2026-10-16 09:00"),
        ("the last friday of next month", "2026-10-30 09:00"),
        ("the second tuesday of september", "2027-09-14 09:00"),
        ("first monday of november at 2pm", "2026-11-02 14:00"),
    ],
)
def test_a_weekdays_place_in_a_month_is_that_day(phrase, expected):
    """"The first Monday of November" read as the next Monday (28 September):
    the weekday was found and the month and the place were ignored."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected


def test_a_note_about_the_past_reads_the_month_gone():
    from datetime import date

    from tessellate.ai import recognise

    assert recognise.span("the first monday of march", date(2026, 9, 21), "past") == (date(2026, 3, 2),) * 2 + ("day",)
    assert recognise.span("the first monday of march", date(2026, 9, 21), "future") == (date(2027, 3, 1),) * 2 + ("day",)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("the last day of this month", "2026-09-30 09:00"),
        ("last day of next month", "2026-10-31 09:00"),
        ("first day of march", "2027-03-01 09:00"),
        ("next month on the 3rd", "2026-10-03 09:00"),
        ("the 3rd of next month", "2026-10-03 09:00"),
    ],
)
def test_a_day_named_by_its_month_is_that_day(phrase, expected):
    """"The last day of this month" read as 1 September, "next month on the
    3rd" as 1 October: the month was read and the day ignored."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected, phrase


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("a week from friday", "2026-10-02 09:00"),
        ("two days from today", "2026-09-23 09:00"),
        ("a week from today", "2026-09-28 09:00"),
        ("30 minutes from now", "2026-09-21 16:25"),
        ("half an hour from now", "2026-09-21 16:25"),
        ("2 hours from now", "2026-09-21 17:55"),
    ],
)
def test_an_offset_from_a_day_or_from_now_is_read(phrase, expected):
    """"A week from Friday" read as Friday and "30 minutes from now" was
    unread: only "in 30 minutes" counted as an offset."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.astimezone(NOW.tzinfo).strftime("%Y-%m-%d %H:%M") == expected, phrase


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("3 o'clock", "2026-09-22 15:00"),
        ("tomorrow at 3 o'clock", "2026-09-22 15:00"),
        ("9 oclock", "2026-09-21 21:00"),
        ("friday at three", "2026-09-25 15:00"),
        ("at nine", "2026-09-21 21:00"),
        ("tomorrow at nine", "2026-09-22 09:00"),
        ("at ten thirty", "2026-09-21 22:30"),
        ("tomorrow at ten thirty", "2026-09-22 10:30"),
        ("tomorrow at three thirty pm", "2026-09-22 15:30"),
        ("tomorrow at eleven forty-five am", "2026-09-22 11:45"),
        ("tomorrow at 1530", "2026-09-22 15:30"),
        ("at 1630", "2026-09-21 16:30"),
        ("tomorrow at 0330", "2026-09-22 03:30"),
        ("tomorrow at 1030", "2026-09-22 10:30"),
        ("tomorrow at 15h30", "2026-09-22 15:30"),
        ("at 16h30", "2026-09-21 16:30"),
        ("friday at 0900 hours", "2026-09-25 09:00"),
    ],
)
def test_a_clock_in_words_or_24_hour_figures_resolves(phrase, expected):
    """"3 o'clock", "at three", "at ten thirty", "at 1530", "at 15h30" were
    unread and asked "Remind you when?". The 12-hour forms keep the bare-hour
    rule (3 is afternoon, 9 the next nine); the figure forms (1530, 15h30,
    0330) are 24-hour notation, so their hour is never guessed."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected, phrase


@pytest.mark.parametrize(
    "phrase",
    ["at one point", "at three of them", "at three people", "at 2561", "at 2460", "at 15h75", "at 153", "o'clock", "the 1530 train"],
)
def test_words_that_only_look_like_a_clock_stay_unread(phrase):
    assert when.resolve(phrase, NOW) is None, phrase


@pytest.mark.parametrize(("locale", "expected"), [("en-US", "2027-02-11 15:30"), ("en-AU", "2026-11-02 15:30")])
def test_a_24_hour_clock_beside_a_numeric_date_follows_the_locale_date_order(locale, expected):
    """The clock is the same in every locale; only the day order moves."""
    got = when.resolve("2/11 at 1530", NOW, locale=locale)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected


def test_a_reminder_keeps_its_words_around_a_clock_in_words():
    for sentence, due, task in (
        ("call mum at three", "15:00", "Call mum"),
        ("pay rent tomorrow at 15h30", "15:30", "Pay rent"),
        ("feed the cat at 1630", "16:30", "Feed the cat"),
        ("lock up at ten thirty", "22:30", "Lock up"),
        ("be home by 9 o'clock", "21:00", "Be home"),
    ):
        got = when.parse_reminder_text(sentence, NOW)
        assert got is not None, sentence
        assert got["due_at"].strftime("%H:%M") == due and got["text"] == task, (sentence, got)


def test_the_owners_typos_in_a_clock_are_put_right_before_it_is_read():
    """"thre", "thrity", "oclock", "tmrw": heard() repairs the spelling, then
    the one reader reads the clock."""
    from tessellate.ai import reminder_parser

    for typed, due in (
        ("cal mum tmrw at thre oclock", "2026-09-22 15:00"),
        ("remnd me tmrw at ten thrity to feed the cat", "2026-09-22 10:30"),
        ("pay the rent tomorow at 1530 plz", "2026-09-22 15:30"),
    ):
        got = when.parse_reminder_text(reminder_parser.heard(typed), NOW)
        assert got is not None and got["due_at"].strftime("%Y-%m-%d %H:%M") == due, (typed, got)


def test_a_repeat_keeps_its_rule_when_the_clock_is_in_words_or_figures():
    from tessellate.ai import recognise

    rules = {
        span.value
        for text in ("every day at three", "every monday at 1530", "every friday at 15h30", "every day at ten thirty")
        for span in recognise.recognise(text, now=NOW.replace(tzinfo=None))
        if span.kind == "recurrence"
    }
    assert rules == {
        "FREQ=DAILY;BYHOUR=15;BYMINUTE=0",
        "FREQ=WEEKLY;BYDAY=MO;BYHOUR=15;BYMINUTE=30",
        "FREQ=WEEKLY;BYDAY=FR;BYHOUR=15;BYMINUTE=30",
        "FREQ=DAILY;BYHOUR=10;BYMINUTE=30",
    }


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("in 1h30", "2026-09-21 17:25"),
        ("in 1h30m", "2026-09-21 17:25"),
        ("in 2h", "2026-09-21 17:55"),
        ("in 1.5h", "2026-09-21 17:25"),
        ("in 1 hour 30 minutes", "2026-09-21 17:25"),
        ("in 1 hour and 30 minutes", "2026-09-21 17:25"),
        ("in two hours 15 mins", "2026-09-21 18:10"),
        ("in an hour and 20 minutes", "2026-09-21 17:15"),
        ("in 2 hours", "2026-09-21 17:55"),
        ("in 90 mins", "2026-09-21 17:25"),
    ],
)
def test_an_hours_and_minutes_offset_is_read_whole(phrase, expected):
    """"In 1h30" was unread, and "in 1 hour 30 minutes" read as one hour with
    the half hour left in the reminder's text."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected, phrase


def test_an_hours_and_minutes_offset_leaves_the_reminders_words_alone():
    for sentence, due, task in (
        ("take the bread out in 1h30", "17:25", "Take the bread out"),
        ("remind me in 1 hour 30 minutes to call mum", "17:25", "Call mum"),
        ("check the oven in 2h", "17:55", "Check the oven"),
    ):
        got = when.parse_reminder_text(sentence, NOW)
        assert got is not None, sentence
        assert got["due_at"].strftime("%H:%M") == due and got["text"] == task, (sentence, got)


@pytest.mark.parametrize("phrase", ["in 2 hot dogs", "in 1h75", "in h30", "1h30"])
def test_words_that_only_look_like_an_offset_stay_unread(phrase):
    assert when.resolve(phrase, NOW) is None, phrase


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("eod", "2026-09-21 17:00"),
        ("by eod", "2026-09-21 17:00"),
        ("end of day", "2026-09-21 17:00"),
        ("eod tomorrow", "2026-09-22 17:00"),
        ("by end of the day friday", "2026-09-25 17:00"),
    ],
)
def test_end_of_day_is_five_in_the_afternoon(phrase, expected):
    """"eod" was unread. The rule is the existing one for "end of day": 17:00,
    on the day named, else today."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected, phrase


def test_end_of_day_said_after_five_is_the_next_one():
    late = NOW.replace(hour=18, minute=30)
    got = when.resolve("eod", late)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == "2026-09-22 17:00"


def test_a_reminder_keeps_its_words_around_eod_even_misspelt():
    from tessellate.ai import reminder_parser

    for sentence, due, task in (
        ("send the report eod", "2026-09-21 17:00", "Send the report"),
        ("send the report by eod tomorrow", "2026-09-22 17:00", "Send the report"),
        (reminder_parser.heard("sned the repot by eod tmrw plz"), "2026-09-22 17:00", "Send the report"),
    ):
        got = when.parse_reminder_text(sentence, NOW)
        assert got is not None, sentence
        assert got["due_at"].strftime("%Y-%m-%d %H:%M") == due, (sentence, got)
        assert got["text"].lower().startswith(task.lower()[:9]), (sentence, got)


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("in two weeks on wednesday", "2026-10-07 09:00"),
        ("in 2 weeks wednesday", "2026-10-07 09:00"),
        ("in two weeks, on wednesday at 3pm", "2026-10-07 15:00"),
        ("in a week on friday", "2026-10-02 09:00"),
        ("in a fortnight on friday", "2026-10-09 09:00"),
        ("in 3 weeks on monday", "2026-10-12 09:00"),
        ("in two weeks on monday", "2026-10-05 09:00"),
        ("in two weeks on sunday", "2026-10-11 09:00"),
        ("in two weeks", "2026-10-05 15:55"),
    ],
)
def test_a_weekday_named_after_a_week_offset_is_that_weekday_of_that_week(phrase, expected):
    """"In two weeks on wednesday" read 5 October 15:55: the weekday was
    dropped. Decided, to match "next friday" (the Friday of next week, in
    `_day` and `span`): weeks are Monday to Sunday, "in N weeks" is the week
    N weeks on, and the weekday is its day there. So "in a week on friday" is
    "next friday", and said on a Friday, "in two weeks on wednesday" is the
    Wednesday before the mark two weeks out, never the one after it."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected, phrase


def test_a_week_offset_weekday_is_by_calendar_week_not_by_day_count():
    friday = datetime(2026, 9, 25, 10, 0, tzinfo=NOW.tzinfo)
    got = when.resolve("in two weeks on wednesday", friday)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == "2026-10-07 09:00"
    assert when.resolve("in a week on friday", friday) == when.resolve("next friday", friday)


def test_a_reminder_keeps_its_words_around_a_week_offset_and_a_weekday():
    got = when.parse_reminder_text("dentist in two weeks on wednesday", NOW)
    assert got is not None and got["text"] == "Dentist"
    assert got["due_at"].strftime("%Y-%m-%d %H:%M") == "2026-10-07 09:00"

    from tessellate.ai import reminder_parser

    typed = when.parse_reminder_text(reminder_parser.heard("dentst in 2 wks on wensday at 3pm"), NOW)
    assert typed is not None and typed["due_at"].strftime("%Y-%m-%d %H:%M") == "2026-10-07 15:00"
    assert typed["text"] == "Dentist"


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("midnight", "2026-09-22 00:00"),
        ("at midnight", "2026-09-22 00:00"),
        ("midnight tonight", "2026-09-22 00:00"),
        ("tomorrow at midnight", "2026-09-23 00:00"),
        ("midnight on 5 october", "2026-10-06 00:00"),
        ("midnight on new year's eve", "2027-01-01 00:00"),
        ("midnight at new year", "2027-01-01 00:00"),
        ("new year at midnight", "2027-01-01 00:00"),
        ("midnight on new years eve", "2027-01-01 00:00"),
    ],
)
def test_midnight_is_the_next_one_unless_the_phrase_names_the_new_year(phrase, expected):
    """"Remind me at midnight to see the new year" read 2 January: midnight
    belongs to the night of the day it is said with (so "midnight on 5
    october" is the turn into the 6th), and "new year" is 1 January, which put
    it a night late. Decided: midnight alone is tonight's, the next one; a date
    keeps that rule; "new year" (not "new year's eve" or "new year's day", which
    name their day and follow the rule) is the midnight that opens the year."""
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected, phrase


def test_midnight_said_just_after_midnight_is_the_next_one():
    after = NOW.replace(day=22, hour=0, minute=20)
    got = when.resolve("at midnight", after)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == "2026-09-23 00:00"


def test_the_new_year_is_the_thing_to_do_not_the_time_in_a_reminder():
    got = when.parse_reminder_text("remind me at midnight to see the new year", NOW)
    assert got is not None
    assert got["due_at"].strftime("%Y-%m-%d %H:%M") == "2027-01-01 00:00"
    assert got["text"] == "See the new year"
    plain = when.parse_reminder_text("remind me at midnight to lock up", NOW)
    assert plain is not None and plain["due_at"].strftime("%Y-%m-%d %H:%M") == "2026-09-22 00:00"
    assert plain["text"] == "Lock up"
    dated = when.parse_reminder_text("call nan on new year's day at 9am", NOW)
    assert dated is not None and dated["text"] == "Call nan"


def test_the_owners_typos_around_midnight_and_the_new_year_are_put_right_first():
    from tessellate.ai import reminder_parser

    got = when.parse_reminder_text(reminder_parser.heard("remnd me at midnite to see the new yaer"), NOW)
    assert got is not None and got["due_at"].strftime("%Y-%m-%d %H:%M") == "2027-01-01 00:00", got


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("in 2 weeks at 3pm", "2026-10-05 15:00"),
        ("in 3 days at 9am", "2026-09-24 09:00"),
        ("in 3 days at 3", "2026-09-24 15:00"),
        ("in a fortnight at noon", "2026-10-05 12:00"),
        ("in 2 months at 9am", "2026-11-21 09:00"),
        ("in 2 days evening", "2026-09-23 18:00"),
        ("in 2 days", "2026-09-23 15:55"),
        ("in 2 hours", "2026-09-21 17:55"),
    ],
)
def test_a_day_sized_offset_keeps_the_clock_said_beside_it(phrase, expected):
    got = when.resolve(phrase, NOW)
    assert got is not None and got.strftime("%Y-%m-%d %H:%M") == expected
