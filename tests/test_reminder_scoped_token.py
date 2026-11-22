"""A reminder's notification acts with a token scoped to that reminder.

The service worker used to hold the person's whole session token in the
notification's `data` (the browser's notification store) to press Done and
Snooze after the tab was closed. It now holds a token the server minted for
one reminder and two actions, good for 24 hours, and the one route that takes
it is outside the unlock gate for that reason alone.
"""

from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessellate.api import routes_auth
from tessellate.core import reminder_token
from tessellate.core.database import utcnow
from tests._clock import SUITE_NOW, pin_clock


@pytest.fixture(autouse=True)
def _suite_clock(monkeypatch):
    """Data here is built from SUITE_NOW, and the app reads the same pinned clock."""
    pin_clock(monkeypatch, SUITE_NOW)

ROOT = Path(__file__).resolve().parents[1]


# --- the token ---------------------------------------------------------------


def test_a_minted_token_names_its_reminder_and_its_two_actions():
    token = reminder_token.mint(7)["token"]
    assert reminder_token.verify(token, 7, "done")
    assert reminder_token.verify(token, 7, "snooze")
    assert not reminder_token.verify(token, 8, "done"), "another reminder"
    assert not reminder_token.verify(token, 7, "delete"), "an action outside the two"
    assert not reminder_token.verify(token, 7, "complete")


def test_a_forged_edited_or_expired_token_is_refused():
    token = reminder_token.mint(7)["token"]
    rid, expires, signature = token.split(".")
    assert not reminder_token.verify(f"{rid}.{expires}.{'0' * len(signature)}", 7, "done"), "a forged signature"
    assert not reminder_token.verify(f"{rid}.{int(expires) + 1}.{signature}", 7, "done"), "a longer expiry, same signature"
    assert not reminder_token.verify(f"8.{expires}.{signature}", 8, "done"), "another id, same signature"
    for junk in ("", "x", "1.2", "a.b.c", "1.2.3.4", None, "7." + "9" * 400):
        assert not reminder_token.verify(junk, 7, "done"), junk
    old = reminder_token.mint(7, now=time.time() - 2 * reminder_token.TTL_SECONDS)["token"]
    assert not reminder_token.verify(old, 7, "done"), "past its 24 hours"
    fresh = reminder_token.mint(7, now=time.time() - reminder_token.TTL_SECONDS + 60)["token"]
    assert reminder_token.verify(fresh, 7, "done"), "a minute inside it"


def test_rotating_the_key_ends_every_token():
    token = reminder_token.mint(3)["token"]
    reminder_token.rotate()
    assert not reminder_token.verify(token, 3, "done")


# --- the route -----------------------------------------------------------------


@pytest.fixture()
def locked_notebook(app_state):
    """A notebook with a password, and a reminder in it made by the owner."""
    from tessellate.api.app import create_app

    app = create_app()
    owner = TestClient(app)
    token = owner.post("/auth/setup", json={"password": "correct horse battery"}).json()["token"]
    owner.headers["X-Auth-Token"] = token
    due = (utcnow() + timedelta(hours=1)).isoformat()
    reminder = owner.post("/reminders", json={"text": "call Sam", "due_at": due}).json()
    other = owner.post("/reminders", json={"text": "water the plants", "due_at": due}).json()
    stranger = TestClient(app)  # the service worker: no session at all
    return owner, stranger, reminder, other


def _act(stranger, reminder_id, token, action="done", **extra):
    return stranger.post(f"/reminders/{reminder_id}/notification-act", json={"token": token, "action": action, **extra})


def test_the_owner_is_given_a_token_and_a_stranger_is_not(locked_notebook):
    owner, stranger, reminder, _ = locked_notebook
    minted = owner.post(f"/reminders/{reminder['id']}/notification-token")
    assert minted.status_code == 200 and minted.json()["token"].startswith(f"{reminder['id']}.")
    assert stranger.post(f"/reminders/{reminder['id']}/notification-token").status_code == 401
    assert owner.post("/reminders/9999/notification-token").status_code == 404


def test_done_works_after_the_tab_is_closed(locked_notebook):
    """The worker holds only the scoped token and no session header."""
    owner, stranger, reminder, other = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    routes_auth._active_tokens.clear()  # the tab, and its session, are gone
    answered = _act(stranger, reminder["id"], token, "done")
    assert answered.status_code == 200 and answered.json() == {"ok": True, "action": "done"}
    # Looked at through a fresh session of the owner's: done, and only that one.
    from tessellate.core.database import Reminder

    from tessellate.core import deps

    with deps.get_db().session() as session:
        assert session.get(Reminder, reminder["id"]).done is True
        assert session.get(Reminder, other["id"]).done is False


def test_snooze_moves_it_ten_minutes_on_and_keeps_it_open(locked_notebook):
    owner, stranger, reminder, _ = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    before = utcnow()
    assert _act(stranger, reminder["id"], token, "snooze").status_code == 200
    from tessellate.core import deps
    from tessellate.core.database import Reminder

    with deps.get_db().session() as session:
        row = session.get(Reminder, reminder["id"])
        moved = row.due_at.replace(tzinfo=None) - before.replace(tzinfo=None)
        assert timedelta(minutes=9, seconds=50) < moved < timedelta(minutes=10, seconds=30), moved
        assert row.done is False


def test_a_repeating_reminder_rolls_on_to_its_next_day(locked_notebook):
    owner, stranger, reminder, _ = locked_notebook
    due = (utcnow() + timedelta(minutes=1)).isoformat()
    daily = owner.post("/reminders", json={"text": "stretch", "due_at": due, "recurring": "daily"}).json()
    token = owner.post(f"/reminders/{daily['id']}/notification-token").json()["token"]
    assert _act(stranger, daily["id"], token, "done", tz_offset_minutes=60).status_code == 200
    listed = owner.get("/reminders").json()
    again = next(r for r in listed if r["id"] == daily["id"])
    assert again["done"] is False and again["due_at"] > due


@pytest.mark.parametrize("what", ["forged", "expired", "other reminder", "garbage"])
def test_a_token_that_does_not_belong_is_refused_and_changes_nothing(locked_notebook, what):
    owner, stranger, reminder, other = locked_notebook
    good = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    token = {
        "forged": good[:-4] + "0000",
        "expired": reminder_token.mint(reminder["id"], now=time.time() - 3 * 86400)["token"],
        "other reminder": owner.post(f"/reminders/{other['id']}/notification-token").json()["token"],
        "garbage": "not-a-token",
    }[what]
    answered = _act(stranger, reminder["id"], token)
    assert answered.status_code == 401
    assert owner.get("/reminders").json() and not next(r for r in owner.get("/reminders").json() if r["id"] == reminder["id"])["done"]


def test_a_refused_token_says_nothing_about_which_reminders_exist(locked_notebook):
    _, stranger, _, _ = locked_notebook
    missing = _act(stranger, 987654, "1.2.3")
    existing = _act(stranger, 1, "1.2.3")
    assert missing.status_code == existing.status_code == 401
    assert missing.json() == existing.json()


def test_only_done_and_snooze_are_accepted(locked_notebook):
    owner, stranger, reminder, _ = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    for action in ("delete", "complete", "purge", "update"):
        assert _act(stranger, reminder["id"], token, action).status_code == 422, action


def test_the_token_opens_nothing_else(locked_notebook):
    """Held by a stranger, as a body field or as a session header, it reads and
    changes nothing: every other reminder route and the rest of the notebook
    still answer 401."""
    owner, stranger, reminder, _ = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    rid = reminder["id"]
    for method, path, body in (
        ("get", "/reminders", None),
        ("get", f"/reminders/{rid}/export.ics", None),
        ("post", f"/reminders/{rid}/complete", None),
        ("put", f"/reminders/{rid}", {"done": True}),
        ("delete", f"/reminders/{rid}", None),
        ("post", f"/reminders/{rid}/notification-token", None),
        ("get", "/entries", None),
        ("get", "/preferences", None),
        ("get", "/categories", None),
    ):
        for headers in ({}, {"X-Auth-Token": token}):
            response = stranger.request(method, path, json=body, headers=headers)
            assert response.status_code == 401, (method, path, headers, response.status_code)


def test_locking_the_notebook_ends_a_notification_s_buttons(locked_notebook):
    owner, stranger, reminder, _ = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    owner.post("/auth/lock")
    assert _act(stranger, reminder["id"], token).status_code == 401


# --- the page and the worker ------------------------------------------------------


def test_the_session_token_is_no_longer_put_in_the_notification():
    notify = (ROOT / "frontend" / "js" / "reminder-notify.js").read_text(encoding="utf-8")
    assert "authToken()" not in notify, "the session token must not reach the notification's data"
    assert "/notification-token" in notify
    sw = (ROOT / "frontend" / "sw.js").read_text(encoding="utf-8")
    assert "X-Auth-Token" not in sw[sw.index("async function actOnReminder") : sw.index("async function openReminders")]
    assert "/notification-act" in sw


# --- a restart (Brief 101b) ---------------------------------------------------------


def test_a_notification_s_buttons_survive_a_restart(locked_notebook):
    """The key was invented per process, so any restart (an update, a crash,
    the desktop app closed and opened) ended the buttons of every notification
    still on screen. It is kept in the data folder now."""
    owner, stranger, reminder, _ = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    reminder_token.forget_process()  # what a new process starts with
    answered = _act(stranger, reminder["id"], token, "done")
    assert answered.status_code == 200, answered.text


def test_locking_after_a_restart_still_ends_a_notification_s_buttons(locked_notebook):
    owner, stranger, reminder, _ = locked_notebook
    token = owner.post(f"/reminders/{reminder['id']}/notification-token").json()["token"]
    reminder_token.forget_process()
    owner.post("/auth/lock")
    reminder_token.forget_process()  # and another restart: the lock holds
    assert _act(stranger, reminder["id"], token).status_code == 401


def test_the_key_file_is_owner_only_and_a_damaged_one_is_replaced(tmp_path):
    token = reminder_token.mint(5, data_dir=tmp_path)["token"]
    path = tmp_path / reminder_token.KEY_FILE
    assert path.stat().st_mode & 0o077 == 0
    reminder_token.forget_process()
    assert reminder_token.verify(token, 5, "done", data_dir=tmp_path)
    path.write_text("not hex", encoding="ascii")
    reminder_token.forget_process()
    assert not reminder_token.verify(token, 5, "done", data_dir=tmp_path)
    assert reminder_token.verify(reminder_token.mint(5, data_dir=tmp_path)["token"], 5, "done", data_dir=tmp_path)
