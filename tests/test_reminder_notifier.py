"""The desktop app's reminder notifications (TIMELINE_PLAN 11 row 3, decision 69).

The launcher's thread reads due reminders from the database and asks the
operating system to show each due time once. Linux runs here for real, through
a stand-in `notify-send` on PATH (the CI machine has no notification service);
the Windows and macOS commands are checked as built, and were not run.
"""

from __future__ import annotations

import os
import stat
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from tessellate.core import reminder_notifier as rn
from tessellate.core.database import utcnow
from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock


def _row(id_, due, *, done=False, alert=None, text="Dentist"):
    return SimpleNamespace(id=id_, due_at=due, done=done, alert_minutes=alert, text=text)


NOW = datetime(2026, 10, 11, 9, 0)


def test_a_due_time_is_announced_once_and_again_at_a_new_time():
    rows = [_row(1, NOW - timedelta(seconds=5))]
    fresh, upcoming = rn.due_now(rows, set(), NOW)
    assert [d.key for d in fresh] == ["1@2026-10-11T08:59"] and upcoming is None
    assert rn.due_now(rows, {fresh[0].key}, NOW)[0] == []
    snoozed = [_row(1, NOW + timedelta(minutes=10))]
    assert rn.due_now(snoozed, {fresh[0].key}, NOW + timedelta(minutes=10))[0][0].key == "1@2026-10-11T09:10"


def test_done_old_and_future_reminders_are_not_announced_and_the_next_time_is_given():
    rows = [
        _row(1, NOW - timedelta(minutes=1), done=True),
        _row(2, NOW - rn.LOOKBACK - timedelta(minutes=1)),
        _row(3, NOW + timedelta(seconds=60)),
    ]
    fresh, upcoming = rn.due_now(rows, set(), NOW)
    assert fresh == [] and upcoming == NOW + timedelta(seconds=60)


def test_an_early_alert_is_its_own_announcement():
    rows = [_row(4, NOW + timedelta(hours=1), alert=60)]
    fresh, upcoming = rn.due_now(rows, set(), NOW)
    assert [(d.key, d.early) for d in fresh] == [("e4@2026-10-11T10:00", True)]
    assert upcoming == NOW + timedelta(hours=1)


def test_the_fired_store_survives_a_restart_and_is_bounded(tmp_path):
    path = tmp_path / rn.STORE_NAME
    store = rn.FiredStore(path)
    store.add([f"k{i}" for i in range(rn.KEPT_KEYS + 5)])
    again = rn.FiredStore(path)
    assert "k5" in again and "k4" not in again and len(again.keys) == rn.KEPT_KEYS
    path.write_text("not json", encoding="utf-8")
    assert rn.FiredStore(path).keys == []


@pytest.mark.parametrize(
    ("platform", "found", "expected"),
    [
        ("win32", {"powershell"}, "powershell"),
        ("darwin", {"osascript"}, "osascript"),
        ("linux", {"notify-send", "gdbus"}, "notify-send"),
        ("linux", {"gdbus"}, "gdbus"),
        ("linux", set(), None),
    ],
)
def test_each_system_has_its_own_notifier(platform, found, expected):
    assert rn.pick_backend(platform, lambda name: name if name in found else None) == expected


def test_the_reminder_text_is_never_part_of_a_script():
    text = "pay rent'); Remove-Item * ; (\" <b>&"
    argv, env, listens = rn.build_command("powershell", "Reminder", text, with_actions=True)
    assert listens and text not in " ".join(argv)
    assert "pay rent&apos;" in env["MM_TOAST_XML"] or "pay rent'" in env["MM_TOAST_XML"]
    assert "&lt;b&gt;&amp;" in env["MM_TOAST_XML"]
    assert 'arguments="done"' in env["MM_TOAST_XML"] and 'arguments="snooze"' in env["MM_TOAST_XML"]
    assert env["MM_TOAST_APP"] == rn.POWERSHELL_APP_ID
    assert rn.build_command("powershell", "R", "x", with_actions=False, frozen=True)[1]["MM_TOAST_APP"] == rn.APP_ID

    argv, _, listens = rn.build_command("osascript", "Reminder", text, with_actions=True)
    assert argv[-2:] == ["Reminder", text] and not listens

    argv, _, _ = rn.build_command("gdbus", "Reminder", 'say "hi" \\ now', with_actions=False)
    assert '"say \\"hi\\" \\\\ now"' in argv


def test_notify_send_offers_buttons_only_where_libnotify_reads_them():
    argv, _, listens = rn.build_command(
        "notify-send", "Reminder", "-rf", with_actions=True, icon="/i.png", send_reads_actions=True
    )
    assert listens and "--wait" in argv and "--action=done=Done" in argv
    assert "--action=snooze=Snooze 10 minutes" in argv and "--action=default=Open" in argv
    assert argv[-3:] == ["--", "Reminder", "-rf"]
    plain, _, listens = rn.build_command("notify-send", "Reminder", "x", with_actions=True)
    assert not listens and not any(a.startswith("--action") for a in plain)


def test_health_says_while_the_launcher_has_the_notification(client, tmp_path, monkeypatch):
    assert client.get("/health").json()["os_notify"] is False
    monkeypatch.setattr(rn, "pick_backend", lambda: "osascript")
    notifier = rn.start(tmp_path, icon=None)
    try:
        assert client.get("/health").json()["os_notify"] is True
    finally:
        notifier.stop()
    assert client.get("/health").json()["os_notify"] is False
    monkeypatch.setattr(rn, "pick_backend", lambda: None)
    assert rn.start(tmp_path) is None and client.get("/health").json()["os_notify"] is False


def _fake_notify_send(tmp_path, answer: str):
    """A `notify-send` that reads `--action`, records each call and presses
    `answer` (empty: the person ignores it)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "shown.log"
    script = bin_dir / "notify-send"
    script.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--help" ]; then echo "  -A, --action=[NAME=]Text  -w, --wait"; exit 0; fi\n'
        f'printf "%s\\n" "$*" >> "{log}"\n'
        f'printf "{answer}"\n',
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return bin_dir, log


def _shown(log):
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


@pytest.mark.skipif(os.name != "posix", reason="a shell stand-in for notify-send")
def test_a_reminder_fires_once_with_no_window_and_done_from_it_marks_it_done(client, tmp_path, monkeypatch):
    """The brief's measure in small: no window at all (the thread does not
    need one), a reminder due shortly, one notification, its Done applied
    through the route's own code."""
    bin_dir, log = _fake_notify_send(tmp_path, "done")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    # Deliberately the real clock: the notifier thread reads its own wall time
    # and the test waits out a real 1.5 s, so a frozen "now" would never fire.
    due = utcnow() + timedelta(seconds=1.5)
    made = client.post("/reminders", json={"text": "Call the dentist", "due_at": due.isoformat()}).json()
    notifier = rn.ReminderNotifier(rn.FiredStore(tmp_path / rn.STORE_NAME), "notify-send").start()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not client.get("/reminders").json()[0]["done"]:
            time.sleep(0.1)
        fired_at = datetime.now(timezone.utc)
        time.sleep(1.5)
    finally:
        notifier.stop()
    shown = _shown(log)
    assert len(shown) == 1 and "Call the dentist" in shown[0] and "--action=done=Done" in shown[0]
    assert client.get("/reminders").json()[0]["done"] is True
    assert (fired_at - due).total_seconds() < 5
    assert made["id"] == client.get("/reminders").json()[0]["id"]


def test_ticks_after_the_first_announce_nothing_and_a_snooze_brings_it_back(client, tmp_path, monkeypatch):
    freeze_reminder_clock(monkeypatch, notifier=True)
    calls = []
    notifier = rn.ReminderNotifier(
        rn.FiredStore(tmp_path / rn.STORE_NAME),
        "osascript",
        run=lambda argv, **kw: calls.append(argv),
    )
    due = FIXED_NOW + timedelta(minutes=1)
    rid = client.post("/reminders", json={"text": "Stretch", "due_at": due.isoformat()}).json()["id"]
    later = due.replace(tzinfo=None) + timedelta(seconds=1)
    assert notifier.tick(later - timedelta(seconds=61)) == pytest.approx(rn.MAX_SLEEP_S)
    assert notifier.tick(later - timedelta(seconds=11)) == pytest.approx(10.25, abs=0.01)
    notifier.tick(later)
    notifier.tick(later + timedelta(seconds=30))
    assert [argv[-1] for argv in calls] == ["Stretch"]
    notifier.answer("snooze", rid)
    moved = datetime.fromisoformat(client.get("/reminders").json()[0]["due_at"]).replace(tzinfo=None)
    assert timedelta(minutes=9) < moved - FIXED_NOW.replace(tzinfo=None) <= timedelta(minutes=10)
    notifier.tick(moved + timedelta(seconds=1))
    assert len(calls) == 2


def test_a_locked_notebook_shows_no_reminder_text(client, tmp_path, monkeypatch):
    freeze_reminder_clock(monkeypatch, notifier=True)
    calls = []
    notifier = rn.ReminderNotifier(
        rn.FiredStore(tmp_path / rn.STORE_NAME),
        "osascript",
        notebook_open=lambda session: False,
        run=lambda argv, **kw: calls.append(argv),
    )
    due = FIXED_NOW + timedelta(minutes=1)
    client.post("/reminders", json={"text": "Private", "due_at": due.isoformat()})
    notifier.tick(due.replace(tzinfo=None) + timedelta(seconds=1))
    assert calls == []


def test_several_at_once_are_one_summary_without_buttons(client, tmp_path, monkeypatch):
    freeze_reminder_clock(monkeypatch, notifier=True)
    calls = []
    notifier = rn.ReminderNotifier(
        rn.FiredStore(tmp_path / rn.STORE_NAME), "osascript", run=lambda argv, **kw: calls.append(argv)
    )
    due = FIXED_NOW + timedelta(minutes=1)
    for text in ("One", "Two", "Three"):
        client.post("/reminders", json={"text": text, "due_at": due.isoformat()})
    notifier.tick(due.replace(tzinfo=None) + timedelta(seconds=1))
    assert [argv[-2:] for argv in calls] == [["Tessellate", "3 reminders are due"]]


def test_the_session_check_is_signed_in_or_no_password(app_state, session, monkeypatch):
    from tessellate.api import routes_auth

    assert routes_auth.notebook_open(session, app_state) is True
    monkeypatch.setattr(routes_auth, "_password_set", lambda s: True)
    monkeypatch.setattr(routes_auth, "_active_tokens", {})
    assert routes_auth.notebook_open(session, app_state) is False
    # routes_auth reads `time.time()` for idle expiry: give it the fixed clock.
    epoch = FIXED_NOW.timestamp()
    monkeypatch.setattr(routes_auth, "time", SimpleNamespace(time=lambda: epoch, monotonic=time.monotonic))
    monkeypatch.setattr(routes_auth, "_active_tokens", {"t": [epoch, epoch]})
    assert routes_auth.notebook_open(session, app_state) is True


def test_the_apps_shutdown_stops_the_notifier_before_the_job_pool_waits_on_it():
    """OPEN.md (cifix5): a quit with the notifier running waited the pool's
    5 s deadline, because its loop is a pool job and only the launcher's own
    stop, run after the window was gone, told it to end."""
    from pathlib import Path

    seen: list[str] = []
    stub = SimpleNamespace(stop=lambda: seen.append("stopped"))
    rn._running["notifier"] = stub
    try:
        rn.stop_running()
        assert seen == ["stopped"]
    finally:
        rn._running["notifier"] = None
    rn.stop_running()  # nothing running: a no-op
    app = (Path(__file__).resolve().parents[1] / "src" / "tessellate" / "api" / "app.py").read_text(encoding="utf-8")
    assert app.index("reminder_notifier.stop_running()") < app.index("jobs.shutdown(deadline=_JOB_SHUTDOWN_SECONDS)")


def test_a_due_reminder_is_told_to_the_hook_once_and_early_alerts_and_locked_notebooks_are_not(client, tmp_path, monkeypatch):
    freeze_reminder_clock(monkeypatch, notifier=True)
    told = []
    notifier = rn.ReminderNotifier(
        rn.FiredStore(tmp_path / rn.STORE_NAME), "osascript", run=lambda argv, **kw: None, on_due=told.append,
    )
    due = FIXED_NOW + timedelta(minutes=1)
    rid = client.post("/reminders", json={"text": "Stretch", "due_at": due.isoformat()}).json()["id"]
    later = due.replace(tzinfo=None) + timedelta(seconds=1)
    notifier.tick(later)
    notifier.tick(later + timedelta(seconds=30))
    assert [[d.reminder_id for d in batch] for batch in told] == [[rid]]
    locked = rn.ReminderNotifier(
        rn.FiredStore(tmp_path / "other.json"), "osascript", notebook_open=lambda s: False, on_due=told.append,
    )
    locked.tick(later)
    assert len(told) == 1


def test_a_failing_hook_never_stops_the_notifier(client, tmp_path, monkeypatch):
    freeze_reminder_clock(monkeypatch, notifier=True)

    def boom(_due):
        raise RuntimeError("no companion")

    notifier = rn.ReminderNotifier(
        rn.FiredStore(tmp_path / rn.STORE_NAME), "osascript", run=lambda argv, **kw: None, on_due=boom,
    )
    due = FIXED_NOW + timedelta(minutes=1)
    client.post("/reminders", json={"text": "Stretch", "due_at": due.isoformat()})
    notifier.tick(due.replace(tzinfo=None) + timedelta(seconds=1))  # no exception
