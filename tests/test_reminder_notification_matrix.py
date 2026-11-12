"""What a due reminder produces under each notification permission (LEDGER L913).

Measured in Chromium with `window.Notification` stubbed (granted, denied,
default) and a reminder due 5 s ahead, with and without the service worker:

- granted, page only: one `new Notification("Reminder", {body: "<text>"})` and the toast;
- granted, worker: `showNotification("Reminder", ...)` with Done and Snooze 10 minutes, and the toast;
- denied or default: no system notification, the toast alone, and in `denied` the
  "Notifications are blocked." line shows.

These run the same two files, `reminder-notify.js` and `notify` in status.js,
under node with those stubs. The desktop launcher's own notification and its
due logic are in `tests/test_reminder_notifier.py`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

LAZY = (JS_DIR / "reminder-notify.js").read_text(encoding="utf-8")
STATUS = (JS_DIR / "status.js").read_text(encoding="utf-8")
NOTIFY = re.search(r"^function notify\(.*?^\}", STATUS, re.S | re.M).group(0)

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(permission: str, *, worker: bool, launcher: bool, fresh: list[dict], token: bool = True) -> dict:
    script = f"""
const log = {{ notes: [], toasts: [] }};
globalThis.window = globalThis;
class N {{
  constructor(title, opts) {{ log.notes.push({{ via: "page", title, body: opts.body }}); }}
  close() {{}}
}}
N.permission = {json.dumps(permission)};
globalThis.Notification = N;
const registration = {json.dumps(worker)} ? {{
  showNotification: async (title, opts) => log.notes.push({{ via: "worker", title, body: opts.body, tag: opts.tag, actions: opts.actions.map((a) => a.title) }}),
  getNotifications: async () => [],
}} : null;
Object.defineProperty(globalThis, "navigator", {{ value: {{ serviceWorker: {{ getRegistration: async () => registration, addEventListener() {{}} }} }}, configurable: true }});
globalThis.NOTIFICATION_AUTOCLOSE_MS = 20;
globalThis.toast = (text) => log.toasts.push(text);
globalThis.toastName = (name) => name;
globalThis.loadReminders = async () => {{}};
globalThis.switchTab = () => {{}};
globalThis.apiJson = async (url) => url === "/health" ? {{ os_notify: {json.dumps(launcher)} }} : {{ token: {json.dumps("t" if token else None)} }};
{NOTIFY}
globalThis.notify = notify;
{LAZY}
announceReminders({json.dumps(fresh)}).then(() => setTimeout(() => process.stdout.write(JSON.stringify(log)), 60));
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


ONE = [{"id": 4, "text": "Water the fern"}]


def test_granted_in_the_page_is_one_notification_and_the_toast():
    log = _run("granted", worker=False, launcher=False, fresh=ONE)
    assert log["notes"] == [{"via": "page", "title": "Reminder", "body": "Water the fern"}]
    assert log["toasts"] == ["Water the fern"]


def test_granted_with_the_worker_has_done_and_snooze_and_the_toast():
    log = _run("granted", worker=True, launcher=False, fresh=ONE)
    assert log["notes"] == [{"via": "worker", "title": "Reminder", "body": "Water the fern", "tag": "reminder-4", "actions": ["Done", "Snooze 10 minutes"]}]
    assert log["toasts"] == ["Water the fern"]


def test_without_a_scoped_token_the_notification_shows_with_no_buttons():
    log = _run("granted", worker=True, launcher=False, fresh=ONE, token=False)
    assert log["notes"][0]["actions"] == []


@pytest.mark.parametrize("permission", ["denied", "default"])
def test_denied_or_default_is_the_toast_alone(permission):
    log = _run(permission, worker=True, launcher=False, fresh=ONE)
    assert log["notes"] == []
    assert log["toasts"] == ["Water the fern"]


def test_the_desktop_launcher_posts_its_own_so_the_page_posts_none():
    log = _run("granted", worker=True, launcher=True, fresh=ONE)
    assert log["notes"] == []
    assert log["toasts"] == ["Water the fern"]


def test_several_at_once_are_one_summary_and_a_reminder_about_a_note_says_so():
    log = _run("granted", worker=False, launcher=False, fresh=[{"id": 1, "text": "A"}, {"id": 2, "text": "B"}])
    assert log["notes"] == [{"via": "page", "title": "Tessellate", "body": "2 reminders are due"}]
    about = _run("granted", worker=False, launcher=False, fresh=[{"id": 3, "text": "Call back", "target_title": "Plan"}])
    assert about["notes"][0]["body"] == "Call back\nAbout Plan"
