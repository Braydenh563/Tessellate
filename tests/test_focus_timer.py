"""The focus timer (UI_MODERNISATION V8, INBOX 829: "can you redesign the
focus timer as well??"): a ring with the time large, presets as a segmented
control plus a custom stepper, Start and Pause as one primary, a chime and a
notification at the end, an optional break cycle, and today's focused
minutes. Measured by scratchpad sweep vu/v8.js at 1440 and 390."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/js/dashboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/01-forms-settings.css").read_text(encoding="utf-8")
WIDGET = JS.split("async function renderFocusTimerWidget(")[1].split("\n}\n")[0]


def test_a_ring_with_the_time_large():
    assert 'createElementNS(SVG_NS, "circle")' in WIDGET or "focusRing(" in WIDGET
    ring = JS.split("function focusRing(")[1].split("\n}\n")[0]
    assert "stroke-dasharray" in ring
    paint = JS.split("function paintFocusTimer(")[1].split("\n}\n")[0]
    assert "strokeDashoffset" in paint
    assert ".focus-ring-time {" in CSS


def test_presets_are_a_segmented_control_with_a_stepper():
    assert "const FOCUS_PRESETS = [5, 15, 25, 50, 60];" in JS
    assert 'seg.className = "seg focus-presets-seg";' in WIDGET
    assert 'aria-pressed' in JS.split("function paintFocusTimer(")[1].split("\n}\n")[0]
    assert "focusStep(-1)" in WIDGET and "focusStep(1)" in WIDGET


def test_one_primary_that_starts_and_pauses():
    assert 'toggle.id = "focus-timer-toggle";' in WIDGET
    assert 'smallButton("ph:play Start"' in WIDGET and '"ph:pause Pause"' in JS


def test_the_end_chimes_notifies_and_may_start_a_break():
    done = JS.split("function focusTimerEnded(")[1].split("\n}\n")[0]
    assert "focusChime()" in done and "notify(" in done and "recordNotification(" in done
    assert 'prefs.bool("focusBreaks", false)' in done
    assert "const FOCUS_BREAK_MIN = 5;" in JS


def test_today_s_focused_minutes_are_kept_per_day():
    assert "function focusTodaySeconds(" in JS and 'prefs.set("focusToday"' in JS
    assert 'id = "focus-today"' in WIDGET.replace("today.id", "id")


def _step_walk(start: int, dir: int, count: int) -> list[int]:
    """Runs the widget's own `focusStep` in node against a stub timer."""
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    fn = "function focusStep(" + JS.split("function focusStep(")[1].split("\n}\n")[0] + "\n}"
    script = (
        f"const focusTimer = {{ focusTotal: {start} * 60 }};\n"
        "const seen = [];\n"
        "function setFocusTimer(m) { focusTimer.focusTotal = m * 60; seen.push(m); }\n"
        f"{fn}\n"
        f"for (let i = 0; i < {count}; i++) focusStep({dir});\n"
        "console.log(JSON.stringify(seen));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_steps_are_one_minute_below_ten_and_five_above():
    assert _step_walk(1, 1, 12) == [2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25]
    assert _step_walk(25, -1, 18) == [20, 15, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1, 1, 1, 1, 1, 1]
    assert _step_walk(12, 1, 1) == [15] and _step_walk(12, -1, 1) == [10]
    assert _step_walk(178, 1, 3) == [180, 180, 180]


def test_the_minutes_are_typeable_and_the_presets_reach_an_hour():
    assert 'value.type = "number"' in WIDGET and 'value.max = "180"' in WIDGET
    assert 'value.addEventListener("change", typed)' in WIDGET
    # A repaint never overwrites the figure being typed.
    assert "document.activeElement !== step" in JS.split("function paintFocusTimer(")[1].split("\n}\n")[0]
