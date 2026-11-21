"""L-chat-105 (CHAT_PLAN X13): the note templates fill {weekday} {week} {title} {n} by rule in the browser
exactly as `ai/template_fill` does, and name the slots left for the person."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime

import pytest

from tessellate.ai import template_fill
from tests._app_js import app_js_text

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _twin(script: str):
    source = app_js_text()
    start = source.index("Object.assign(noteTemplateState")
    end = source.index("\n});\n", start) + 5
    out = subprocess.run([NODE, "-e", "const noteTemplateState = {};" + source[start:end] + script], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


@pytest.mark.parametrize("day", [datetime(2026, 10, 31, 11, 30), datetime(2026, 1, 1, 9, 0), datetime(2027, 1, 3, 9, 0), datetime(2026, 12, 31, 9, 0)])
def test_the_browser_twin_fills_what_the_python_fill_fills(day):
    text = "{weekday} week {week}: {title} no. {n} {what}"
    got = _twin(f"console.log(JSON.stringify(noteTemplateState.vars({text!r}, new Date({day.year}, {day.month - 1}, {day.day}, 12), 'Gym', 3)));")
    want = template_fill.fill(text, day, title="Gym", n=3)
    assert got == want


def test_the_slots_left_to_fill_are_named_and_marks_are_not_slots():
    raw = "Log a workout: {what} on {date}, {what} {{cursor}} {{clipboard}} {where}"
    assert _twin(f"console.log(JSON.stringify(noteTemplateState.slots({raw!r})));") == ["what", "where"] == template_fill.slots(raw)


def test_the_picker_and_use_path_call_the_fill():
    source = app_js_text()
    assert "noteTemplateState.vars(template?.content, new Date(), template?.name)" in source
    assert "noteTemplateState.vars(template.content, new Date(), template.name)" in source
    assert "Fill in: " in source and "{weekday} {date}" in source
