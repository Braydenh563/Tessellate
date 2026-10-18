"""The computed answers of the engine probe (CHAT_PLAN Phase 6, P10 to P13).

"how many days until the dentist", "is the dentist before the boiler
service", "how many times did I mention Porto", "list my work notes" and
"what is due this week" were answered with a quoted note (the digest took the
question before the computing shapes saw it). Each is now one sentence worked
out from the notes' own days and words, then the lines it rests on, each
with its mark. Judged on the shape decision 70 names, not on a rule count.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from tessellate.ai import composer_digest, composer_lists
from tessellate.entry import manager

TODAY = date(2026, 10, 11)
RAW = [
    ("Dentist appointment on 3 November at 9am. Bring the x-ray form.", "2026-10-01", "Health", ["dentist"]),
    ("Porto trip notes: the wine cellars in Gaia were great. Porto has the best pastries.", "2026-08-02", "Travel", ["porto"]),
    ("Porto again: take the tram to the coast, book the Livraria Lello ticket. Porto in May is lovely.", "2026-08-09", "Travel", ["porto"]),
    ("Launch checklist:\n- [x] domain\n- [ ] landing page\n- [ ] press kit\n- [x] pricing", "2026-09-10", "Work", ["launch", "work"]),
    ("Work notes: standup moved to 10am. Send the invoice by Friday 16 October.", "2026-10-08", "Work", ["work"]),
    ("Boiler service on 20 October.", "2026-10-02", "Home", ["home"]),
    ("Pay rent on 1 November. Dentist follow-up on 15 November.", "2026-10-03", "Finance", ["finance"]),
]
NOTES = [
    {"id": i + 1, "content": c, "created_at": f"{d}T10:00:00", "category": cat, "tags": t}
    for i, (c, d, cat, t) in enumerate(RAW)
]


def _say(question: str, notes=NOTES) -> dict | None:
    return composer_digest.answer(question, notes, today=TODAY)


def _marks(result: dict) -> list[int]:
    return [row["note_id"] for row in result["grounding"]]


def test_days_until_a_note_s_day_is_counted_from_today_and_cited():
    result = _say("how many days until the dentist")
    assert result["text"].startswith("The dentist is on 3 November, 23 days from today."), result["text"]
    assert _marks(result)[0] == 1
    assert "[your note" not in result["text"]


def test_days_since_a_day_is_said_in_the_past():
    result = _say("how long since the boiler service", [{**NOTES[5], "content": "Boiler service on 2 October."}])
    assert result["text"].startswith("The boiler service was on 2 October, 9 days ago."), result["text"]


def test_tomorrow_and_today_are_said_as_words():
    one = [{"id": 1, "content": "Dentist on 12 October.", "created_at": "2026-10-01T10:00:00", "category": "Health", "tags": []}]
    assert _say("how many days until the dentist", one)["text"].startswith("The dentist is tomorrow, 12 October."), one
    now = [{**one[0], "content": "Dentist on 11 October."}]
    assert _say("how many days until the dentist", now)["text"].startswith("The dentist is today."), now


def test_which_comes_first_is_worked_out_from_both_days():
    no = _say("is the dentist before the boiler service")
    assert no["text"].startswith("No, the boiler service comes first: 20 October, 14 days before the dentist on 3 November."), no["text"]
    assert sorted(_marks(no)) == [1, 6]
    yes = _say("is the boiler service before the dentist")
    assert yes["text"].startswith("Yes, the boiler service is on 20 October, 14 days before the dentist on 3 November."), yes["text"]
    after = _say("is the dentist after the boiler service")
    assert after["text"].startswith("Yes, the dentist is on 3 November, 14 days after the boiler service on 20 October."), after["text"]


def test_a_day_no_note_names_is_not_invented():
    assert _say("how many days until the wedding") is None
    assert _say("is the wedding before the dentist") is None


def test_mentions_are_counted_over_the_notes_and_cited():
    result = _say("how many times did I mention Porto")
    assert result["text"].startswith("You mentioned Porto 4 times, in 2 notes, "), result["text"]
    assert sorted(set(_marks(result))) == [2, 3]
    assert "[your note" not in result["text"]
    assert _say("how often do I mention Porto")["text"].startswith("You mentioned Porto 4 times")
    one = _say("how many times did I mention boiler")
    assert one["text"].startswith("You mentioned boiler once, in one note, on 2 October."), one["text"]
    assert _say("how many times did I mention Lisbon") is None


def test_a_list_by_category_or_tag_is_every_note_in_it():
    work = _say("list my work notes")
    assert work["text"].startswith("You have two notes in Work, 10 September to 8 October:"), work["text"]
    assert sorted(_marks(work)) == [4, 5]
    assert work["text"].index("Work notes: standup") < work["text"].index("Launch checklist")  # newest first
    tagged = _say("list everything tagged launch")
    assert tagged["text"].startswith("You have one note tagged launch, 10 September:"), tagged["text"]
    assert _marks(tagged) == [4]
    assert _say("show me all my home notes")["text"].startswith("You have one note in Home"), "home"
    assert _say("list my cooking notes") is None


def test_what_is_due_reads_the_days_in_the_notes():
    week = _say("what is due this week")
    assert week["text"].startswith("One date falls in the next seven days: 16 October."), week["text"]
    assert "Send the invoice by Friday 16 October." in week["text"]
    assert _marks(week) == [5]
    month = _say("what is coming up this month")
    assert "20 October" in month["text"] and "16 October" in month["text"], month["text"]
    assert month["text"].index("16 October") < month["text"].index("20 October")
    assert "1 November" not in month["text"] and "3 November" not in month["text"]


@pytest.mark.parametrize(
    "question",
    [
        "what are the deadlines for the tax return",
        "what is due in Work",
        "what is due for the boiler",
        "what is coming up in my Health notes",
        "what is the upcoming iPhone release",
    ],
)
def test_a_due_question_that_names_a_subject_is_not_the_dates_list(question):
    assert composer_lists.kind(question) is None


def test_an_empty_window_says_so_and_names_the_next_day():
    far = _say("what is due tomorrow")
    assert far["text"].startswith("Nothing in your notes falls tomorrow."), far["text"]
    assert "The next is 16 October" in far["text"], far["text"]


def test_all_the_dates_are_listed_soonest_first():
    result = _say("what are all the dates in my notes")
    lines = [line for line in result["text"].split("\n") if line.startswith("- ")]
    assert result["text"].startswith("Five dates are ahead in your notes, 16 October to 15 November:"), result["text"]
    assert len(lines) == 5 and lines[0].startswith("- 16 October")
    none = _say("what are all the dates in my notes", [{"id": 1, "content": "Nothing dated here.", "created_at": "2026-10-01T10:00:00"}])
    assert none and none["text"].startswith("I found no day ahead in your notes."), none


@pytest.mark.parametrize(
    "question",
    ["when are my uni days", "what did I think of Dune", "who is Sam", "what is in my notes about the dentist", "how many notes do I have"],
)
def test_other_questions_are_left_to_their_own_shapes(question):
    assert composer_lists.kind(question) is None


def test_the_five_kinds_are_told_apart():
    assert composer_lists.kind("how many days until the dentist") == "until"
    assert composer_lists.kind("is the dentist before the boiler service") == "order"
    assert composer_lists.kind("how many times did I mention Porto") == "mentions"
    assert composer_lists.kind("list my work notes") == "listed"
    assert composer_lists.kind("what is due this week") == "dates"


def _ask(client, question: str) -> tuple[str, list[dict]]:
    text, grounding = "", []
    with client.stream("POST", "/chat/stream", json={"question": question, "notes_only": True, "use_tools": False}) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            if line.strip():
                event = json.loads(line)
                if event["type"] == "answer":
                    text += event.get("delta", "")
                elif event["type"] == "grounding":
                    grounding = event["sentences"]
    return text, grounding


@pytest.fixture()
def notebook(session):
    """The notebook past the five notes a search returns: eight tagged work."""
    for i in range(8):
        entry = manager.create_entry(session, f"Work item {i}: ship build {i}.", "Work", ["work"])
        entry.created_at = datetime(2026, 9, 1 + i, 10)
    for c, d, cat, t in RAW[:3]:
        entry = manager.create_entry(session, c, cat, t)
        entry.created_at = datetime.fromisoformat(f"{d}T10:00:00")
    session.commit()


def test_through_the_route_the_list_is_every_note_not_the_five_a_search_returns(client, notebook):
    text, _ = _ask(client, "list my work notes")
    #: The category search already says this one (its own listing shape); Ask
    #: used to answer "something to do (find a note)" instead of listing.
    assert "eight Work notes" in text and text.count("\n- [") == 8, text
    assert "something to do" not in text


def test_through_the_route_the_count_reads_every_note_that_mentions_it(client, notebook):
    text, _ = _ask(client, "how many times did I mention Porto")
    assert text.startswith("You mentioned Porto 4 times, in 2 notes"), text


def test_through_the_route_a_word_no_note_says_quotes_no_near_miss(client, notebook):
    text, grounding = _ask(client, "how many times did I mention Zanzibar")
    assert "[your note" not in text and not grounding, (text, grounding)


def test_through_the_route_all_the_dates_is_not_read_as_a_newest_first_overview(client, session):
    """Ask searches "all the dates in my notes" newest first; the digest still
    answers it, and with no day ahead it says so rather than summarising."""
    for i in range(3):
        manager.create_entry(session, f"Gym session {i}: squats and rows.", "Fitness", ["gym"])
    text, _ = _ask(client, "what are all the dates in my notes")
    assert text.startswith("I found no day ahead in your notes."), text


def test_a_name_with_a_capital_outside_ascii_is_still_found(session):
    """SQLite folds only ASCII case, so a LIKE on "ünal" never matched "Ünal"."""
    from tessellate.ai import list_pool

    manager.create_entry(session, "Dinner with Ünal on Friday.", "Social", ["friends"])
    session.commit()
    found = list_pool.pool(session, "how many times did I mention Ünal", [])
    assert [e.content for e in found] == ["Dinner with Ünal on Friday."]


def test_a_count_that_reaches_the_pool_is_said_to_be_a_floor():
    many = [
        {"id": i + 1, "content": f"Note {i} about lisbon.", "created_at": "2026-10-01T10:00:00", "category": "Travel", "tags": []}
        for i in range(composer_lists.POOL_LIMIT)
    ]
    result = _say("how many times did I mention lisbon", many)
    assert result["text"].startswith(f"You mentioned lisbon at least {composer_lists.POOL_LIMIT} times"), result["text"]
    assert _say("how many times did I mention lisbon", many[:5])["text"].startswith("You mentioned lisbon 5 times")


def test_a_long_what_is_question_is_classified_in_linear_time():
    import time

    started = time.perf_counter()
    assert composer_lists.kind("what is " * 5000) is None
    assert time.perf_counter() - started < 0.5
