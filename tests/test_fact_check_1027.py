"""The check on a model's words in a facts turn (`ai/fact_check.py`,
`routes_chat._fact_events`), from the second review of 2026-10-27: each case
here was a miscount the check kept, or a right answer it refused, measured
through `/chat/stream` with a fake model and a fixed clock.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from tessellate.ai import fact_check
from tessellate.api import routes_chat
from tessellate.core.database import Entry, Reminder

#: A fixed clock (CLAUDE.md section 8), Tuesday 27 October 2026, 9:30.
NOW = datetime(2026, 10, 27, 9, 30)


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    monkeypatch.setattr(routes_chat, "user_now", lambda _config=None: NOW)


def _seed(session, last=datetime(2026, 11, 20, 11)) -> None:
    """Three reminders: two this week, the third `last`."""
    for text, due in (("call mum", datetime(2026, 10, 28, 9)), ("pay rent", datetime(2026, 10, 29, 10)), ("book dentist", last)):
        session.add(Reminder(text=text, due_at=due))
    session.commit()


def _kept(client, fake, question: str, prose: str, use_tools: bool = False) -> bool:
    """Whether the model's words were kept: they lead the answer and the
    latest `meta` names the model."""
    fake.librarian_reply = prose
    events = []
    with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": use_tools}) as response:
        for line in response.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    assert fake.chat_calls, "the model was never asked"
    answer = "".join(e.get("delta", "") for e in events if e["type"] == "answer")
    meta = [e for e in events if e["type"] == "meta"][-1]
    return answer.startswith(prose) and bool(meta["answered_by"])


SURFACES = pytest.mark.parametrize("use_tools", [False, True], ids=["chat", "popup-agent"])


@SURFACES
@pytest.mark.parametrize(
    ("question", "prose", "ok"),
    [
        ("what reminders do I have this week", "You have 3 reminders this week.", False),
        ("what reminders do I have this week", "You have 2 reminders this week.", True),
        ("what reminders do I have today", "You have 3 reminders today.", False),
        ("what reminders do I have today", "You have no reminders today.", True),
        # The third review: "tomorrow" and "next week" were no windows, so the
        # whole list's 3 stood. Only call mum is due tomorrow; none next week.
        ("what reminders do I have tomorrow", "You have 3 reminders tomorrow.", False),
        ("what reminders do I have tomorrow", "You have 1 reminder tomorrow.", True),
        ("what reminders do I have next week", "You have 3 reminders next week.", False),
        ("what reminders do I have next week", "You have no reminders next week.", True),
        ("what reminders do I have on thursday", "You have 3 reminders on Thursday.", False),
        ("what reminders do I have on thursday", "You have 1 reminder on Thursday.", True),
        ("what reminders do I have in the next 3 days", "You have 3 reminders in the next 3 days.", False),
        ("what reminders do I have in the next 3 days", "You have 2 reminders in the next 3 days.", True),
        ("what reminders do I have next month", "You have 3 reminders next month.", False),
        ("what reminders do I have next month", "You have 1 reminder next month.", True),
    ],
)
def test_a_windowed_list_is_checked_against_the_window(ai_client, fake_ollama, session, question, prose, ok, use_tools):
    """The counts were the whole list's (3) while the engine said the week's (2)."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, question, prose, use_tools) is ok


@pytest.mark.parametrize(
    ("question", "prose", "ok"),
    [
        ("how many minutes in 2 hours", "That is 130 minutes.", False),
        ("how many minutes in 2 hours", "That is 120 minutes.", True),
        ("how many minutes in 2 hours", "That is 2 hours.", False),
        ("how many days until christmas", "There are 90 days until Christmas.", False),
        ("how many days until christmas", "There are 59 days until Christmas.", True),
        ("how many days until christmas", "Christmas is about 8 weeks away.", True),
        ("convert 3 hours to minutes", "That's 200 minutes.", False),
        ("convert 3 hours to minutes", "That's 180 minutes.", True),
        ("how many weeks until 1 january", "That is 20 weeks.", False),
        ("how many weeks until 1 january", "That is about 9 weeks.", True),
        ("how many seconds in a day", "A day is 86,400 seconds.", True),
        ("how many seconds in a day", "A day is 86,000 seconds.", False),
    ],
)
def test_a_span_the_engine_computed_is_checked(ai_client, fake_ollama, session, question, prose, ok):
    """A figure before a time unit was never read, so any span stood."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, question, prose) is ok


@pytest.mark.parametrize(
    ("question", "prose", "ok"),
    [
        # The third review: right spans said another way, and a wrong one the
        # ceil let through.
        ("how many days until christmas", "Christmas is 8 weeks and 3 days away.", True),
        ("how many days until christmas", "Christmas is 1 month and 29 days away.", True),
        ("how many days until christmas", "Christmas is roughly 60 days away.", True),
        ("how many days until christmas", "Christmas is almost 60 days away.", True),
        ("how many days until christmas", "Christmas is 1 year away.", False),
        ("how many days until christmas", "Christmas is 1 month away.", False),
        ("how many days until christmas", "Christmas is about 3 months away.", False),
        ("how many days until christmas", "Christmas is 65 days away.", False),
        ("how many days until christmas", "Christmas is 8 weeks and 6 days away.", False),
        ("convert 2.5 hours to minutes", "That is 150 minutes, or 2 hours 30 minutes.", True),
        ("convert 2.5 hours to minutes", "That is 150 minutes, or 2 hours 45 minutes.", False),
    ],
)
def test_a_span_said_another_way_is_checked_with_a_tolerance(ai_client, fake_ollama, session, question, prose, ok):
    _seed(session)
    assert _kept(ai_client, fake_ollama, question, prose) is ok


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("You have 3 reminders; pay rent is in 2 days.", True),
        ("You have 3 reminders; call mum is in 1 day.", True),
        ("You have 3 reminders; book dentist is in 3 weeks.", True),
        ("You have 3 reminders; book dentist is in about 24 days.", True),
        ("You have 3 reminders; pay rent is in 5 days.", False),
        ("You have 3 reminders; book dentist is in 3 months.", False),
        ("You have 3 reminders; the oldest was last edited 400 days ago.", False),
    ],
)
def test_a_span_the_facts_do_not_state_is_checked_against_their_dates(ai_client, fake_ollama, session, prose, ok, use_tools):
    """"last edited 400 days ago" stood because the facts held no span; now a
    span is read against the dates the facts carry, and refused with none."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


def test_a_span_with_no_dates_in_the_facts_is_refused(ai_client, fake_ollama, session):
    session.add(Entry(content="Gym plan"))
    session.commit()
    assert not _kept(ai_client, fake_ollama, "how many notes do I have", "You have 1 note, last edited 400 days ago.")
    assert _kept(ai_client, fake_ollama, "how many notes do I have", "You have 1 note.")


@SURFACES
def test_a_span_the_engine_did_not_compute_is_the_models(ai_client, fake_ollama, session, use_tools):
    """Under a list of dated reminders, "in 2 days" is the model's reading."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", "You have 3 reminders; pay rent is in 2 days.", use_tools)


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("Only one is waiting.", False),
        ("One is due soon.", False),
        ("You have 3 reminders. One of them, call mum, is due tomorrow.", True),
        ("You have 3 reminders; the first one is call mum.", True),
        # The third review: a modifier between the determiner and "one".
        ("You have 3 reminders; the urgent one is call mum.", True),
        ("You have 3 reminders; the dentist one is tomorrow.", True),
        ("You have 3 reminders; the rent one is the biggest.", True),
        ("You have 3 reminders; no one is overdue.", True),
        ("You have 3 reminders; your dentist one is tomorrow.", True),
        ("You have 3 reminders; only one is overdue.", False),
        ("You have 3 reminders; just one is overdue.", False),
        ("You have 3 reminders; the rest are fine and one is overdue.", False),
    ],
)
def test_a_bare_one_counts_unless_it_points(ai_client, fake_ollama, session, prose, ok, use_tools):
    """A bare "one" always stood, so "Only one is waiting" passed with 3."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("You have a couple of reminders.", False),
        ("You have a dozen reminders.", False),
        ("You have a hundred reminders.", False),
        ("You have two dozen reminders.", False),
        ("You have three reminders.", True),
    ],
)
def test_an_amount_said_in_words_is_a_figure(ai_client, fake_ollama, session, prose, ok, use_tools):
    """"a couple of", "a dozen" and "a hundred" passed with 3."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@SURFACES
@pytest.mark.parametrize(
    "prose",
    [
        "Call mum is due October 28, 2026; you have 3 reminders.",
        "You have 3 reminders; pay rent is due Thursday by 10.",
        "You have 3 reminders; call mum is due by 9.30 tomorrow.",
        "Call mum is due 2026-10-28; you have 3 reminders.",
    ],
)
def test_a_year_a_time_and_an_iso_date_are_no_figures(ai_client, fake_ollama, session, prose, use_tools):
    """Each was refused for a figure that counts nothing."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools)


@pytest.mark.parametrize(("notes", "prose", "ok"), [(1, "You have a single note.", True), (2, "You have a single note.", False)])
def test_a_single_note_is_one(ai_client, fake_ollama, session, notes, prose, ok):
    for n in range(notes):
        session.add(Entry(content=f"Gym plan {n}"))
    session.commit()
    assert _kept(ai_client, fake_ollama, "how many notes do I have", prose) is ok


def test_only_a_breakdown_counts_inside_a_nested_dict():
    """Any int in a nested dict was a count of notes, so a filter's limit
    of 10 excused "10 notes"."""
    assert fact_check.result_counts("search_notes", {"filters": {"limit": 10}, "notes": [{"id": 1}, {"id": 2}]}) == {"note": {"2"}}
    assert fact_check.result_counts("count_notes", {"total": 5, "by_category": {"Work": 3, "Home": 2}}) == {"note": {"5", "3", "2"}}



@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        # The third review: a figure after by/after/until/around that is no
        # time of the facts is a figure like any other.
        ("You have 3 reminders, up by 5.", False),
        ("You have 3 reminders; pay rent is due after 4.", False),
        ("You have 3 reminders; call mum is due until 7.", False),
        ("You have 3 reminders; pay rent is due Thursday by 10.", True),
        ("You have 3 reminders; call mum is due by 9.30 tomorrow.", True),
        ("You have 3 reminders; call mum is due around 9 tomorrow.", True),
        # A range is two figures, each checked.
        ("You have 10-12 reminders.", False),
        ("You have 2-3 reminders.", False),
        ("You have 3 reminders; call mum is due 9-10am.", True),
        # A year counts nothing only where it is a year.
        ("You have 3 reminders, up from 2000.", False),
        ("You have 3 reminders; call mum is due on 28 October 2026.", True),
        ("You have 3 reminders; call mum is due October 28, 2026.", True),
        ("You have 3 reminders; the dentist is due in 2026.", True),
    ],
)
def test_a_figure_after_by_a_range_and_a_year_are_verified(ai_client, fake_ollama, session, prose, ok, use_tools):
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@pytest.mark.parametrize(
    ("prose", "facts", "counts", "ok"),
    [
        ("Not a single one is tagged.", "You have 0 tagged notes.", {"note": {"0"}}, True),
        ("Not a single one is tagged.", "You have 3 tagged notes.", {"note": {"3"}}, False),
        ("Not a single note is tagged.", "You have 0 tagged notes.", {"note": {"0"}}, True),
        ("Only a single note, nothing else.", "You have 1 note.", {"note": {"1"}}, True),
        ("Only a single note, nothing else.", "You have 2 notes.", {"note": {"2"}}, False),
        ("A single note and nothing more.", "You have 1 note.", {"note": {"1"}}, True),
        ("You have one hundred and five notes.", "You have 105 notes.", {"note": {"105"}}, True),
        ("You have one hundred and five notes.", "You have 5 notes.", {"note": {"5"}}, False),
        ("You have a hundred and twenty-one notes.", "You have 121 notes.", {"note": {"121"}}, True),
        ("You have two thousand three hundred and four notes.", "You have 2304 notes.", {"note": {"2304"}}, True),
        ("You have twenty one notes.", "You have 21 notes.", {"note": {"21"}}, True),
        ("You have one or two notes.", "You have 2 notes.", {"note": {"2"}}, False),
        ("Every single note is filed.", "You have 3 notes.", {"note": {"3"}}, True),
    ],
)
def test_an_amount_in_words_is_read_whole(prose, facts, counts, ok):
    """The third review: "not a single one" was 0 and then a stray "one",
    "nothing else" was a count of none, and "one hundred and five" was 100
    and 5."""
    assert fact_check.keeps(prose, facts, "how many notes", counts, False) is ok


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        # The article and "both" as counts: each passed on three reminders.
        ("You have a reminder this week.", False),
        ("You only have a reminder: call mum.", False),
        ("There is a reminder this week.", False),
        ("Both reminders are this week.", False),
        ("You have 3 reminders; both are this week.", True),
        # "a" in ordinary prose claims no total.
        ("You have 3 reminders, including a reminder on Friday.", True),
        ("You have 3 reminders; the first is a reminder to call mum.", True),
    ],
)
def test_the_article_and_both_are_counts(ai_client, fake_ollama, session, prose, ok, use_tools):
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@SURFACES
@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        # Reminders on Wed 28 Oct and Fri 30 Oct (and one on 20 Nov).
        ("You have 3 reminders; rent is due on 12 November.", False),
        ("You have 3 reminders; rent is due 2026-12-01.", False),
        ("You have 3 reminders; rent is due on 30 Oct 2025.", False),
        ("You have 3 reminders; call mum is due Wed 28 Oct.", True),
        ("You have 3 reminders; call mum is due 28 October 2026.", True),
        ("You have 3 reminders; book dentist is due on 20 November.", True),
        ("You have 3 reminders; book dentist is due on 2026-11-20.", True),
        ("You have 3 reminders; call mum is due Thursday 28 Oct.", False),
        ("Today is 27 Oct; you have 3 reminders.", True),
    ],
)
def test_a_calendar_date_must_be_one_the_facts_name(ai_client, fake_ollama, session, prose, ok, use_tools):
    """Clock times ("3pm") stay unchecked; only the calendar date is."""
    _seed(session)
    assert _kept(ai_client, fake_ollama, "what reminders do I have", prose, use_tools) is ok


@pytest.mark.parametrize(
    ("prose", "ok"),
    [
        ("Rent is due Thursday 29 Oct at 3pm. You have 2 reminders.", False),
        ("Rent is due Thursday 29. You have 2 reminders.", False),
        ("Rent is due at 3pm. You have 2 reminders.", True),
        ("Call mum is due Wed 28 Oct at 3pm. You have 2 reminders.", True),
        ("Rent is due Friday 30. You have 2 reminders.", True),
    ],
)
def test_a_date_the_rows_do_not_have_is_refused(prose, ok):
    """Rows on Wed 28 Oct and Fri 30 Oct: Thursday 29 is invented, a clock time is not checked."""
    facts = "You have 2 reminders: call mum (Wed 28 Oct, 9:00) and book dentist (Fri 30 Oct, 11:00)."
    assert fact_check.keeps(prose, facts, "what reminders do I have", {"reminder": {"2"}}, False, NOW) is ok
