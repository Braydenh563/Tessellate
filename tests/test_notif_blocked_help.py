"""The blocked-notifications line and its help (LEDGER L914, parts b and c).

Measured in Chromium with `Notification.permission` "denied": the line "Notifications are blocked."
is in the Reminders tab and in Settings, and its question mark opens the help
with one paragraph each for Chrome and Edge, Firefox, Safari and the desktop app.
Both lines are built lazily, so the sync has to run when each surface is built;
before this the Reminders line stayed hidden until the next minute's poll.
Hidden-tab firing: a due reminder fires its notification with the tab hidden
(`document.visibilityState` overridden, `visibilitychange` dispatched), because
the due-time timer, not the minute tick, is what fires it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

STATUS = (JS_DIR / "status.js").read_text(encoding="utf-8")
INDEX = (JS_DIR.parent / "index.html").read_text(encoding="utf-8")


def test_the_line_is_synced_when_the_reminders_tab_and_settings_are_built():
    assert 'onSurface("settings", syncNotifBlocked);' in STATUS
    assert 'onSurface("reminders", syncNotifBlocked);' in STATUS


@pytest.mark.parametrize("target", ["reminders-notif-help", "settings-notif-help"])
def test_the_help_names_every_browser_and_the_desktop_app(target):
    body = re.search(rf'id="{target}".*?</div>', INDEX, re.S).group(0)
    for words in (
        "only the system notification is off",
        "Chrome and Edge: the icon left of the address, then Notifications, Allow.",
        "Firefox: the icon left of the address, then clear Notifications blocked, and reload.",
        "Safari: its own Settings (Websites, then Notifications), then Allow for this site.",
        "The desktop app: your system's notification settings for Tessellate.",
    ):
        assert words in body


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(("permission", "shown"), [("denied", True), ("granted", False), ("default", False)])
def test_only_denied_shows_the_line(permission, shown):
    fn = re.search(r"^function syncNotifBlocked\(.*?^\}", STATUS, re.S | re.M).group(0)
    script = f"""
globalThis.window = globalThis;
globalThis.Notification = {{ permission: {json.dumps(permission)} }};
const line = {{ hidden: true, classList: {{ toggle(c, on) {{ line.hidden = on; }} }} }};
globalThis.document = {{ querySelectorAll: () => [line] }};
{fn}
syncNotifBlocked();
process.stdout.write(JSON.stringify(!line.hidden));
"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) is shown


def test_a_hidden_tab_keeps_its_due_timer_and_coming_back_asks_at_once():
    watch = re.search(r"^function startReminderWatch\(.*?^\}", STATUS, re.S | re.M).group(0)
    handler = re.search(r'addEventListener\("visibilitychange", \(\) => \{.*?\n  \}\);', watch, re.S).group(0)
    #: Only the minute tick is stopped while hidden; the due-time timeout is not touched.
    assert "reminderDueTimer.stop?.()" in handler and "clearTimeout" not in handler
    assert "document.hidden ? null : startMinuteTicker(tick)" in handler
    #: The timer fires the check itself, hidden or not (measured: notification with visibilityState hidden).
    assert "reminderDueTimer.id = setTimeout(checkDueReminders" in STATUS
