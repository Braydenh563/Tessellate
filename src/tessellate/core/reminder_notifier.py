"""The desktop app's own reminder notifications (WORLD_CLASS_PLAN decision 69,
TIMELINE_PLAN 11 row 3).

The page cannot be the desktop's notifier: WKWebView has no `Notification`,
pywebview answers neither WebView2's nor WebKitGTK's permission request, and
on Windows the window spends its life hidden in the tray. The launcher's
process also runs the server, so this thread reads the open reminders from
the database itself and asks the operating system to show each due time
once, with tools every machine already has (no new dependency, nothing
leaves the computer):

- Windows: a toast through PowerShell's WinRT bridge; Done and Snooze answer
  while that PowerShell waits on the toast.
- macOS: `osascript`'s `display notification` (no buttons: an Apple limit).
- Linux: `notify-send`, with buttons where libnotify reads `--action`;
  `gdbus` calling the notification service when `notify-send` is missing.

The page keeps the chime, the toast and the centre; `/health`'s `os_notify`
tells it this thread has the system notification, so it is shown once.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape as xml_escape

from tessellate.core.subproc import NO_WINDOW

logger = logging.getLogger(__name__)

APP_NAME = "Tessellate"
#: The id the launcher gives its process (`_run_desktop`) and both installers
#: give the Start menu shortcut; Windows shows a desktop app's toast only
#: under an id a shortcut carries.
APP_ID = "memorymap.desktop.app.1"
#: PowerShell's own shortcut id, for a source checkout with no installed one.
POWERSHELL_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
#: The longest the thread sleeps: a reminder made in the app while it sleeps
#: is seen within this, and the next due time sets an earlier wake.
MAX_SLEEP_S = 30.0
#: A due time older than this when first seen is not announced: a notebook
#: opened after a week away does not get a week of banners.
LOOKBACK = timedelta(hours=12)
SNOOZE = timedelta(minutes=10)
#: How long a notification's buttons are listened for.
ACTION_WAIT_S = 600
KEPT_KEYS = 200
STORE_NAME = "notified-reminders.json"
#: The running notifier, for `/health` (None: the page notifies itself).
_running: dict[str, "ReminderNotifier | None"] = {"notifier": None}
ACTIONS = (("done", "Done"), ("snooze", "Snooze 10 minutes"))


@dataclass(frozen=True)
class Due:
    """One announcement: a reminder's due time, or its early alert."""

    key: str
    reminder_id: int
    text: str
    early: bool
    #: Why it matters: the note the reminder is attached to (CHAT_PLAN 6); "" for none.
    about: str = ""


def said(due: Due) -> str:
    """The notification's words as one sentence, with why it matters: the note it hangs on (CHAT_PLAN B27)."""
    text = due.text.strip().rstrip(".")
    if not due.about or due.about == due.text:
        return due.text
    return f"{text}, from your note \u201c{due.about}\u201d."


def _naive_utc(value: datetime) -> datetime:
    return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)


def _times(reminder) -> list[tuple[str, datetime, bool]]:  # noqa: ANN001  # a Reminder row
    due = _naive_utc(reminder.due_at)
    stamp = due.isoformat(timespec="minutes")
    out = [(f"{reminder.id}@{stamp}", due, False)]
    if reminder.alert_minutes:
        out.append((f"e{reminder.id}@{stamp}", due - timedelta(minutes=reminder.alert_minutes), True))
    return out


#: What a reminder from a private space says when it fires (INBOX 1727).
PRIVATE_REMINDER = "A private reminder"


def shown_text(session, reminder) -> str:  # noqa: ANN001
    """A reminder's words for a notification: never a private space's."""
    from tessellate.entry import private_space

    return PRIVATE_REMINDER if private_space.is_private_space(session, reminder.workspace_id) else reminder.text


def due_now(
    reminders,  # noqa: ANN001
    fired: set[str],
    now: datetime,
    private_spaces: frozenset[str] = frozenset(),
    titles: dict[int, str] | None = None,
) -> tuple[list[Due], datetime | None]:
    """What to announce at `now` (naive UTC), and the next time anything is due.

    A key is the id and the due time, so a snoozed or rolled-on reminder is
    announced again at its new time, and never twice at the same one.
    """
    fresh: list[Due] = []
    upcoming: list[datetime] = []
    for reminder in reminders:
        if reminder.done:
            continue
        for key, at, early in _times(reminder):
            if at > now:
                upcoming.append(at)
            elif key not in fired and now - at <= LOOKBACK:
                text = PRIVATE_REMINDER if getattr(reminder, "workspace_id", None) in private_spaces else reminder.text
                private = text == PRIVATE_REMINDER
                about = "" if private else (titles or {}).get(getattr(reminder, "entry_id", None) or 0, "")
                fresh.append(Due(key, reminder.id, text, early, about))
    return fresh, min(upcoming, default=None)


class FiredStore:
    """The keys already announced, on disk so a restart does not repeat them."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.keys = list(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            self.keys = []

    def __contains__(self, key: str) -> bool:
        return key in self.keys

    def as_set(self) -> set[str]:
        return set(self.keys)

    def add(self, keys: list[str]) -> None:
        self.keys = [*self.keys, *keys][-KEPT_KEYS:]
        try:
            self.path.write_text(json.dumps(self.keys), encoding="utf-8")
        except OSError as exc:
            logger.warning("could not record the announced reminders: %s", exc)


# --- the commands, one per system ---------------------------------------------

def _gvariant_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _notify_send_reads_actions() -> bool:
    try:
        shown = subprocess.run(
            ["notify-send", "--help"], capture_output=True, text=True, timeout=5, check=False,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "--action" in shown.stdout and "--wait" in shown.stdout


def pick_backend(platform: str = sys.platform, which=shutil.which) -> str | None:  # noqa: ANN001
    """The notifier this machine has, or None (the page then keeps the job)."""
    if platform == "win32":
        return "powershell" if which("powershell") else None
    if platform == "darwin":
        return "osascript" if which("osascript") else None
    if which("notify-send"):
        return "notify-send"
    if which("gdbus"):
        return "gdbus"
    return None


_TOAST_SCRIPT = (
    "$ErrorActionPreference = 'Stop';"
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
    "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
    "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; $xml.LoadXml($env:MM_TOAST_XML);"
    "$toast = New-Object Windows.UI.Notifications.ToastNotification $xml;"
    "Register-ObjectEvent -InputObject $toast -EventName Activated -SourceIdentifier mmAct | Out-Null;"
    "Register-ObjectEvent -InputObject $toast -EventName Dismissed -SourceIdentifier mmGone | Out-Null;"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:MM_TOAST_APP).Show($toast);"
    "$e = Wait-Event -Timeout " + str(ACTION_WAIT_S) + ";"
    "if ($e -and $e.SourceIdentifier -eq 'mmAct') {"
    " try { [Console]::Out.WriteLine(([Windows.UI.Notifications.ToastActivatedEventArgs]$e.SourceEventArgs).Arguments) }"
    " catch { [Console]::Out.WriteLine('open') } }"
)


def toast_xml(title: str, body: str, with_actions: bool) -> str:
    buttons = "".join(
        f'<action content="{label}" arguments="{key}" activationType="foreground"/>'
        for key, label in ACTIONS
    )
    return (
        '<toast launch="open" activationType="foreground"><visual><binding template="ToastGeneric">'
        f"<text>{xml_escape(title)}</text><text>{xml_escape(body)}</text></binding></visual>"
        + (f"<actions>{buttons}</actions>" if with_actions else "")
        + "</toast>"
    )


def build_command(
    backend: str,
    title: str,
    body: str,
    *,
    with_actions: bool,
    icon: str | None = None,
    send_reads_actions: bool = False,
    frozen: bool = False,
) -> tuple[list[str], dict[str, str], bool]:
    """(argv, extra environment, whether stdout names a pressed button).

    The text is passed as arguments or environment, never spliced into a
    script, so a reminder's words cannot become code.
    """
    if backend == "powershell":
        env = {
            "MM_TOAST_XML": toast_xml(title, body, with_actions),
            "MM_TOAST_APP": APP_ID if frozen else POWERSHELL_APP_ID,
        }
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _TOAST_SCRIPT]
        return argv, env, True
    if backend == "osascript":
        argv = [
            "osascript",
            "-e", "on run argv",
            "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
            "-e", "end run",
            title,
            body,
        ]
        return argv, {}, False
    if backend == "notify-send":
        argv = ["notify-send", f"--app-name={APP_NAME}"]
        if icon:
            argv.append(f"--icon={icon}")
        listens = send_reads_actions
        if listens:
            argv += ["--action=default=Open"]
            if with_actions:
                argv += [f"--action={key}={label}" for key, label in ACTIONS]
            argv.append("--wait")
        return [*argv, "--", title, body], {}, listens
    if backend == "gdbus":
        argv = [
            "gdbus", "call", "--session",
            "--dest", "org.freedesktop.Notifications",
            "--object-path", "/org/freedesktop/Notifications",
            "--method", "org.freedesktop.Notifications.Notify",
            _gvariant_string(APP_NAME), "0", _gvariant_string(icon or ""),
            _gvariant_string(title), _gvariant_string(body), "[]", "{}", "-1",
        ]
        return argv, {}, False
    raise ValueError(f"unknown notifier: {backend}")


def local_offset_minutes() -> int:
    offset = datetime.now().astimezone().utcoffset()
    return int(offset.total_seconds() // 60) if offset else 0


# --- the thread -----------------------------------------------------------------

def _open_reminders(session) -> list:  # noqa: ANN001
    from sqlalchemy import select

    from tessellate.core.database import Reminder

    return list(session.scalars(select(Reminder).where(Reminder.done.is_(False)).order_by(Reminder.due_at)))


def _entry_titles(session, reminders) -> dict[int, str]:  # noqa: ANN001
    """The titles of the notes open reminders hang on, for the "About" line."""
    from sqlalchemy import select

    from tessellate.core.database import Entry

    ids = {r.entry_id for r in reminders if getattr(r, "entry_id", None)}
    if not ids:
        return {}
    return {e.id: e.title for e in session.scalars(select(Entry).where(Entry.id.in_(ids))) if e.title}


def _notebook_open(session) -> bool:  # noqa: ANN001
    """Signed in (or no password yet): a locked notebook shows no reminder text."""
    from tessellate.api import routes_auth
    from tessellate.core import deps

    return routes_auth.notebook_open(session, deps.get_config())


def apply_action(reminder_id: int, action: str) -> None:
    """Done or Snooze from a notification, through the routes' own code, so a
    repeating reminder rolls on exactly as the app's Done does."""
    from tessellate.api import routes_reminders as rr
    from tessellate.core import deps

    db = deps.peek_db()
    if db is None:
        return
    session = db.session()
    try:
        if action == "done":
            # `expected_due_at` is a Query default, truthy when the route is called as a
            # function; None says no occurrence was named (b9f90aa made it a 409 otherwise).
            rr.complete_reminder(
                reminder_id, tz_offset_minutes=local_offset_minutes(), expected_due_at=None, session=session
            )
        elif action == "snooze":
            when = datetime.now(timezone.utc) + SNOOZE
            rr.update_reminder(reminder_id, rr.ReminderUpdate(due_at=when, done=False), session=session)
    finally:
        session.close()


class ReminderNotifier:
    def __init__(
        self,
        store: FiredStore,
        backend: str,
        *,
        on_open: Callable[[], None] | None = None,
        icon: str | None = None,
        on_due: Callable[[list[Due]], None] | None = None,
        session_source: Callable[[], object] | None = None,
        notebook_open: Callable[[object], bool] = _notebook_open,
        act: Callable[[int, str], None] = apply_action,
        run=subprocess.run,  # noqa: ANN001
    ) -> None:
        self.store = store
        self.backend = backend
        self.on_open = on_open
        self.icon = icon
        #: Told of each batch of reminders that just fell due (not the early alerts),
        #: after the notification is posted: the desktop companion fetches a card.
        self.on_due = on_due
        self.session_source = session_source or self._default_session
        self.notebook_open = notebook_open
        self.act = act
        self.run = run
        self.send_reads_actions = backend == "notify-send" and _notify_send_reads_actions()
        self.frozen = bool(getattr(sys, "frozen", False))
        self.stopped = threading.Event()
        #: Notifications whose buttons are being listened for: (process,
        #: give-up time, reminder id). Polled by the loop itself, so a
        #: waiting notification holds no thread of its own.
        self.listening: list[tuple[subprocess.Popen, float, int | None]] = []

    @staticmethod
    def _default_session():
        from tessellate.core import deps

        db = deps.peek_db()
        return db.session() if db is not None else None

    def tick(self, now: datetime | None = None) -> float:
        """One look: announce what is due, return how long to sleep."""
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        session = self.session_source()
        if session is None:
            return MAX_SLEEP_S
        try:
            if not self.notebook_open(session):
                return MAX_SLEEP_S
            from tessellate.entry import private_space

            hidden = frozenset(private_space.private_space_ids(session))
            open_now = _open_reminders(session)
            fresh, upcoming = due_now(open_now, self.store.as_set(), now, hidden, _entry_titles(session, open_now))
        finally:
            session.close()
        if fresh:
            self.store.add([d.key for d in fresh])
            self.announce(fresh)
            self._tell_due([d for d in fresh if not d.early])
        if upcoming is None:
            return MAX_SLEEP_S
        return max(0.25, min(MAX_SLEEP_S, (upcoming - now).total_seconds() + 0.25))

    def _tell_due(self, due: list[Due]) -> None:
        if due:
            from tessellate.core import companion_events

            companion_events.record("reminder_bell")  # a kind and a time for the desk companion, whatever the hook (W31)
        if not due or self.on_due is None:
            return
        try:
            self.on_due(due)
        except Exception as exc:  # noqa: BLE001  # a card is never worth the notifier
            logger.warning("the due-reminder hook failed: %s", exc)

    def announce(self, fresh: list[Due]) -> None:
        if len(fresh) == 1:
            due = fresh[0]
            title = "Coming up" if due.early else "Reminder"
            self.post(title, said(due), None if due.early else due.reminder_id)
        else:
            self.post(APP_NAME, f"{len(fresh)} reminders are due", None)

    def post(self, title: str, body: str, reminder_id: int | None) -> None:
        argv, extra, listens = build_command(
            self.backend,
            title,
            body,
            with_actions=reminder_id is not None,
            icon=self.icon,
            send_reads_actions=self.send_reads_actions,
            frozen=self.frozen,
        )
        if listens:
            self._listen(argv, extra, reminder_id)
        else:
            self._spawn(argv, extra, wait=10)

    def _spawn(self, argv: list[str], extra: dict[str, str], wait: float):
        try:
            return self.run(
                argv, env={**os.environ, **extra}, capture_output=True, text=True,
                timeout=wait, check=False, creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("the reminder notification did not show: %s", exc)
            return None

    def _listen(self, argv: list[str], extra: dict[str, str], reminder_id: int | None) -> None:
        try:
            proc = subprocess.Popen(  # noqa: S603  # argv is built by build_command, never from a shell string
                argv, env={**os.environ, **extra}, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("the reminder notification did not show: %s", exc)
            return
        self.listening.append((proc, time.monotonic() + ACTION_WAIT_S + 30, reminder_id))

    def collect(self) -> None:
        """Apply the button of each notification that has ended, and give up
        on one nobody answered."""
        waiting = []
        for proc, give_up, reminder_id in self.listening:
            if proc.poll() is None and time.monotonic() < give_up:
                waiting.append((proc, give_up, reminder_id))
                continue
            if proc.poll() is None:
                proc.kill()
            try:
                answer = (proc.stdout.read() if proc.stdout else "").strip().splitlines()
            except (OSError, ValueError):
                answer = []
            finally:
                if proc.stdout:
                    proc.stdout.close()
                proc.wait()
            self.answer(answer[-1] if answer else "", reminder_id)
        self.listening = waiting

    def answer(self, action: str, reminder_id: int | None) -> None:
        try:
            if action in ("done", "snooze") and reminder_id is not None:
                self.act(reminder_id, action)
            elif action in ("default", "open") and self.on_open:
                self.on_open()
        except Exception as exc:  # noqa: BLE001  # a button is not worth the thread
            logger.warning("the notification's %s did not apply: %s", action, exc)

    def loop(self) -> None:
        """Runs as a job on the pool's `notify` lane, until `stop`."""
        try:
            while not self.stopped.is_set():
                try:
                    wait = self.tick()
                    self.collect()
                except Exception as exc:  # noqa: BLE001  # the next look may work
                    logger.warning("reminder check failed: %s", exc)
                    wait = MAX_SLEEP_S
                #: A notification being listened for is looked at every second, so a
                #: button answers promptly.
                self.stopped.wait(min(wait, 1.0) if self.listening else wait)
        finally:
            for proc, _, _ in self.listening:
                proc.kill()
            self.listening = []

    def start(self) -> "ReminderNotifier":
        from tessellate.core import jobs

        jobs.enqueue("reminder-notifier", self.loop, name="reminder notifier")
        return self

    def stop(self) -> None:
        self.stopped.set()
        if _running["notifier"] is self:
            _running["notifier"] = None


def stop_running() -> None:
    """Stop this process's notifier, if one runs. The app's shutdown calls it
    before the job pool's, because the notifier's loop is a job on that pool:
    left to the launcher's own stop (which runs once the window is gone) a
    quit waited the pool's whole deadline for a loop nothing had told to end."""
    notifier = _running["notifier"]
    if notifier is not None:
        notifier.stop()


def active() -> bool:
    """Whether this process posts the system notification for a due reminder."""
    return _running["notifier"] is not None


def start(
    data_dir: Path,
    *,
    on_open: Callable[[], None] | None = None,
    icon: str | None = None,
    on_due: Callable[[list[Due]], None] | None = None,
):
    """The launcher's entry: None when this machine has no notifier, in which
    case `/health` says so and the page posts its own notification."""
    backend = pick_backend()
    if backend is None:
        logger.info("no system notifier found; the page will notify while it is open")
        return None
    notifier = ReminderNotifier(
        FiredStore(Path(data_dir) / STORE_NAME), backend, on_open=on_open, icon=icon, on_due=on_due
    )
    _running["notifier"] = notifier
    return notifier.start()
