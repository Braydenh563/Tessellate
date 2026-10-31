"""perf-1031 leftover 3 (perf3-1031, lagfix item 4): a layout that is cooling
is drawn a few times a second, not once per worker tick."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR, frontend_text

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _body(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


COOL = r"""
const draws = [];
const timers = [];
let clock = 0;
const gcRequestDraw = () => draws.push(clock);
const setTimeout = (fn, ms) => { timers.push([clock + ms, fn]); return timers.length; };
const performance = { now: () => clock };
%(source)s
const out = {};
const tick = (s, drift, at) => { clock = at; while (timers.length && timers[0][0] <= clock) { const [, fn] = timers.shift(); fn(); } gcTickDraw(s, at, drift); };
%(probes)s
console.log(JSON.stringify(out));
"""


def _cool(probes: str) -> dict:
    source = (JS_DIR / "graph-canvas.js").read_text(encoding="utf-8")
    consts = re.findall(r"^const GC_COOL_\w+ = [\d.]+;\n", source, re.M)
    funcs = [re.search(rf"^function {name}\(.*?^\}}\n", source, re.S | re.M).group(0) for name in ("gcDrawTick", "gcTickDraw", "gcDrawHeld")]
    funcs.append("const gcCooling = (s) => s.alpha < GC_COOL_ALPHA && !s.dragNode;\n")
    script = COOL % {"source": "".join(consts) + "".join(funcs), "probes": probes}
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(done.stdout)


@needs_node
def test_a_hot_layout_draws_every_tick_and_a_cooling_one_a_few_times_a_second():
    out = _cool(
        """
const hot = { alpha: 0.5, transform: { k: 1 } };
for (let t = 0; t < 10; t++) tick(hot, 3, t * 16);
out.hot = draws.length;
draws.length = 0;
const cool = { alpha: 0.004, transform: { k: 1 }, lastTickDraw: 1000 };
for (let t = 0; t < 63; t++) tick(cool, 4, 1000 + t * 16);   // one second of 16 ms ticks
out.cool = draws.length;
"""
    )
    assert out["hot"] == 10
    assert 9 <= out["cool"] <= 14  # one every 80 to 96 ms (a tick), not 63


@needs_node
def test_ticks_that_move_nothing_you_can_see_are_not_drawn_until_they_add_up():
    out = _cool(
        """
const s = { alpha: 0.004, transform: { k: 1 }, lastTickDraw: -1000 };
for (let t = 0; t < 4; t++) tick(s, 0.1, t * 100);   // 0.4 held in all: under half a pixel
out.early = draws.length;
tick(s, 0.1, 500);                                    // 0.5 held: drawn
out.later = draws.length;
const zoomedOut = { alpha: 0.004, transform: { k: 0.1 }, lastTickDraw: -1000 };
draws.length = 0;
tick(zoomedOut, 3, 2000);                              // 3 units at 0.1x is 0.3 px
out.zoomedOut = draws.length;
"""
    )
    assert out["early"] == 0 and out["later"] == 1 and out["zoomedOut"] == 0


@needs_node
def test_a_draw_held_back_is_made_when_its_time_is_up_and_at_rest():
    out = _cool(
        """
const s = { alpha: 0.004, transform: { k: 1 }, lastTickDraw: 100 };
tick(s, 5, 110);          // too soon after the last draw: held
out.heldAt = draws.length;
tick(s, 0, 190);          // 100 + 80 passed: the held draw is made
out.made = draws.length;
const rest = { alpha: 0, transform: { k: 1 }, heldDrift: 0.2 };
gcDrawHeld(rest);
out.rest = draws.length;
gcDrawHeld(rest);          // nothing held now
out.again = draws.length;
"""
    )
    assert out["heldAt"] == 0 and out["made"] == 1
    assert out["rest"] == 2 and out["again"] == 2


def test_the_tick_handler_asks_the_cooling_gate_and_the_end_draws_what_was_held():
    canvas = frontend_text("graph-canvas.js")
    handler = _body(canvas, "if (message.type === \"tick\") {", "} else if (message.type === \"frame\")")
    assert "const drift = gcAimNodes(s, positions, count);" in handler
    assert "if (gcTickSettles(s)) gcGlideFinish(s);" in handler  # a cooling tick does not start a glide
    assert "const gcTickSettles = (s) => gcTickSnaps(s) || gcCooling(s);" in canvas
    assert "gcTickDraw(s, now, drift);" in handler and "gcRequestDraw(s);" not in handler
    end = _body(canvas, "} else if (message.type === \"end\") {", "s.settledSig = s.layoutSig;")
    assert "gcGlideFinish(s);" in end and "gcDrawHeld(s);" in end
