"""L371: a topic's due day can carry a time (`due_time`, "HH:MM"), set by the
Due row's picker (the date and time fields of DESIGN.md's date recipe). Decision
37's day stays the day; a time only sharpens "was due" and the words. The pure
functions run in node under a fixed clock (12 Nov 2026, 10:00)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
CLOCK = (
    "const RealDate = Date; globalThis.Date = class extends RealDate {"
    " constructor(...a) { if (a.length) super(...a); else super(2026, 10, 12, 10, 0, 0); } };\n"
)


def _run(expr: str) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = MAP_JS[MAP_JS.index("function wbMapMarkerParts") : MAP_JS.index("//: The row before the label.")]
    out = subprocess.run([node, "-e", CLOCK + "const WB_MAP_MARKERS_MAX = 6; const WB_MAP_MARKER_ICON_NAMES = new Map();\n" + code + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_the_parts_read_a_time_only_beside_a_due_day():
    assert _run('wbMapMarkerParts({ due: "2026-11-20", due_time: "09:30" }).dueTime') == "09:30"
    assert _run('wbMapMarkerParts({ due_time: "09:30" }).dueTime') is None
    assert _run('wbMapMarkerParts({ due: "2026-11-20", due_time: "9:30" }).dueTime') is None


def test_the_words_say_the_time_and_it_decides_was_due_on_the_day_itself():
    said = _run('wbMapDueWords("2026-11-20", null, "09:30")')
    assert "9:30" in said["words"] and said["past"] is False
    today_later = _run('wbMapDueWords("2026-11-12", null, "15:00")')
    assert today_later["past"] is False
    today_earlier = _run('wbMapDueWords("2026-11-12", null, "09:00")')
    assert today_earlier["past"] is True
    assert _run('wbMapDueWords("2026-11-12")')["past"] is False
    assert "9:30" in _run('wbMapMarkerWords(wbMapMarkerParts({ due: "2026-11-20", due_time: "09:30" }))')


def test_the_due_row_is_the_date_field_recipe_with_a_time_field_and_remind_me_uses_it():
    row = MAP_JS[MAP_JS.index("function wbMapDateRow") : MAP_JS.index("const wbMarkerUi")]
    assert row.count("enhanceDateField(") >= 2
    assert 'type = "time"' in row and "due_time" in row
    assert "dueTime" in row
