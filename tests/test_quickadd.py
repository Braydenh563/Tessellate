"""Quick add (CHAT_PLAN decision 50, Brief 66): one grammar of chips under
every field where a dated or tagged thing is typed.

The reading is the server's (`GET /read`, decision 47); these check that
quickadd.js is wired into the five surfaces, stays out of the boot scripts,
never reads language itself, and turns a reading into the values a save
carries (run in node against canned readings, so this holds whether or not
the reader is merged). The end-to-end score over the 60 phrases is the sweep's
(`scratchpad/ui-sweeps/quickadd.js`), against a running app.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
QUICKADD = _js_scope.unwrapped_copy(JS / "quickadd.js")
FIXTURE = ROOT / "tests" / "fixtures" / "composer" / "quickadd_1010.json"


def _text(name: str) -> str:
    return _js_scope.unwrapped((JS / name).read_text(encoding="utf-8"))


def test_quickadd_is_lazy_with_its_own_stylesheet():
    app = _text("app.js")
    assert 'quickAdd: ["/css/quickadd-lazy.css", "/js/quickadd.js"]' in app
    entry = re.search(r"quickAdd: \[([^\]]*)\],\n", app[app.index("const LAZY_ENTRY_POINTS") :])
    assert entry, "quickAdd has no entry points"
    for name in ("quickAddAttach", "quickAddSlots", "quickAddAsk", "quickAddClear", "magicAddReminder"):
        assert f'"{name}"' in entry.group(1)
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "quickadd.js" not in index and "quickadd-lazy.css" not in index


def test_the_reader_is_warmed_after_sign_in_not_on_the_lock_screen():
    # Both warm-up asks answered 401 into the console on every launch with a
    # password or a stale token (scan 2026-10-11): the module loads three
    # seconds after boot, before or after the session exists.
    src = _text("quickadd.js")
    body = src.split("function qaPrewarm(")[1].split("\n}\n")[0]
    assert 'authToken() && lock && lock.classList.contains("hidden")' in body
    assert body.index("const live") < body.index('qaFetch("in 5 minutes", "reminder")')
    assert "\n  qaPrewarm();\n" in src


def test_every_surface_reads_through_the_one_grammar():
    assert "quickAddAttach(box, \"note\"" in _text("quick-note.js")
    assert "quickAddSlots(quickNoteBox())" in _text("quick-note.js")
    meetings = _text("meetings.js")
    assert 'quickAddAttach(titleInput, "meeting"' in meetings and "quickAddSlots(titleInput)" in meetings
    palette = _text("app-palette.js")
    assert "quickAddPaletteRow(query)" in palette and 'quickAddAttach($("palette-input"), "palette")' in palette
    own = QUICKADD.read_text(encoding="utf-8")
    assert 'quickAddAttach($("reminder-magic"), "reminder"' in own
    assert 'quickAddAttach(search, "timeline"' in own
    #: Magic add moved with the chips; the boot file no longer defines it.
    assert "function magicAddReminder" not in _text("shell-reminders.js")
    assert "async function magicAddReminder" in own


def test_quickadd_never_reads_language_itself():
    """Decision 47: one reading per input, the server's. A weekday, a month or
    a relative day appears here only in the one question's example."""
    words = re.compile(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|january|february|march|april|june|july|"
        r"august|september|october|november|december|tomorrow|today|tonight|yesterday|noon|midnight|weekend)\b",
        re.I,
    )
    hits = [
        line
        for line in QUICKADD.read_text(encoding="utf-8").splitlines()
        if words.search(line) and not line.lstrip().startswith("//") and "Remind you when?" not in line
    ]
    assert not hits, hits


def test_the_phrase_set_is_sixty_and_covers_the_five_surfaces():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = doc["phrases"]
    assert len(rows) == 60
    assert {r["surface"] for r in rows} == {"reminder", "note", "meeting", "timeline", "palette"}
    assert len({(r["surface"], r["text"]) for r in rows}) == 60
    for row in rows:
        expect = row["expect"]
        for key in ("date",):
            if expect.get(key):
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", expect[key]), row
        if expect.get("time"):
            assert re.fullmatch(r"\d{2}:\d{2}", expect["time"]), row


NODE_HARNESS = r"""
const fs = require("fs");
const vm = require("vm");
const ctx = { console, Date, Math, JSON, Number, String, Array, Set, Map, WeakMap, Promise, RegExp, Object,
  setTimeout: () => 0, clearTimeout, encodeURIComponent, $: () => null, document: {}, navigator: {},
  authToken: () => "", apiJson: () => Promise.reject(new Error("no server here")), onSurface: () => {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx);
const span = (text, kind, phrase, value, extra = {}) => {
  const start = text.indexOf(phrase);
  if (start < 0) throw new Error(`${phrase} not in ${text}`);
  return { kind, text: phrase, start, end: start + phrase.length, value, read_as: phrase, ...extra };
};
const run = (surface, text, spans, extra = {}) => {
  const state = { surface, text, reading: { intent: extra.intent || "", spans, slots: extra.slots || {} },
    off: new Set(extra.off || []), on: new Set(), opts: extra.opts || {} };
  const slots = ctx.qaSlotsOf(state);
  return { title: slots.title, date: slots.date, time: slots.time, recurring: slots.recurring,
    tags: slots.tags, people: slots.people, range: slots.range, chips: ctx.qaSpans(state).map((s) => s.kind),
    due: slots.due ? slots.due.toISOString() : null, missing: ctx.qaMissing(state) };
};
const out = {};
let t = "pay rent on the 1st at 9am";
out.rent = run("reminder", t, [span(t, "date", "1st", "2026-11-01"), span(t, "time", "9am", "09:00")]);
t = "weekly review every friday at 4pm";
out.weekly = run("reminder", t, [span(t, "recurrence", "every friday", { freq: "weekly" }), span(t, "datetime", "friday at 4pm", "2026-10-16T16:00")]);
t = "standup every 2 weeks monday 9am";
out.fortnight = run("reminder", t, [span(t, "recurrence", "every 2 weeks", "FREQ=WEEKLY;INTERVAL=2"), span(t, "datetime", "monday 9am", "2026-10-19T09:00")]);
t = "lunch with Ana friday #work";
out.note = run("note", t, [span(t, "date", "friday", "2026-10-16"), span(t, "tag", "#work", "work")], { opts: { offKinds: ["date", "time", "datetime"] } });
t = "remind me to call Bo tomorrow at 10am #house";
out.noteRemind = run("note", t, [span(t, "datetime", "tomorrow at 10am", "2026-10-15T10:00:00"), span(t, "tag", "#house", "house")], { intent: "reminder", slots: { text: "call Bo", due_at: "2026-10-15T10:00" }, opts: { offKinds: ["datetime"] } });
t = "remind me friday 9 dentist";
out.joined = run("palette", t, [span(t, "date", "friday", "2026-10-16"), span(t, "number", "9", 9), span(t, "time", "9", "21:00", { rank: 1 })], { intent: "reminder", slots: { text: "dentist", due_at: "2026-10-16T09:00", recurring: "weekly" } });
t = "check oven in 30 minutes";
out.duration = run("reminder", t, [span(t, "duration", "in 30 minutes", "PT30M")]);
t = "review budget friday";
out.asks = run("reminder", t, [span(t, "date", "friday", "2026-10-16")]);
out.notGiven = run("reminder", t, [span(t, "date", "friday", "2026-10-16")], { intent: "reminder", slots: { text: "Review budget", due_at: "2026-10-16T09:00" } });
t = "buy milk";
out.asksWhen = run("reminder", t, []);
t = "dentist friday 9am";
out.zoned = run("reminder", t, [span(t, "datetime", "friday 9am", "2026-10-16T09:00:00Z")]);
out.off = run("reminder", t, [span(t, "datetime", "friday 9am", "2026-10-16T09:00:00")], { off: ["datetime:8:18"] });
t = "water the plants every day at 8am";
out.ruleHour = run("reminder", t, [span(t, "recurrence", "every day at 8am", "FREQ=DAILY;BYHOUR=8;BYMINUTE=0")], { intent: "reminder", slots: { text: "Water the plants", due_at: "2026-10-15T08:00", recurring: "daily" } });
t = "harbor last week";
out.range = run("timeline", t, [span(t, "range", "last week", { start: "2026-10-05", end: "2026-10-11" })]);
t = "garden yesterday";
out.day = run("timeline", t, [span(t, "date", "yesterday", "2026-10-13")]);
t = "Sync with Ana friday 2pm";
out.meeting = run("meeting", t, [span(t, "person", "Ana", "Ana"), span(t, "datetime", "friday 2pm", "2026-10-16T14:00")]);
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def slots(tmp_path_factory):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("qa") / "harness.js"
    script.write_text(NODE_HARNESS, encoding="utf-8")
    run = subprocess.run(
        [node, str(script), str(QUICKADD)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={"TZ": "UTC", "PATH": ""},
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_a_reading_becomes_the_saved_values(slots):
    rent = slots["rent"]
    assert (rent["title"], rent["date"], rent["time"], rent["recurring"]) == ("pay rent", "2026-11-01", "09:00", None)
    assert rent["due"] == "2026-11-01T09:00:00.000Z"
    weekly = slots["weekly"]
    assert (weekly["title"], weekly["recurring"], weekly["time"]) == ("weekly review", "weekly", "16:00")
    assert slots["zoned"]["due"] == "2026-10-16T09:00:00.000Z"
    assert slots["meeting"]["people"] == ["Ana"] and slots["meeting"]["title"] == "Sync with Ana"


def test_the_readings_own_slots_join_what_the_chips_show(slots):
    """ai/reading.py puts "friday" and "9" together as the reminder's due;
    an alternative reading (rank 1) is never a second chip."""
    joined = slots["joined"]
    assert (joined["title"], joined["date"], joined["time"], joined["recurring"]) == ("dentist", "2026-10-16", "09:00", "weekly")
    assert joined["chips"] == ["date", "time"]


def test_a_repeats_hour_is_its_time(slots):
    hour = slots["ruleHour"]
    assert (hour["title"], hour["date"], hour["time"], hour["recurring"]) == ("Water the plants", "2026-10-15", "08:00", "daily")


def test_a_repeat_beyond_the_three_words_is_kept_as_its_rule(slots):
    """TIMELINE_PLAN 11 row 8 (Brief 85): every 2 weeks was left as words
    because the store took only daily, weekly and monthly; it keeps the rule
    now, and the words leave the title like any other repeat."""
    fortnight = slots["fortnight"]
    assert fortnight["recurring"] == "FREQ=WEEKLY;INTERVAL=2"
    assert fortnight["title"] == "standup"


def test_a_notes_day_is_an_offer_unless_the_words_are_a_reminder(slots):
    assert slots["note"]["tags"] == ["work"] and slots["note"]["due"] is None
    assert slots["noteRemind"]["due"] == "2026-10-15T10:00:00.000Z"
    assert slots["noteRemind"]["title"] == "call Bo"


def test_a_chip_pressed_off_is_not_saved(slots):
    assert slots["off"]["due"] is None and slots["off"]["title"] == "dentist friday 9am"
    assert slots["off"]["missing"].startswith("Remind you when?")


def test_a_missing_slot_is_asked_never_guessed(slots):
    assert slots["asks"]["due"] is None and slots["asks"]["missing"].startswith("What time on ")
    #: The reading's own 09:00 for a day alone is not taken (decision 50).
    assert slots["notGiven"]["due"] is None and slots["notGiven"]["chips"] == ["date"]
    assert slots["asksWhen"]["missing"].startswith("Remind you when?")
    assert slots["duration"]["due"] is not None and slots["duration"]["missing"] == ""


def test_the_timeline_takes_a_window_and_keeps_the_rest(slots):
    assert slots["range"]["range"] == {"start": "2026-10-05", "end": "2026-10-11"}
    assert slots["range"]["title"] == "harbor"
    assert slots["day"]["range"] == {"start": "2026-10-13", "end": "2026-10-13"}
