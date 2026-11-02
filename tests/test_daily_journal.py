"""The journal's daily note: created once, found again, and counted.

WORLD_CLASS_PLAN section 13, D6. The convention (a note whose first line is
`# <ISO date>`) shipped with Phase 4 of the timeline work; what it never had
was the "or returns" half, so pressing "today's note" twice in one day made
two notes headed with the same date and split the day's writing between them.
"""

from __future__ import annotations


def test_todays_note_is_made_once_and_found_again(client):
    first = client.post("/entries/daily/2026-09-13")
    assert first.status_code == 200, first.text
    assert first.json()["content"].startswith("# 2026-09-13")

    second = client.post("/entries/daily/2026-09-13")
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    # And there is one note, not two, which is the bug this endpoint exists
    # to remove.
    everything = client.get("/entries?limit=200").json()
    headed = [row for row in everything if (row["content"] or "").startswith("# 2026-09-13")]
    assert len(headed) == 1


def test_a_different_day_is_a_different_note(client):
    one = client.post("/entries/daily/2026-09-12").json()
    two = client.post("/entries/daily/2026-09-13").json()
    assert one["id"] != two["id"]


def test_writing_in_the_note_is_kept_when_it_is_opened_again(client):
    made = client.post("/entries/daily/2026-09-13").json()
    client.put(
        f"/entries/{made['id']}",
        json={"content": "# 2026-09-13\n\nrang the dentist, finally"},
    )
    again = client.post("/entries/daily/2026-09-13").json()
    assert again["id"] == made["id"]
    assert "rang the dentist" in again["content"]


def test_a_date_that_is_not_a_date_is_refused(client):
    assert client.post("/entries/daily/not-a-date").status_code == 422
    assert client.post("/entries/daily/2026-13-45").status_code == 422
    assert client.get("/entries/daily/not-a-date").status_code == 422


def test_reading_a_day_never_writes_one(client):
    """The GET is read-only: a GET that makes a row sits outside the CSRF
    defence, which judges methods. Opening the journal is the POST."""
    assert client.get("/entries/daily/2026-09-13").status_code == 404
    assert client.get("/entries?limit=200").json() == []

    made = client.post("/entries/daily/2026-09-13").json()
    assert client.get("/entries/daily/2026-09-13").json()["id"] == made["id"]


def test_a_note_that_merely_mentions_a_date_is_not_that_days_journal(client):
    client.post(
        "/entries",
        json={"content": "notes from the meeting\n\n# 2026-09-13 was when we agreed it"},
    )
    made = client.post("/entries/daily/2026-09-13").json()
    assert made["content"].startswith("# 2026-09-13\n")
    assert "meeting" not in made["content"]


def test_the_window_says_which_days_were_written(client):
    client.post("/entries/daily/2026-09-13")
    client.post("/entries/daily/2026-09-11")
    window = client.get("/entries/daily?through=2026-09-13&days=5").json()
    assert window["through"] == "2026-09-13"
    assert [day["date"] for day in window["days"]] == [
        "2026-09-09",
        "2026-09-10",
        "2026-09-11",
        "2026-09-12",
        "2026-09-13",
    ]
    assert {day["date"] for day in window["days"] if day["written"]} == {
        "2026-09-11",
        "2026-09-13",
    }


def test_the_streak_counts_back_and_stops_at_the_first_gap(client):
    for day in ("2026-09-13", "2026-09-12", "2026-09-11"):
        client.post(f"/entries/daily/{day}")
    # 09-10 is skipped on purpose.
    client.post("/entries/daily/2026-09-09")
    assert client.get("/entries/daily?through=2026-09-13&days=10").json()["streak"] == 3


def test_an_empty_today_does_not_wipe_the_streak(client):
    """The counter must not punish the morning: nine days written and today
    not yet opened is a streak of nine, not zero."""
    for day in ("2026-09-12", "2026-09-11", "2026-09-10"):
        client.post(f"/entries/daily/{day}")
    assert client.get("/entries/daily?through=2026-09-13&days=10").json()["streak"] == 3


def test_a_notebook_with_no_journal_has_no_streak(client):
    window = client.get("/entries/daily?through=2026-09-13&days=7").json()
    assert window["streak"] == 0
    assert all(day["written"] is False for day in window["days"])


def test_a_binned_journal_entry_leaves_the_window(client):
    made = client.post("/entries/daily/2026-09-13").json()
    client.delete(f"/entries/{made['id']}")
    window = client.get("/entries/daily?through=2026-09-13&days=3").json()
    assert window["streak"] == 0
    assert all(day["written"] is False for day in window["days"])


def test_the_window_is_bounded(client):
    """A calendar strip asks for days, and a year is the most it can mean."""
    assert client.get("/entries/daily?through=2026-09-13&days=0").status_code == 422
    assert client.get("/entries/daily?through=2026-09-13&days=100000").status_code == 422
    assert client.get("/entries/daily?through=2026-09-13&days=366").status_code == 200
    assert client.get("/entries/daily?through=nonsense").status_code == 422


def test_today_is_the_users_day_not_the_servers(client, monkeypatch):
    """Audit 1028 K22: with no `through`, today was the server's
    `date.today()`, so a phone across the date line saw the wrong day."""
    from datetime import datetime, timezone

    from tessellate.core import config as config_module

    fixed = datetime(2026, 9, 13, 20, 0, tzinfo=timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr(config_module, "datetime", Clock)
    saved = client.put("/preferences", json={"timezone": "Pacific/Kiritimati"})
    assert saved.status_code == 200
    answer = client.get("/entries/daily?days=3").json()
    assert answer["through"] == "2026-09-14", "20:00 UTC is 10:00 the next day at UTC+14"
