"""Audit 1029 row 50 (N16 and N17): a toast is never ghosted by a surface that
fills the window, and a shrunk panel can always be put back.

Measured in the app (scratchpad/ui-sweeps, 1280 by 720): in the sketch the
focus sits on the drawing viewport, which covers the window, so every toast
was drawn at opacity 0.12 and let clicks through to the canvas."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap

import pytest

from tests._app_js import frontend_text


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


NODE = shutil.which("node")


def _yields(focused: dict, toast: dict, window: dict) -> bool:
    """Run the real `toastYield` body against stub geometry."""
    body = _body(frontend_text("status.js"), "function toastYield(") + "\n}"
    script = textwrap.dedent(
        """
        const cfg = %s;
        const rect = (r) => ({ left: r[0], top: r[1], right: r[0] + r[2], bottom: r[1] + r[3], width: r[2], height: r[3] });
        const classes = new Set();
        const toastEl = { toastTimer: 1, getBoundingClientRect: () => rect(cfg.toast) };
        const box = { id: "toast-box", children: [toastEl], contains: () => false, classList: {
          remove: (c) => classes.delete(c), toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) } };
        const $ = () => box;
        const document = { body: {}, activeElement: null };
        const innerWidth = cfg.window[0], innerHeight = cfg.window[1];
        const target = { closest: () => null, getBoundingClientRect: () => rect(cfg.focused) };
        %s
        toastYield(target);
        console.log(JSON.stringify(classes.has("is-yielding")));
        """
    ) % (json.dumps({"focused": focused_to_list(focused), "toast": focused_to_list(toast), "window": window}), body)
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    out = out.stdout
    return json.loads(out)


def focused_to_list(r):
    return r if isinstance(r, list) else [r["x"], r["y"], r["w"], r["h"]]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_toast_steps_aside_for_a_small_focused_control_it_covers():
    # A 120 by 32 button under a toast in the corner of a 1280 by 720 window.
    assert _yields([1100, 640, 120, 32], [1000, 620, 260, 60], [1280, 720]) is True


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_toast_stays_whole_over_a_surface_that_fills_the_window():
    # The sketch viewport: nothing under the toast is a control to be hidden.
    assert _yields([0, 0, 1280, 720], [1000, 620, 260, 60], [1280, 720]) is False


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_wide_but_short_focus_target_still_makes_way():
    # A full-width toolbar field is wide, not window-sized: the toast must still yield.
    assert _yields([0, 600, 1280, 100], [1000, 620, 260, 60], [1280, 720]) is True


def test_the_reset_for_a_shrunk_panel_is_the_one_recipe_with_three_ways_in():
    """The reset shipped in 4a1130b (head button, double-click on the head,
    Home on the grip). Pinned here so the audit row cannot come back."""
    src = frontend_text("panel-movable.js")
    assert "panel-reset" in src
    assert "dblclick" in src
    assert 'e.key === "Home"' in src


def test_the_reset_button_names_every_way_to_reset():
    src = frontend_text("panel-movable.js")
    assert "Double-clicking the title bar" in src
