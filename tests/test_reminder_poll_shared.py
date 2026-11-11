"""One reminders poll for every tab, none while hidden (audit 1031 BK12).

Each tab used to ask `/reminders` once a minute, hidden or not. The tick,
focus and return checks now go through `pollReminders`: a poll only if
no tab has asked in the last 45 s (a Web Lock makes the claim atomic, a shared
timestamp is the memory), and the answer is handed to the other tabs over a
BroadcastChannel. A hidden tab's minute tick is stopped.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATUS = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "status.js").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    i = STATUS.index(start)
    return STATUS[i : STATUS.index(end, i)]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_ten_tabs_ticking_together_make_one_poll_a_minute():
    shared = _block("function pollReminders", "//: What every tab does")
    script = (
        """
let now = 1_000_000_000_000;
const store = {};
const prefs = { get: (k, d) => (k in store ? store[k] : d), set: (k, v) => { store[k] = v; } };
const Date = { now: () => now };
let held = false, polls = 0;
const navigator = { locks: { request: async (name, opts, fn) => {
  if (held && opts.ifAvailable) return fn(null);
  held = true;
  try { return await fn({}); } finally { held = false; }
} } };
const REMINDER_POLL_MS = 60000;
// the real poll stamps the shared time before it asks (checked below)
const checkDueReminders = async () => { prefs.set("reminderPolledAt", Date.now()); polls += 1; await new Promise((r) => setTimeout(r, 5)); };
"""
        + shared
        + """
(async () => {
  const tabs = 10;
  await Promise.all(Array.from({ length: tabs }, () => pollReminders()));
  const first = polls;                       // ten tabs ticking in the same instant
  now += 30_000;
  await Promise.all(Array.from({ length: tabs }, () => pollReminders()));
  const half = polls;                        // a focus half a minute later
  now += 31_000;
  await Promise.all(Array.from({ length: tabs }, () => pollReminders()));
  console.log(JSON.stringify({ first, half, next: polls }));
})();
"""
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == {"first": 1, "half": 1, "next": 2}, out


def test_the_poll_stamps_before_it_asks_and_the_others_only_paint():
    body = re.search(r"(?ms)^async function checkDueReminders\(\).*?\n\}", STATUS).group(0)
    assert body.index("reminderPolledAt") < body.index('"/reminders/due"')  # K32: the small look and the list both come after the stamp
    assert "postMessage(all)" in body
    told = STATUS[STATUS.index("reminderChannel.onmessage = ") :].split("\n", 1)[0]
    assert "paintReminderList(" in told and "announce" not in told.lower()


def test_a_hidden_tab_stops_its_minute_tick_and_a_return_restarts_it():
    watch = _block("function startReminderWatch(", "\n}\n")
    hidden = watch[watch.index('addEventListener("visibilitychange"') :]
    assert "reminderDueTimer.stop?.()" in hidden and "document.hidden ? null : startMinuteTicker(tick)" in hidden
    assert "reminderDueTimer.stop = document.hidden ? null : startMinuteTicker(tick);" in watch.split("window.addEventListener")[0]
    assert "setInterval(" not in watch
    # tick, focus and return all go through the shared check, never a bare poll
    assert "pollReminders()" in watch and 'addEventListener("focus", pollReminders)' in watch
    assert not re.search(r"(?<!Shared)checkDueReminders\(\);", watch[watch.index("if (reminderWatchStarted)") :])
