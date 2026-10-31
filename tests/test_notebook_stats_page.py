"""`GET /statistics`: the Statistics page's counts in one call
(UI_MODERNISATION statistics rows 1 and 2, Brief 89).

Exact, like the chat's statistics: every figure is a count of rows, so a test
that accepted "about right" would test nothing.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from tessellate.ai import notebook_stats
from tessellate.core import deps
from tessellate.core.database import Category, Entry, EntryLink, Reminder


def _session():
    return deps.get_db().session()


def _note(session, content, tags=(), created=None):
    entry = Entry(content=content, tags=json.dumps(list(tags)))
    if created is not None:
        entry.created_at = created
    session.add(entry)
    session.flush()
    return entry


#: A Wednesday, so this week has two days before it and last week is whole.
NOW = datetime(2026, 10, 14, 15, 0, tzinfo=timezone.utc)


def test_the_page_counts_the_notebook(client):
    with _session() as session:
        a = _note(session, "one two three", ["work", "idea"], created=NOW)
        b = _note(session, "four five", ["work"], created=NOW)
        _note(session, "six", [], created=NOW)
        session.add(EntryLink(source_entry_id=a.id, target_entry_id=b.id))
        session.add(Category(name="Projects"))
        session.commit()
        page = notebook_stats.page(session, NOW, {"features": [], "unused_days": 90})
    book = page["notebook"]
    assert (book["notes"], book["words"], book["tags"], book["links"], book["orphans"]) == (3, 6, 2, 1, 1)
    assert book["categories"] >= 1
    assert len(book["growth"]) == notebook_stats.GROWTH_MONTHS
    assert book["growth"][-1]["value"] == 3


def test_growth_is_per_month_and_bounded(client):
    with _session() as session:
        _note(session, "old", created=NOW - timedelta(days=400))
        _note(session, "march", created=datetime(2026, 3, 9, tzinfo=timezone.utc))
        _note(session, "october", created=datetime(2026, 10, 2, tzinfo=timezone.utc))
        session.commit()
        growth = notebook_stats.page(session, NOW, {})["notebook"]["growth"]
    labels = [row["label"] for row in growth]
    assert labels[0] == "2025-11" and labels[-1] == "2026-10"
    assert {row["label"]: row["value"] for row in growth}["2026-03"] == 1
    assert sum(row["value"] for row in growth) == 2


def test_reminders_made_done_late_and_open(client):
    with _session() as session:
        session.add_all([
            Reminder(text="late", due_at=NOW - timedelta(days=1)),
            Reminder(text="soon", due_at=NOW + timedelta(days=1)),
            Reminder(text="done", due_at=NOW - timedelta(days=2), done=True),
        ])
        session.commit()
        block = notebook_stats.page(session, NOW, {})["reminders"]
    assert block == {"made": 3, "done": 1, "late": 1, "open": 2}


def test_ticking_a_reminder_stamps_when_and_unticking_clears_it(client):
    with _session() as session:
        reminder = Reminder(text="x", due_at=NOW)
        session.add(reminder)
        session.commit()
        assert reminder.done_at is None
        reminder.done = True
        assert reminder.done_at is not None
        reminder.done = False
        assert reminder.done_at is None


def test_the_week_review_is_this_week_against_last(client):
    monday = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    with _session() as session:
        _note(session, "a b c", created=monday)
        _note(session, "d e", created=monday - timedelta(days=3))
        _note(session, "f", created=monday - timedelta(days=6))
        _note(session, "too old", created=monday - timedelta(days=9))
        session.add(Reminder(text="r", due_at=NOW, done=False))
        session.commit()
        ticked = Reminder(text="t", due_at=NOW)
        session.add(ticked)
        session.flush()
        ticked.done_at = monday - timedelta(days=2)
        session.commit()
        week = notebook_stats.page(session, NOW, {})["week"]
    assert week["this"]["start"] == "2026-10-12" and week["this"]["end"] == "2026-10-14"
    assert week["last"]["start"] == "2026-10-05" and week["last"]["end"] == "2026-10-11"
    assert (week["this"]["notes"], week["this"]["words"], week["this"]["reminders_done"]) == (1, 3, 0)
    assert (week["last"]["notes"], week["last"]["words"], week["last"]["reminders_done"]) == (2, 3, 1)


def test_binned_notes_are_not_counted_and_private_words_are_not_read(client):
    with _session() as session:
        _note(session, "seen")
        hidden = _note(session, "private words here")
        hidden.is_private = True
        gone = _note(session, "binned")
        gone.deleted_at = NOW
        session.commit()
        book = notebook_stats.page(session, NOW, {})["notebook"]
    # INBOX 1439: a private note is a note (one count everywhere); its words are not counted.
    assert (book["notes"], book["words"]) == (2, 1)


def test_a_link_to_a_binned_or_private_note_is_not_a_link_on_the_page(client):
    """INBOX 1280: the count of links is the links between notes that are
    counted, so it cannot say a hidden note is joined to anything."""
    with _session() as session:
        a = _note(session, "seen one")
        b = _note(session, "seen two")
        hidden = _note(session, "private words")
        hidden.is_private = True
        gone = _note(session, "binned")
        gone.deleted_at = NOW
        session.add_all(
            [
                EntryLink(source_entry_id=a.id, target_entry_id=b.id),
                EntryLink(source_entry_id=a.id, target_entry_id=hidden.id),
                EntryLink(source_entry_id=gone.id, target_entry_id=b.id),
            ]
        )
        session.commit()
        book = notebook_stats.page(session, NOW, {})["notebook"]
    assert (book["notes"], book["links"], book["orphans"]) == (3, 1, 0)


def test_the_route_answers_in_one_call_with_the_usage_rows(client):
    client.post("/usage", json={"features": ["tab:chat", "tab:chat", "palette:undo"]})
    client.post("/entries", json={"content": "hello there"})
    body = client.get("/statistics").json()
    assert set(body) == {"as_of", "notebook", "reminders", "week", "usage"}
    assert body["notebook"]["notes"] >= 1
    assert {f["name"]: f["count"] for f in body["usage"]["features"]}["tab:chat"] == 2
    assert body["usage"]["uses"] == 3
    assert body["usage"]["unused_days"] == 90



def test_the_week_can_start_on_sunday_or_saturday():
    wednesday = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
    assert notebook_stats.week_start(wednesday).date().isoformat() == "2026-10-12"
    assert notebook_stats.week_start(wednesday, 6).date().isoformat() == "2026-10-11"
    assert notebook_stats.week_start(wednesday, 5).date().isoformat() == "2026-10-10"
    sunday = datetime(2026, 10, 11, 9, 0, tzinfo=timezone.utc)
    assert notebook_stats.week_start(sunday, 6).date().isoformat() == "2026-10-11"


def test_the_first_day_follows_the_choice_then_the_locale_then_monday(client):
    first = client.get("/statistics").json()["week"]["this"]["start"]
    assert datetime.fromisoformat(first).weekday() == 0
    client.put("/preferences", json={"week_start_locale": 6})
    reported = client.get("/statistics").json()["week"]["this"]["start"]
    assert datetime.fromisoformat(reported).weekday() == 6
    client.put("/preferences", json={"week_start": "saturday"})
    chosen = client.get("/statistics").json()["week"]["this"]["start"]
    assert datetime.fromisoformat(chosen).weekday() == 5
    bad = client.put("/preferences", json={"week_start": "friday"})
    assert bad.status_code == 422


def test_words_added_to_older_notes_by_edits_are_counted_apart(client):
    """Ledger 1525: the week's edits to notes made before it, read from the revisions."""
    from tessellate.core.database import EntryRevision

    monday = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    with _session() as session:
        old = _note(session, "one two three", created=monday - timedelta(days=30))
        old.content = "one two three four five six seven"
        session.add(EntryRevision(entry_id=old.id, content="one two three", created_at=monday - timedelta(days=1)))
        session.add(EntryRevision(entry_id=old.id, content="one two three four five", created_at=monday))
        session.commit()
        week = notebook_stats.page(session, NOW, {})["week"]
    # The edit made in the week (one two three four five -> seven words) added two;
    # the edit made last week is last week's.
    assert week["this"]["edited_words"] == 2
    assert week["last"]["edited_words"] == 2


def test_the_growth_range_is_three_months_a_year_or_all(client):
    """INBOX 1319: the growth chart's range is a server parameter."""
    with _session() as session:
        _note(session, "old", created=datetime(2024, 5, 9, tzinfo=timezone.utc))
        _note(session, "march", created=datetime(2026, 3, 9, tzinfo=timezone.utc))
        _note(session, "october", created=datetime(2026, 10, 2, tzinfo=timezone.utc))
        session.commit()
        three = notebook_stats.page(session, NOW, {}, growth="3")["notebook"]["growth"]
        year = notebook_stats.page(session, NOW, {})["notebook"]["growth"]
        everything = notebook_stats.page(session, NOW, {}, growth="all")["notebook"]["growth"]
    assert [row["label"] for row in three] == ["2026-08", "2026-09", "2026-10"]
    assert len(year) == 12
    assert everything[0]["label"] == "2024-05" and everything[-1]["label"] == "2026-10"
    assert sum(row["value"] for row in everything) == 3 and len(everything) == 30


def test_the_route_takes_the_growth_range_and_rejects_others(client):
    client.post("/entries", json={"content": "hello there"})
    assert len(client.get("/statistics?growth=3").json()["notebook"]["growth"]) == 3
    assert len(client.get("/statistics?growth=all").json()["notebook"]["growth"]) >= 1
    assert len(client.get("/statistics").json()["notebook"]["growth"]) == 12
    assert client.get("/statistics?growth=7").status_code == 422


def test_the_week_carries_a_count_per_day_for_both_weeks(client):
    """The sparkline under each week row: fourteen days, last week's Monday first."""
    monday = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    with _session() as session:
        _note(session, "a b c", created=monday)
        _note(session, "d e", created=monday)
        _note(session, "f", created=monday - timedelta(days=6))
        ticked = Reminder(text="t", due_at=NOW)
        session.add(ticked)
        session.flush()
        ticked.done_at = monday - timedelta(days=2)
        session.commit()
        daily = notebook_stats.page(session, NOW, {})["week"]["daily"]
    assert daily["start"] == "2026-10-05"
    assert len(daily["notes"]) == len(daily["words"]) == len(daily["reminders_done"]) == 14
    assert daily["notes"][1] == 1 and daily["notes"][7] == 2 and sum(daily["notes"]) == 3
    assert daily["words"][7] == 5 and daily["reminders_done"][5] == 1
