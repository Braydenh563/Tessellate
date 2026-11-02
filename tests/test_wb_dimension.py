"""Dimension lines (INBOX 1313, plan row 7): a connector's label `%length%`
reads its own drawn length, live, and a command makes one."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _expand(text: str, builtin: str, props: str = "null"):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = _function("wbExpandPlaceholders") + f"console.log(JSON.stringify(wbExpandPlaceholders({json.dumps(text)}, {props}, {builtin})));"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


B = "(n) => ({length: 240, width: 96, height: 40, date: 'today'})[n]"


def test_length_width_and_height_are_built_ins() -> None:
    assert _expand("%length% px", B) == "240 px"
    assert _expand("%width% by %height%", B) == "96 by 40"


def test_an_item_property_of_the_same_name_wins_and_no_answer_keeps_the_text() -> None:
    assert _expand("%length%", B, '{length: "about 2 m"}') == "about 2 m"
    assert _expand("%length%", "() => ''") == "%length%"
    assert _expand("%other%", B) == "%other%"


def test_the_label_is_worded_again_on_every_layout() -> None:
    """A drag of either end calls the layout, so the number follows it."""
    layout = _function("wbLayoutLinkLabel")
    assert "__wbMeasured" in layout and "wbPlaceholderBuiltins(" in layout
    paint = _function("wbPaintLinkLabel")
    assert 'includes("%length%")' in paint


def test_the_command_is_in_the_arrange_menu_with_its_words() -> None:
    assert 'id: "measure"' in CMD and "wbMeasureSelection()" in CMD
    assert re.search(r'data-wb-cmd="measure"[^>]*>.*?<span>Measure with a dimension line</span>', HTML)


def test_one_connector_or_a_pair_is_measurable() -> None:
    body = CMD[CMD.index("async function wbMeasureSelection(") :]
    body = body[: body.index("\n}\n")]
    assert 'startCap: "arrow", endCap: "arrow"' in body
    assert body.count("WB_MEASURE_LABEL") >= 2 and 'wbJoinPlan(entries, "chain")' in body
