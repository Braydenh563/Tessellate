"""A Gantt view of the topics that have dates (MINDMAP_PLAN gap 3, XMind): a
`start` marker beside `due`, and a sheet drawing a bar from one to the other."""

from tests._app_js import frontend_text
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._help_text import help_core_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MAP = frontend_text("whiteboard-map.js")
GANTT = (JS / "whiteboard-map-more.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = GANTT.index(f"function {name}(")
    return GANTT[start : GANTT.index("\n  }\n", start) + 5]


def _run(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const WB_GANTT_DAY=86400000;"
        + "".join(_function(n) for n in ("wbGanttDayNumber", "wbGanttDayText", "wbGanttShift", "wbGanttRows"))
        + body
    )
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_start_is_a_marker_read_painted_and_kept_by_a_look_reset():
    assert re.search(r"const start = typeof data\?\.start === \"string\"", MAP)
    assert "return { priority, progress, flag, icons, due, dueTime, start };" in MAP
    keys = re.search(r"const WB_MAP_CONTENT_KEYS = \[(.*?)\];", MAP, re.S).group(1)
    assert '"due_time", "start"' in keys
    assert "wbMapDateRow(live, parts, set, \"Start\", \"start\")" in MAP
    assert "wbMapDateRow(live, parts, set, \"Due\", \"due\")" in MAP


def test_rows_are_the_topics_with_both_days_in_order_and_the_rest_are_counted():
    out = _run(
        "const nodes=[{id:1,parent_id:null,data:{}},"
        "{id:2,parent_id:1,data:{start:'2026-10-20',due:'2026-10-25'}},"
        "{id:3,parent_id:2,data:{start:'2026-10-05',due:'2026-10-12'}},"
        "{id:4,parent_id:1,data:{due:'2026-10-30'}},"
        "{id:5,parent_id:1,data:{start:'2026-10-01'}},"
        "{id:6,parent_id:1,data:{start:'2026-10-09',due:'2026-10-02'}},"
        "{id:7,parent_id:1,data:{start:'2026-10-12',due:'2026-10-12'}}];"
        "const r=wbGanttRows(nodes,(n)=>'T'+n.id);"
        "console.log(JSON.stringify({ids:r.rows.map(x=>x.id),depth:r.rows.map(x=>x.depth),"
        "span:r.rows.map(x=>x.due-x.start+1),from:wbGanttDayText(r.from),to:wbGanttDayText(r.to),"
        "dueOnly:r.dueOnly,startOnly:r.startOnly,backwards:r.backwards}));"
    )
    assert out["ids"] == [3, 7, 2]
    assert out["depth"] == [2, 1, 1]
    assert out["span"] == [8, 1, 6]  # a start day equal to the due day is one day, not none
    assert (out["from"], out["to"]) == ("2026-10-05", "2026-10-25")
    assert (out["dueOnly"], out["startOnly"], out["backwards"]) == (1, 1, 1)


def test_shifting_a_bar_moves_both_days_across_month_and_year_ends():
    out = _run(
        "console.log(JSON.stringify({a:wbGanttShift({start:'2026-10-30',due:'2026-11-02'},3),"
        "b:wbGanttShift({start:'2026-01-02',due:'2026-01-03'},-5)}));"
    )
    assert out["a"] == {"start": "2026-11-02", "due": "2026-11-05"}
    assert out["b"] == {"start": "2025-12-28", "due": "2025-12-29"}


def test_the_view_is_one_undo_step_a_menu_row_a_lazy_file_and_in_the_guide():
    # A drag or a key moves both days in one patch through the one style writer (one Undo step).
    assert "wbMapSetNodeStyle(live, wbGanttShift(" in GANTT
    # The file's one export is a shared object (the audio file adds to it), so the shared scope gains one name.
    assert "Object.assign(window, { wbMapLazy });" in GANTT and "openGantt: wbMapOpenGantt" in GANTT
    assert MAP.count("wbMapLazy.openGantt()") == 2  # the palette row and the View menu item
    #: In the `boards` bundle (lazy-entries.js) since D22, 2026-11-11; it was `library`'s in app.js.
    app = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert '"/js/whiteboard-map-more.js"' in app
    assert app.index("whiteboard-map-more.js") > app.index('"/js/whiteboard-map.js"')
    topics = help_core_text()
    assert "Gantt" in topics
