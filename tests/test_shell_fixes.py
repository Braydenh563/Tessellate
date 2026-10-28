"""App-shell audit 1028 fixes (S1, S4 to S10): source-level guards.

The behaviour was measured in the running app (see the commit messages); these
keep the wiring from being removed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent


def test_flash_entry_renders_through_the_target():
    js = app_js_text()
    assert "let pendingJumpId = null;" in js
    assert "pendingJumpId = id;" in js
    assert "No such note." in js


def test_lock_screen_is_a_dialog_that_takes_focus():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    card = html[html.index('id="lock-card"') - 40 : html.index('id="lock-card"') + 120]
    assert 'role="dialog"' in card and 'aria-modal="true"' in card
    assert 'aria-labelledby="lock-title"' in card
    js = app_js_text()
    assert "lockReturn ||= document.activeElement;" in js
    assert "lockReturn = lockReturn?.focus()" in js


def test_ask_controls_wrap_on_a_phone():
    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    rule = css[css.index("\n.ask-controls {") :].split("}", 1)[0]
    assert "flex-wrap: wrap;" in rule


def _node(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _extract(path: str, *heads: str) -> str:
    source = (ROOT / "frontend" / "js" / path).read_text(encoding="utf-8")
    out = []
    for head in heads:
        start = source.index(head)
        out.append(source[start : source.index("\n}\n", start) + 3])
    return "\n".join(out)


def test_timeline_count_line_pluralises_and_marks_a_page():
    body = _extract("timeline.js", "function timelineUnitText(", "function timelineCountLine(")
    script = (
        "let timelineNextCursor = null;\n"
        + body
        + """
const out = [];
out.push(timelineCountLine(1, 1, timelineUnitText(1, "day")));
out.push(timelineCountLine(3, 3, timelineUnitText(2, "day")));
out.push(timelineCountLine(2, 7, timelineUnitText(1, "week")));
timelineNextCursor = "more";
out.push(timelineCountLine(100, 100, timelineUnitText(4, "month")));
out.push(timelineCountLine(1, 1, timelineUnitText(1, "year")));
console.log(JSON.stringify(out));
"""
    )
    assert json.loads(_node(script)) == [
        "1 item · 1 day",
        "3 items · 2 days",
        "2 of 7 items · 1 week",
        "100+ items · 4 months",
        "1+ items · 1 year",
    ]
