"""INBOX 1551 (the owner): "I pressed 'start a timer' and it did nothing, is
there a timer/stopwatch/alarm window and also maybe that could be integrated
with the dashboard and reminders etc and clock idk. also the stopwatch option
didnt open either".

The Start a timer and Start a stopwatch rows (`POPUP_TOOLS`) started a clock
on the status bar and toasted, though the "/" menu says "opens a panel". They
open one Clock panel now (`openClockPanel`, utility-tools.js) on `openSheet`
with `modal: false`, so `panelMovable` drags, resizes and docks it. The clock
code runs in node with stubs and a fixed clock; nothing here reads the real
time."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
SRC = (JS / "utility-tools.js").read_text(encoding="utf-8")
CLOCK_PART = SRC[: SRC.index("//: The text a palette command acts on")]

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

HARNESS = r"""
const vm = require("vm");
const store = new Map(Object.entries(__STORED__));
let now = __NOW__;
const toasts = [], notes = [], opened = [], chimes = [], handlers = {};
const chip = { classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); } },
  title: "", attrs: {}, setAttribute(k, v) { this.attrs[k] = v; },
  addEventListener(type, fn) { handlers[type] = fn; } };
const timers = new Map();
let nextTimer = 1;
class FakeDate extends Date {
  constructor(...a) { if (a.length) super(...a); else super(now); }
  static now() { return now; }
}
const sandbox = {
  prefsCache: {}, clockOptions: () => ({}), authToken: () => 'token', performance: { now: () => 1000 },
  $: (id) => (id === 'lock-overlay' ? null : chip),
  setLabel: (el, text) => { chip.label = text; },
  toast: (t) => toasts.push(t),
  offerUndo: () => {},
  notify: (a, b) => notes.push(b),
  askNotificationPermission() {},
  //: The dashboard's chime (dashboard.js), played at the end of a timer.
  focusChime: () => chimes.push(now),
  //: What the chip, the rows and the palette ask for.
  openClockPanel: (tab) => opened.push(tab || "timer"),
  prefs: {
    json: (k, d) => { try { return store.has(k) ? JSON.parse(store.get(k)) : d; } catch { return d; } },
    bool: (k, d) => (store.has(k) ? store.get(k) === "1" : d),
    set: (k, v) => { store.set(k, String(v)); return true; },
    has: (k) => store.has(k),
    get: (k, d) => (store.has(k) ? store.get(k) : d),
    remove: (k) => store.delete(k),
  },
  setInterval: (fn) => { const id = nextTimer++; timers.set(id, fn); return id; },
  clearInterval: (id) => timers.delete(id),
  setTimeout: () => nextTimer++,
  clearTimeout: () => {},
  document: { addEventListener() {} },
  Date: FakeDate,
  Math, Number, String, Object, Array, JSON, Infinity, isFinite,
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(__CODE__, sandbox);
const run = (src) => vm.runInContext(src, sandbox);
const tick = () => { for (const fn of [...timers.values()]) fn(); };
const out = (extra) => console.log(JSON.stringify({ toasts, notes, opened, chimes, label: chip.label, title: chip.title, hidden: chip.classList._s.has("hidden"), stored: store.get("utility-clocks") || null, ...extra }));
__BODY__
"""


def _run(body: str, stored: dict | None = None, now: int = 1_700_000_000_000):
    script = (
        HARNESS.replace("__STORED__", json.dumps(stored or {}))
        .replace("__NOW__", str(now))
        .replace("__CODE__", json.dumps(CLOCK_PART))
        .replace("__BODY__", body)
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, env={"TZ": "UTC", "PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


# --- the rows open the panel -------------------------------------------------

def _tools_open(which: str) -> list:
    """Run the real `open` of a `POPUP_TOOLS` row with `ensureModule` and the
    panel stubbed, and say what was asked for."""
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    registry = "const POPUP_TOOLS = [" + panes.split("const POPUP_TOOLS = [", 1)[1].split("\n];", 1)[0] + "\n];"
    script = (
        "const vm = require('vm'); const asked = [];"
        "const sandbox = { asked, ensureModule: (name) => { asked.push('module:' + name); return Promise.resolve(); },"
        " openClockPanel: (tab) => asked.push('panel:' + tab), startUtilityTimer: () => asked.push('started'), startStopwatch: () => asked.push('started') };"
        "vm.createContext(sandbox);"
        f"vm.runInContext({json.dumps(registry + chr(10) + 'globalThis.POPUP_TOOLS = POPUP_TOOLS;')}, sandbox);"
        f"const tool = sandbox.POPUP_TOOLS.find((t) => t.id === {json.dumps(which)});"
        "Promise.resolve(tool.open()).then(() => new Promise((r) => setTimeout(r, 5))).then(() => console.log(JSON.stringify(asked)));"
    )
    done = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


@needs_node
def test_the_slash_row_start_a_timer_opens_the_clock_panel():
    assert _tools_open("timer") == ["module:utilities", "panel:timer"]


@needs_node
def test_the_slash_row_start_a_stopwatch_opens_the_clock_panel():
    assert _tools_open("stopwatch") == ["module:utilities", "panel:stopwatch"]


@needs_node
def test_a_set_an_alarm_row_opens_the_alarm_tab():
    assert _tools_open("alarm") == ["module:utilities", "panel:alarm"]


def test_chat_s_slash_menu_runs_the_row_and_says_it_opens_a_panel():
    editor = (JS / "editor.js").read_text(encoding="utf-8")
    # `tool.open(` takes the chat field as its target for the Diagram builder (1588), so the call has an argument now
    assert 'hint: "opens a panel"' in editor and "afterPress(() => tool.open(" in editor


def test_the_palette_timer_rows_open_the_panel_too():
    palette = _js_scope.unwrapped((JS / "app-palette.js").read_text(encoding="utf-8"))
    row = palette[palette.index("function utilityPaletteRows"):][:1800]
    assert "openClockPanel" in row and "startUtilityTimer(minutes)" in row, "a typed length starts that timer and shows it"
    assert "opens the Clock" in row.split("run:")[0], "the row says where the timer shows"


@needs_node
def test_pressing_the_chip_opens_the_panel_and_no_longer_only_stops_the_clock():
    got = _run("run('startUtilityTimer(10)'); handlers.click(); out({n: run('utilityClocks.length')});")
    assert got["opened"] == ["timer"] and got["n"] == 1, "a press on the chip leaves the clock running"


@needs_node
def test_pressing_a_stopwatch_chip_opens_the_stopwatch_tab_and_never_stops_it():
    """The owner (INBOX 1551, a screenshot of "Stopwatch stopped at 1:13:25. Undo"):
    "I clicked it and it just stoped. I wanted a panel to show so I could pause it
    or lap it or reset it". A press on the chip is a way into the panel."""
    got = _run("run('startStopwatch()'); now += 5_000; handlers.click(); out({n: run('utilityClocks.length'), paused: run('utilityClocks[0].paused')});")
    assert got["opened"] == ["stopwatch"], "the stopwatch's own tab, not the timer's"
    assert got["n"] == 1 and got.get("paused") is None, "still running"
    assert not [t for t in got["toasts"] if "stopped" in t.lower()], "no Stopwatch stopped toast"


@needs_node
def test_pressing_a_timer_chip_opens_the_timer_tab_and_never_stops_it():
    got = _run("run('startUtilityTimer(10)'); handlers.click(); out({n: run('utilityClocks.length')});")
    assert got["opened"] == ["timer"] and got["n"] == 1
    assert not [t for t in got["toasts"] if "stopped" in t.lower()]


@needs_node
def test_reset_puts_a_stopwatch_back_to_zero_and_a_timer_back_to_its_length_held():
    got = _run(
        "run('startStopwatch()'); now += 65_400; run('utilityOps.lap(utilityClocks[0])');"
        "run('utilityOps.reset(utilityClocks[0])');"
        "const watch = {secs: run('utilityClockSeconds(utilityClocks[0])'), laps: run('utilityClocks[0].laps ?? null'), paused: run('utilityClocks[0].paused')};"
        "now += 30_000; const watchLater = run('utilityClockSeconds(utilityClocks[0])');"
        "run('utilityOps.play(utilityClocks[0])'); now += 2_000; const watchGoing = run('utilityClockSeconds(utilityClocks[0])');"
        "run('startUtilityTimer(10)'); now += 60_000; run('utilityOps.reset(utilityClocks[1])');"
        "const timer = {secs: run('utilityClockSeconds(utilityClocks[1])'), paused: run('utilityClocks[1].paused')};"
        "now += 3_600_000; tick();"
        "out({watch, watchLater, watchGoing, timer, finished: toasts.filter((t) => t.startsWith('Time is up')).length});"
    )
    assert got["watch"] == {"secs": 0, "laps": None, "paused": 0}, "zero, no laps, held"
    assert got["watchLater"] == 0, "held at zero until Resume"
    assert got["watchGoing"] == 2, "Resume counts from zero"
    assert got["timer"] == {"secs": 600, "paused": 600_000}, "the whole length, held"
    assert got["finished"] == 0, "a held timer never runs out"


def test_every_clock_row_has_a_reset_button():
    row = SRC[SRC.index("function clockRow(id)"):][:1800]
    assert '"ph:arrow-counter-clockwise"' in row and "utilityOps.reset(" in row


# --- pause, resume, laps, several at once --------------------------------------

@needs_node
def test_a_timer_pauses_holds_its_time_and_resumes_from_it():
    got = _run(
        "run('startUtilityTimer(10)'); now += 60_000; const c = run('utilityClocks[0]');"
        "run('utilityOps.pause(utilityClocks[0])'); const held = run('utilityClockSeconds(utilityClocks[0])');"
        "now += 3_600_000; tick(); const still = run('utilityClockSeconds(utilityClocks[0])');"
        "const finished = toasts.filter((t) => t.startsWith('Time is up')).length;"
        "run('utilityOps.play(utilityClocks[0])'); const end = run('utilityClocks[0].end');"
        "out({held, still, finished, end, at: now});"
    )
    assert got["held"] == 540 and got["still"] == 540, "9:00 left, paused for an hour"
    assert got["finished"] == 0 and got["notes"] == []
    assert got["end"] == got["at"] + 540_000


@needs_node
def test_a_stopwatch_pauses_and_resumes_and_laps_record_the_elapsed_time():
    got = _run(
        "run('startStopwatch()'); now += 65_400; run('utilityOps.lap(utilityClocks[0])');"
        "now += 10_000; run('utilityOps.lap(utilityClocks[0])');"
        "run('utilityOps.pause(utilityClocks[0])'); now += 500_000; run('utilityOps.play(utilityClocks[0])'); now += 1_000;"
        "out({laps: run('utilityClocks[0].laps'), secs: run('utilityClockSeconds(utilityClocks[0])')});"
    )
    assert got["laps"] == [65_400, 75_400]
    assert got["secs"] == 76, "paused time is not counted"


@needs_node
def test_several_clocks_run_at_once_and_each_is_kept_across_a_reload():
    got = _run(
        "run('startUtilityTimer(10)'); run('startUtilityTimer(5)'); run('startStopwatch()'); run('startStopwatch()');"
        "run('utilityOps.pause(utilityClocks[1])'); out({n: run('utilityClocks.length'), ids: new Set(run('utilityClocks.map((c) => c.id)')).size});"
    )
    assert got["n"] == 4 and got["ids"] == 4
    saved = json.loads(got["stored"])
    back = _run("run('utilityRestore()'); out({n: run('utilityClocks.length'), paused: run('utilityClocks.map((c) => c.paused ?? null)')});", stored={"utility-clocks": json.dumps(saved)}, now=1_700_000_030_000)
    assert back["n"] == 4 and sum(p is not None for p in back["paused"]) == 1


@needs_node
def test_paused_state_and_laps_come_back_and_bad_ones_are_dropped():
    clocks = [
        {"id": "a", "kind": "stopwatch", "name": "Stopwatch", "start": 0, "end": 0, "paused": 5000, "laps": [1000, "x", 4000]},
        {"id": "b", "kind": "timer", "name": "5 minute", "start": 0, "end": 1_700_000_300_000, "paused": "soon"},
    ]
    got = _run("run('utilityRestore()'); out({laps: run('utilityClocks[0].laps'), p0: run('utilityClocks[0].paused'), p1: run('utilityClocks[1].paused ?? null')});", stored={"utility-clocks": json.dumps(clocks)})
    assert got["laps"] == [1000, 4000] and got["p0"] == 5000 and got["p1"] is None


# --- the end of a timer ----------------------------------------------------------

@needs_node
def test_a_timer_that_ends_chimes_and_notifies_and_the_sound_can_be_turned_off():
    got = _run("run('startUtilityTimer(1)'); now += 61_000; tick(); out({});")
    assert len(got["chimes"]) == 1 and got["notes"] == ["Time is up: the 1 minute timer has finished."]
    quiet = _run("sandbox.prefs.set('utility-sound', '0'); run('startUtilityTimer(1)'); now += 61_000; tick(); out({});")
    assert quiet["chimes"] == [] and len(quiet["notes"]) == 1, "no sound, still a notification"


# --- the typed length, the alarm, the dashboard ----------------------------------

@needs_node
def test_a_typed_length_is_read_in_minutes_seconds_and_hours():
    cases = {"10": 10, "10m": 10, "90s": 1.5, "2h": 120, "1h30m": 90, "1:30": 1.5, "1:02:03": 62.05, "0.5": 0.5, "abc": None, "": None, "0": None, "-5": None}
    got = _run("out({r: " + json.dumps(list(cases)) + ".map((t) => run('utilityOps.parseLength(' + JSON.stringify(t) + ')'))});")
    assert got["r"] == list(cases.values())


@needs_node
def test_an_alarm_time_is_today_if_it_is_ahead_else_tomorrow():
    #: 2023-11-14 22:13:20 UTC
    got = _run("out({a: run('utilityOps.alarmValue(\"23:30\")'), b: run('utilityOps.alarmValue(\"07:05\")'), c: run('utilityOps.alarmValue(\"22:13\")'), d: run('utilityOps.alarmValue(\"\")')});")
    assert got["a"] == "2023-11-14T23:30" and got["b"] == "2023-11-15T07:05"
    assert got["c"] == "2023-11-15T22:13", "a minute that has begun is passed"
    assert got["d"] is None


def test_the_alarm_is_a_reminder_through_the_existing_api():
    assert "addReminder(" in SRC[SRC.index("function alarmSet"):][:900]


@needs_node
def test_the_dashboard_line_reads_the_same_clocks():
    got = _run(
        "run('startUtilityTimer(10)'); run('startStopwatch()'); const two = run('utilityOps.clocksLine()'); "
        "run('utilityClocks.length = 0'); out({two, none: run('utilityOps.clocksLine()')});"
    )
    assert got["two"].startswith("2 clocks running") and "10:00" in got["two"]
    assert got["none"] == "No clock running"


def test_the_focus_widget_has_a_row_for_the_clocks_and_opens_the_panel():
    dash = (JS / "dashboard.js").read_text(encoding="utf-8")
    widget = dash[dash.index("async function renderFocusTimerWidget"):][:6000]
    assert 'ensureModule("utilities").then(() => utilityOps.focusRow(body))' in widget
    row = SRC[SRC.index("function focusRow"):][:900]
    assert 'row.id = "focus-clocks"' in row and "openClockPanel(" in row and "clocksLine()" in row


# --- the panel itself ------------------------------------------------------------

def test_the_panel_is_a_movable_modeless_sheet_with_three_tabs():
    body = SRC[SRC.index("function openClockPanel"):]
    assert "openSheet({" in body and "modal: false" in body and 'name: "clock"' in body
    for tab in ("timer", "stopwatch", "alarm"):
        assert f'["{tab}"' in body or f"'{tab}'" in body or f'"{tab}"' in body
    assert 'role", "tablist"' in body


def test_a_stopped_clock_still_offers_undo_from_the_panel():
    assert "stopUtilityClock(find())" in SRC[SRC.index("function openClockPanel"):]


# L586: the Clock panel's head carries a '?' popover (data-help-for) for the Timer and Stopwatch tabs;
# Count words has no surface of its own (a palette row that toasts), so its help is the Guide topic.
def test_the_clock_panel_head_has_a_help_popover_naming_each_tab():
    assert 'help.setAttribute("data-help-for", "clock-help")' in SRC
    assert 'body.id = "clock-help"' in SRC
    help_lines = SRC.split("const CLOCK_HELP = [", 1)[1].split("];", 1)[0]
    for lead in ('"Timer: ', '"Stopwatch: ', '"Alarm: '):
        assert lead in help_lines, lead


def test_count_words_and_the_clock_have_guide_topics():
    from tessellate.ai import help_topics_more

    topics = {t["id"]: t for t in help_topics_more.MORE_TOPICS}
    assert "Count words" in topics["count-words"]["body"]
    assert "stopwatch" in topics["timer"]["body"].lower()
