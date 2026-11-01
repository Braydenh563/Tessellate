"""Audit 1031 G20: the map's zoom strip is one Tab stop with arrow keys."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest
from tests._app_js import JS_DIR

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_the_zoom_strip_is_one_tab_stop_and_the_arrows_move_inside_it():
    source = (JS_DIR / "graph.js").read_text(encoding="utf-8")
    fn = re.search(r"^function graphZoomRoving\(.*?^\}\n", source, re.S | re.M).group(0)
    script = (
        fn
        + """
const listeners = {};
const mk = (name) => ({ name, tabIndex: 0, focus() { this.focused = true; strip.focused = this; fire("focusin", { target: this }); } });
const buttons = ["in", "out", "fit", "full"].map(mk);
const attrs = {};
const strip = { querySelectorAll: () => buttons, setAttribute: (k, v) => { attrs[k] = v; }, addEventListener: (type, fn) => { listeners[type] = fn; } };
const fire = (type, event) => listeners[type](event);
graphZoomRoving(strip);
const stops = () => buttons.filter((b) => b.tabIndex === 0).map((b) => b.name);
const out = { initial: stops(), role: attrs.role, orientation: attrs["aria-orientation"] };
const key = (name, from) => { let prevented = false; fire("keydown", { key: name, target: from, preventDefault() { prevented = true; } }); return prevented; };
key("ArrowDown", buttons[0]);
out.down = stops();
key("ArrowDown", buttons[1]);
out.down2 = stops();
key("ArrowUp", buttons[2]);
out.up = stops();
key("End", buttons[1]);
out.end = stops();
out.pastEnd = key("ArrowDown", buttons[3]);
key("Home", buttons[3]);
out.home = stops();
out.other = key("a", buttons[0]);
console.log(JSON.stringify(out));
"""
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    out = json.loads(done.stdout)
    assert out["initial"] == ["in"] and out["role"] == "toolbar" and out["orientation"] == "vertical"
    assert out["down"] == ["out"] and out["down2"] == ["fit"] and out["up"] == ["out"]
    assert out["end"] == ["full"] and out["pastEnd"] is False and out["home"] == ["in"] and out["other"] is False


def test_the_strip_is_wired_where_its_buttons_are():
    source = (JS_DIR / "graph.js").read_text(encoding="utf-8")
    assert source.index('graphZoomRoving($("graph-zoom"));') < source.index('$("graph-zoom-in").addEventListener')
