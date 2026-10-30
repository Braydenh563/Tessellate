"""One minute tick for every minute-level wake (audit 1028 S38).

The three clocks each chained their own timeout and the reminder check ran on
its own `setInterval`, so an idle visible minute woke the page four times for
work that is "once a minute". `startMinuteTicker` (shell-reminders.js) is now
one wall-clock-aligned chain shared by every caller, and the reminder watch
rides it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
REMINDERS = (JS / "shell-reminders.js").read_text(encoding="utf-8")
STATUS = (JS / "status.js").read_text(encoding="utf-8")


def _block(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_the_reminder_watch_rides_the_shared_minute_tick():
    body = _block(STATUS, "function startReminderWatch(", "\n}\n")
    assert "startMinuteTicker(" in body and "setInterval(" not in body


def test_no_clock_chains_its_own_timeout():
    ticker = _block(REMINDERS, "const minuteTickers", "\nlet clockTimer")
    assert ticker.count("setTimeout(") == 1, "one chain, however many painters"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_four_painters_share_one_wake_and_stopping_the_last_stops_the_chain():
    ticker = _block(REMINDERS, "const MINUTE_TICK_MARGIN_MS", "\nlet clockTimer")
    script = f"""
let now = 1_000_000_000_000 + 10_000;
const timers = [];
const setTimeout = (fn, ms) => {{ timers.push({{ fn, ms }}); return timers.length; }};
const clearTimeout = (id) => {{ timers[id - 1] = null; }};
const fire = (id) => {{ const t = timers[id - 1]; timers[id - 1] = null; t.fn(); }};
const Date = {{ now: () => now }};
{ticker}
const seen = {{ a: 0, b: 0, c: 0, d: 0 }};
const stops = ['a', 'b', 'c', 'd'].map((k) => startMinuteTicker(() => {{ seen[k] += 1; }}));
const live = () => timers.filter(Boolean).length;
const first = live();
const wait = timers[0].ms;
fire(1);
const afterTick = {{ ...seen }};
stops.slice(0, 3).forEach((stop) => stop());
fire(timers.length);
const afterThree = {{ ...seen }};
stops[3]();
const armedAfterAll = live();
console.log(JSON.stringify({{ first, wait, afterTick, afterThree, armedAfterAll }}));
"""
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["first"] == 1, "four painters, one timer"
    assert out["wait"] == 60000 - (1_000_000_010_000 % 60000) + 250, "aligned to :00.25"
    assert out["afterTick"] == {"a": 2, "b": 2, "c": 2, "d": 2}, "each painted at start and once on the tick"
    assert out["afterThree"] == {"a": 2, "b": 2, "c": 2, "d": 3}, "a stopped painter is not called again"
    assert out["armedAfterAll"] == 0, "the last painter off clears the timer"
