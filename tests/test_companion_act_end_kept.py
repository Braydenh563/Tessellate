"""L-general-46: a re-sync dropped the end of the act in flight.

`companionperf.js` failed on fresh data dirs: Atlas +564 ms/s of main thread idle over the page with it off (63
style recalcs and 63 layouts a second). Traced (a timer log on a fresh boot): `atlasOn` starts the greeting wave
(`nameMarkBuddyAct("wave")`, its end `nmb.timer` 2.1 s on); choosing the companion in Settings 2 s later ran
`syncNameMarkBuddy` -> `nameMarkBuddySchedule`, which cleared `nmb.timer` and set the 20 to 60 s tick in its place.
The wave held (`nmb-act-wave` on, `nmb.act` "wave") until that tick, so the pacer (`nameMarkBuddyTempo`) counted
the figure busy and played every loop in the drawing at full rate: the sitting pose's coil breath, a `scale`
Web Animation on an svg `g`, restyled and laid out the figure every frame. Run here under node with stubs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import pytest

from tests._app_js import frontend_text

# avatars.js is a lazy module, outside `app_js_text()`; `frontend_text` reads it unwrapped from its IIFE.
AV = frontend_text("avatars.js")


def _schedule() -> str:
    start = AV.index("function nameMarkBuddySchedule() {")
    return AV[start : AV.index("\n}\n", start) + 3]


def _run(act: str, timer: int, hidden: bool = False) -> dict:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    script = f"""
const cleared = [];
const set = [];
const clearTimeout = (id) => cleared.push(id);
const setTimeout = (fn, ms) => (set.push(Math.round(ms)), 900);
const document = {{ hidden: {json.dumps(hidden)}, getElementById: () => ({{ classList: {{ contains: () => false }} }}) }};
const nmb = {{ act: {json.dumps(act)}, timer: {timer}, cat: {{ load() {{}} }}, fadeComes: () => false, mind: {{ nextIn: () => 30000 }} }};
const nameMarkBuddyState = () => {{}};
const nameMarkBuddyStill = () => false;
const nameMarkBuddyTick = () => {{}};
{_schedule()}
nameMarkBuddySchedule();
console.log(JSON.stringify({{ timer: nmb.timer, cleared, set }}));
"""
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_a_resync_leaves_the_end_of_an_act_in_flight() -> None:
    got = _run("wave", 286)
    assert got == {"timer": 286, "cleared": [], "set": []}, "the wave's end timer must survive a re-sync"


def test_with_no_act_the_next_tick_is_set_as_before() -> None:
    got = _run("", 286)
    assert got == {"timer": 900, "cleared": [286], "set": [30000]}


def test_an_act_whose_end_was_dropped_by_a_hide_still_gets_a_tick() -> None:
    # visibilitychange (hidden) sets `nmb.timer` 0 with a resting act (a lie-down) on: coming back, the tick is set.
    got = _run("lie", 0)
    assert got["timer"] == 900 and got["set"] == [30000]
