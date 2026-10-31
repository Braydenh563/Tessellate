"""Audit 1029 X14: timers keep their end time, several can run, and they
come back after a reload. The clock code runs in node with stubs and a
fixed clock; nothing here reads the real time."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "frontend/js/utility-tools.js").read_text(encoding="utf-8")
CLOCK_PART = SRC[: SRC.index("//: The text a palette command acts on")]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = r"""
const vm = require("vm");
const store = new Map(Object.entries(__STORED__));
let now = __NOW__;
const toasts = [];
const notes = [];
const undos = [];
const chip = { classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); } },
  title: "", attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, addEventListener() {} };
const timers = new Map();
let nextTimer = 1;
const sandbox = {
  $: () => chip,
  setLabel: (el, text) => { chip.label = text; },
  toast: (t) => toasts.push(t),
  //: A stop is offered back (audit 1031 Z2); the stub keeps the closures.
  offerUndo: (label, message, undo, redo) => { toasts.push(message); undos.push({ label, undo, redo }); },
  notify: (a, b) => notes.push(b),
  askNotificationPermission() {},
  prefs: {
    json: (k, d) => { try { return store.has(k) ? JSON.parse(store.get(k)) : d; } catch { return d; } },
    set: (k, v) => { store.set(k, String(v)); return true; },
    has: (k) => store.has(k),
    remove: (k) => store.delete(k),
  },
  setInterval: (fn) => { const id = nextTimer++; timers.set(id, fn); return id; },
  clearInterval: (id) => timers.delete(id),
  //: The one-shot wake at the soonest end (audit 1030 Y6); the test drives
  //: the clock itself, so it never fires.
  setTimeout: () => nextTimer++,
  clearTimeout: () => {},
  document: { addEventListener() {} },
  Date: { now: () => now },
  Math, Number, String, Object, Array, JSON,
};
vm.createContext(sandbox);
vm.runInContext(__CODE__, sandbox);
const run = (src) => vm.runInContext(src, sandbox);
const tick = () => { for (const fn of [...timers.values()]) fn(); };
const out = (extra) => console.log(JSON.stringify({ toasts, notes, label: chip.label, title: chip.title, hidden: chip.classList._s.has("hidden"), stored: store.get("utility-clocks") || null, intervals: timers.size, ...extra }));
__BODY__
"""


def _run(body: str, stored: dict | None = None, now: int = 1_000_000):
    script = (
        HARNESS.replace("__STORED__", json.dumps(stored or {}))
        .replace("__NOW__", str(now))
        .replace("__CODE__", json.dumps(CLOCK_PART))
        .replace("__BODY__", body)
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_a_second_timer_does_not_replace_the_first():
    got = _run("run('startUtilityTimer(10)'); now += 1000; run('startUtilityTimer(5)'); out({n: run('utilityClocks.length')});")
    assert got["n"] == 2
    assert got["intervals"] == 1, "one wake source for all of them"
    saved = json.loads(got["stored"])
    assert len(saved) == 2 and {c["end"] for c in saved} == {1_000_000 + 600_000, 1_001_000 + 300_000}


def test_the_chip_shows_the_soonest_and_says_how_many():
    got = _run("run('startUtilityTimer(10)'); run('startUtilityTimer(5)'); out();")
    assert "05:00" in got["label"]
    assert "2 timers" in got["title"]


def test_the_time_comes_from_the_clock_not_from_ticks():
    got = _run("run('startUtilityTimer(1)'); now += 59_000; tick(); out();")
    assert "00:01" in got["label"], "a throttled tab that ticked once still reads true"
    assert "Time is up: the 1 minute timer has finished." not in got["toasts"]


def test_a_timer_that_ran_out_while_hidden_is_announced_once():
    got = _run("run('startUtilityTimer(1)'); now += 600_000; tick(); tick(); out();")
    assert got["toasts"].count("Time is up: the 1 minute timer has finished.") == 1
    assert len(got["notes"]) == 1
    assert got["intervals"] == 0 and got["hidden"] is True
    assert got["stored"] is None, "nothing left to restore"


def test_timers_are_restored_on_boot_and_expired_ones_are_announced():
    stored = {
        "utility-clocks": json.dumps(
            [
                {"id": "a", "kind": "timer", "name": "10 minute", "start": 900_000, "end": 1_300_000},
                {"id": "b", "kind": "timer", "name": "1 minute", "start": 900_000, "end": 950_000},
            ]
        )
    }
    got = _run("run('utilityRestore()'); out({n: run('utilityClocks.length')});", stored=stored)
    assert got["n"] == 1
    assert "05:00" in got["label"]
    assert got["toasts"] == ["Time is up: the 1 minute timer has finished."]
    assert got["intervals"] == 1


def test_a_bad_stored_value_is_ignored():
    got = _run("run('utilityRestore()'); out({n: run('utilityClocks.length')});", stored={"utility-clocks": "{nope"})
    assert got["n"] == 0


def test_stopping_stops_the_shown_one_only():
    got = _run("run('startUtilityTimer(10)'); run('startUtilityTimer(5)'); run('stopUtilityClock()'); out({n: run('utilityClocks.length')});")
    assert got["n"] == 1 and "10:00" in got["label"]


def test_boot_asks_for_the_module_only_when_something_is_stored():
    boot = (ROOT / "frontend/js/spaces-find.js").read_text(encoding="utf-8")
    assert 'prefs.has("utility-clocks")' in boot and 'ensureModule("utilities")' in boot


def test_a_stopped_timer_is_offered_back_with_the_time_it_had_left():
    """Audit 1031 Z2: the chip stops a clock on one press, so the stop has an Undo."""
    got = _run(
        "run('startUtilityTimer(25)'); now += 60_000; run('stopUtilityClock()');"
        "const stopped = run('utilityClocks.length'); const offer = undos[0].label;"
        "now += 120_000; undos[0].undo();"
        "const back = run('utilityClocks.length'); const end = run('utilityClocks[0].end');"
        "undos[0].redo(); out({stopped, offer, back, end, after: run('utilityClocks.length')});"
    )
    assert got["stopped"] == 0 and got["back"] == 1 and got["after"] == 0
    assert got["offer"] == "Stop timer"
    assert got["end"] == 1_000_000 + 60_000 + 120_000 + 24 * 60_000, "restored with 24:00 left, not 22:00"
    assert "Timer stopped with 24:00 left." in got["toasts"]


def test_a_stopped_stopwatch_resumes_from_what_it_had_counted():
    got = _run(
        "run('startStopwatch()'); now += 30_000; run('stopUtilityClock()');"
        "now += 90_000; undos[0].undo(); now += 5_000;"
        "out({shown: run('utilityClockSeconds(utilityClocks[0])')});"
    )
    assert got["shown"] == 35
