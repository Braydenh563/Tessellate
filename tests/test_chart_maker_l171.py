"""L171 and L254: the chart maker, a note block (paste values, SVG, PNG and CSV, a fenced chart block)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

#: Loads ask-chart.js with no page and runs `drawAskChart.maker.<call>` on `arg`.
RUNNER = """
const fs = require("fs"), vm = require("vm");
const win = {};
vm.runInNewContext(fs.readFileSync(process.argv[1], "utf8"), { window: win, document: {}, getComputedStyle: () => ({}) });
const [call, arg] = JSON.parse(process.argv[2]);
process.stdout.write(JSON.stringify(win.drawAskChart.maker[call](arg)));
"""


def _maker(call: str, arg):
    out = subprocess.run(
        ["node", "-e", RUNNER, str(ROOT / "frontend/js/ask-chart.js"), json.dumps([call, arg])],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(out.stdout)


@node
def test_two_columns_and_csv_both_parse():
    for text in ("Mon 3\nTue 5\nWed 4", "Mon, 3\nTue, 5\nWed, 4", "Mon;3\nTue;5\nWed;4", "Mon\t3\nTue\t5\nWed\t4"):
        chart = _maker("parse", text)
        assert [(r["label"], r["value"]) for r in chart["rows"]] == [("Mon", 3), ("Tue", 5), ("Wed", 4)], text
        assert chart["kind"] == "bar"


@node
def test_a_header_row_and_junk_lines_are_skipped_and_a_title_and_kind_read():
    chart = _maker("parse", "title: Sleep\nkind: line\nDay, Hours\nMon, 7\nbad line\nTue, 6.5\nWed, -2")
    assert chart["title"] == "Sleep" and chart["kind"] == "line"
    assert [(r["label"], r["value"]) for r in chart["rows"]] == [("Mon", 7), ("Tue", 6.5)]


@node
def test_a_phrase_label_keeps_its_words_and_a_dollar_sign_reads():
    chart = _maker("parse", "Rent paid late 1200\nGym $45")
    assert [(r["label"], r["value"]) for r in chart["rows"]] == [("Rent paid late", 1200), ("Gym", 45)]


@node
def test_csv_and_the_saved_block_round_trip():
    chart = _maker("parse", "title: Sleep\nkind: line\nMon, 7\nTue, 6.5")
    csv = _maker("csv", chart)
    assert csv.splitlines() == ["Label,Value", "Mon,7", "Tue,6.5"]
    fence = _maker("fence", chart)
    assert fence.startswith("```chart\n") and fence.endswith("\n```")
    again = _maker("parse", "\n".join(fence.splitlines()[1:-1]))
    assert again == chart, "the block saved to a note draws the chart it was made from"


def test_the_note_view_draws_a_chart_fence_and_the_editor_offers_the_maker():
    js = app_js_text()
    assert 'language === "chart"' in js and 'ensureModule("chartMaker")' in js
    editor = (ROOT / "frontend/js/editor.js").read_text()
    assert 'id: "chart"' in editor and "drawAskChart.maker.open" in editor
    chart = (ROOT / "frontend/js/ask-chart.js").read_text()
    assert "Save as SVG" in chart and "Save as CSV" in chart and "Save as PNG" in chart
