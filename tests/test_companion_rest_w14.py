"""The companion at rest (W14, owner decision Q10; audit-1108-perf P1 and P5).

Measured with the companion on, the page at rest restyled and laid out 30 to
45 times a second (the dress morph at 10 Hz, the pacer at 20 Hz, the tail's
settle, a glance or a mood every few seconds). Two seconds from the last
input, not walking and doing nothing, the drawn loops stop; the first input
starts them again in the next frame. A key typed in a field is not input, so
typing with it at rest costs what typing with it off costs. Fixed clock, fakes.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
LIFE = unwrapped((JS / "atlas-life.js").read_text(encoding="utf-8"))
AVATARS = (JS / "avatars.js").read_text(encoding="utf-8")
MICRO = (JS / "atlas-micro.js").read_text(encoding="utf-8")
ATLAS = (JS / "atlas.js").read_text(encoding="utf-8")
MOTION = (JS / "atlas-motion.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _block(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i : src.index(end, i)]


@needs_node
def test_resting_needs_two_quiet_seconds_a_calm_state_and_no_act() -> None:
    code = (
        "const atlasTailCalm = () => {};\n"
        'atlasTailCalm.states = new Set(["idle", "sit"]);\n'
        "let clock = 10000;\nconst performance = { now: () => clock };\n"
        + _block(LIFE, "atlasTailCalm.rest = {", "//: Entering a rest pauses")
        + "atlasTailCalm.rest.holds = () => true;\n"
        + r"""
const buddy = (cls) => ({ className: cls });
const box = (cls) => ({ closest: () => (cls === null ? null : buddy(cls)) });
const at = (ms, cls, state) => { clock = 10000 + ms; return atlasTailCalm.resting(box(cls), state); };
atlasTailCalm.rest.at = 10000;
process.stdout.write(JSON.stringify({
  fresh: at(500, "", "idle"),
  quiet: at(2500, "", "idle"),
  walking: at(2500, "nmb-walking", "idle"),
  act: at(2500, "nmb-act-juggle", "idle"),
  thinking: at(2500, "nmb-think", "idle"),
  busyState: at(2500, "", "glide"),
  large: at(2500, null, "idle"),
}));
"""
    )
    run = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    got = json.loads(run.stdout)
    assert got == {"fresh": False, "quiet": True, "walking": False, "act": False, "thinking": False, "busyState": False, "large": False}


def test_the_drawn_loops_ask_whether_it_rests() -> None:
    # The morph timer, the pacer, the saccade, the glance clock, the mood drift and the tail's act pick.
    assert "atlasTailCalm.rest.sync(box, low.state)" in LIFE
    assert "atlasTailCalm?.rest.on" in AVATARS and "nameMarkBuddyTempo" in AVATARS
    assert "atlasTailCalm?.rest.on" in MOTION
    assert "atlasTailCalm?.rest.on" in MICRO
    assert "atlasTailCalm?.rest.on" in ATLAS
    assert "atlasTailCalm.resting(box, tail.state)" in LIFE


def test_input_wakes_in_the_next_frame_and_typing_in_a_field_is_not_input() -> None:
    wake = _block(LIFE, 'for (const type of typeof document.addEventListener', "//: On the function, not the shared scope")
    assert "setTimeout(() => r.wake.forEach" in wake, "the wake is not the input handler's cost"
    assert 'type === "keydown" && event.key !== "Enter"' in wake and "input, textarea, select, [contenteditable]" in wake


def test_a_key_does_not_rewrite_the_drowsy_class() -> None:
    # `remove` writes the attribute even when the class is absent: one restyle of the companion per key.
    assert 'if (buddy.classList.contains("nmb-drowsy")) buddy.classList.remove("nmb-drowsy");' in AVATARS


def test_a_blink_does_not_wake_the_rig() -> None:
    assert re.search(r"replace\(/\\batl-blinking\\b/g", MOTION)


@needs_node
def test_motion_at_rest_is_a_setting_still_by_default() -> None:
    # Decision 55: "still" (the default) always rests, "mains" (opt-in) rests on battery only, "always" never rests;
    # a machine with no battery reading is on mains. Intent moved (L-general-47, 2026-11-21): the default was "mains",
    # alive on mains, and Atlas then cost +340 to +563 ms/s of main thread idle against a budget of 120; resting, +24.
    code = (
        "const atlasTailCalm = () => {};\n"
        "let clock = 0, stored = null;\nconst performance = { now: () => clock };\n"
        "const prefs = { get: (k, f) => (stored === null ? f : stored) };\n"
        "let charging = true, api = true;\n"
        'Object.defineProperty(globalThis, "navigator", { configurable: true, get: () => (api ? '
        "{ getBattery: () => Promise.resolve({ get charging() { return charging; }, addEventListener() {} }) } : {}) });\n"
        + _block(LIFE, "atlasTailCalm.rest = {", "//: **Whether the rest may hold now**")
        + _block(LIFE, "//: **Whether the rest may hold now**", "//: At rest: a corner companion")
        + """
const at = async (mode, onBattery, hasApi = true) => {
  stored = mode; charging = !onBattery; api = hasApi; clock += 5000; atlasTailCalm.rest.asked = false; atlasTailCalm.rest.battery = false;
  atlasTailCalm.rest.holds();
  await Promise.resolve(); await Promise.resolve();
  clock += 5000; return atlasTailCalm.rest.holds();
};
(async () => {
  process.stdout.write(JSON.stringify({
    unset: await at(null, false), unsetBattery: await at(null, true),
    always: await at("always", true), still: await at("still", false),
    mainsPlugged: await at("mains", false), mainsBattery: await at("mains", true), mainsNoApi: await at("mains", true, false),
  }));
})();
"""
    )
    run = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    assert json.loads(run.stdout) == {
        "unset": True, "unsetBattery": True, "always": False, "still": True,
        "mainsPlugged": False, "mainsBattery": True, "mainsNoApi": False,
    }


@needs_node
def test_unplugging_stops_the_full_loops_at_once_and_plugging_in_starts_them() -> None:
    # The full mode is the opt-in: it is not held to the idle budget, but a `chargingchange` to battery rests it in that
    # event (the wakers run `sync`, which pauses the loops), not at the next morph tick or the next second's re-read.
    code = (
        "const atlasTailCalm = () => {};\n"
        "let clock = 0;\nconst performance = { now: () => clock };\n"
        'const prefs = { get: () => "mains" };\n'
        'const battery = { charging: true, on: null, addEventListener(type, fn) { if (type === "chargingchange") this.on = fn; } };\n'
        'Object.defineProperty(globalThis, "navigator", { configurable: true, value: { getBattery: () => Promise.resolve(battery) } });\n'
        + _block(LIFE, "atlasTailCalm.rest = {", "//: **Whether the rest may hold now**")
        + _block(LIFE, "//: **Whether the rest may hold now**", "//: At rest: a corner companion")
        + """
const seen = [];
atlasTailCalm.rest.wake.add(() => seen.push(atlasTailCalm.rest.holds()));
(async () => {
  const before = atlasTailCalm.rest.holds();
  await Promise.resolve(); await Promise.resolve();
  const plugged = atlasTailCalm.rest.holds();
  clock += 10;
  battery.charging = false; battery.on();
  const unplugged = atlasTailCalm.rest.holds();
  battery.charging = true; battery.on();
  process.stdout.write(JSON.stringify({ before, plugged, unplugged, again: atlasTailCalm.rest.holds(), seen }));
})();
"""
    )
    run = subprocess.run(["node", "-e", code], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-1500:]
    assert json.loads(run.stdout) == {"before": False, "plugged": False, "unplugged": True, "again": False, "seen": [True, False]}


def test_the_setting_is_wired_and_reset_clears_it() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    controls = unwrapped((JS / "settings-controls.js").read_text(encoding="utf-8"))
    settings = (JS / "settings.js").read_text(encoding="utf-8")
    assert 'id="avatar-buddy-rest"' in html and html.count('<option value="mains">') == 1
    # The default is the first option, so a fresh select shows what `holds` does with no choice stored.
    assert re.search(r'<select id="avatar-buddy-rest"[^>]*>\s*<option value="still">', html)
    assert 'prefs.get("avatar-buddy-rest", null) || "still"' in settings
    assert 'prefs.set("avatar-buddy-rest", e.target.value)' in controls
    reset = settings[settings.index("function resetAppearance()") : settings.index("// --- generative background")]
    for key in ("avatar-buddy-motion", "avatar-buddy-rest", "avatar-buddy-entrances"):
        assert f'"{key}"' in reset, f"Reset appearance clears {key} (B60)"


def test_a_key_rewrites_no_class_on_the_chat_dock_or_its_clear_button() -> None:
    panes = (JS / "settings-panes.js").read_text(encoding="utf-8")
    clear = (JS / "field-clear.js").read_text(encoding="utf-8")
    assert 'if (dock?.classList.contains("ring-held")) dock.classList.remove("ring-held");' in panes
    assert 'if (button.classList.contains("hidden") === full) button.classList.toggle("hidden", !full);' in clear
