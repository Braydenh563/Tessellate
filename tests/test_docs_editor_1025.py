"""Owner's 22-10 bug doc, Documents rows: pins for what the browser sweeps found.

Browser checks: the 10-25 docs-agent probes (suggestion hide and restore, a
Read-view tick, the focus bar and dock at 1280, 700 and 420, and a selection's
bar hit-tested in full screen).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_JS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
FOCUS_CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_suggestions_can_be_hidden_and_dismissed_ones_restored():
    assert "function docProseSetHidden(" in DOCS_JS
    assert "if (docProseHidden) docProseFound = [];" in DOCS_JS
    assert "docProseIgnored.delete(row.key)" in DOCS_JS


def test_read_view_tasks_are_wired_to_their_source_lines():
    render = DOCS_JS[DOCS_JS.index("function renderDocPreview("):]
    render = render[: render.index("\n}\n")]
    assert "docWireReadTasks(preview, text)" in render
    wire = DOCS_JS[DOCS_JS.index("function docWireReadTasks("):]
    wire = wire[: wire.index("\n}\n")]
    # Counts must agree before any box is enabled: a box never ticks a wrong line.
    assert "tasks.length !== boxes.length" in wire
    assert "replaceRange" in wire


def test_full_screen_popups_stack_above_the_page():
    m = re.search(r"body\.doc-focus-on :is\(([^)]*)\)\s*\{\s*--doc-focus-layer:\s*(\d+)", LAZY_CSS)
    assert m, "the focus-mode stacking rule is gone"
    assert int(m.group(2)) >= 1000  # equal to the page (1000) and later in the DOM
    for name in (".selection-bar", ".editor-menu", ".doc-block-bar"):
        assert name in m.group(1)


def test_focus_page_clears_its_floating_bar():
    block = FOCUS_CSS[FOCUS_CSS.index("#tab-documents.doc-focus .doc-main {") :]
    block = block[: block.index("}")]
    assert "--target-min" in block, "the bar's height uses the touch floor, so must the page's top gap"


def test_a_colour_pick_on_a_highlight_switches_it(tmp_path):
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = """
const src = require('fs').readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('function mdColourEdit');
eval(src.slice(a, src.indexOf('\\n}\\n', a) + 3));
const t = (v, sub, k, c) => { const s = v.indexOf(sub); const r = mdColourEdit(v, s, s + sub.length, k, c); return v.slice(0, r.from) + r.insert + v.slice(r.to); };
console.log(JSON.stringify([
  t('a ==yellow text== b', 'yellow', 'highlight', 'blue'),
  t('a ==blue|x== b', 'x', 'highlight', 'yellow'),
  t('a ++red|x++ b', 'x', 'ink', 'green'),
  t('a plain b', 'plain', 'highlight', 'pink'),
]));
"""
    out = subprocess.run([node, "-e", script, str(ROOT / "frontend" / "js" / "documents.js")], capture_output=True, text=True, check=True)
    import json

    assert json.loads(out.stdout) == [
        "a ==blue|yellow text== b",
        "a ==x== b",
        "a ++green|x++ b",
        "a ==pink|plain== b",
    ]


def test_toolbar_menus_and_the_slash_menu_answer_an_outside_press():
    assert 'document.querySelectorAll("details.doc-toolbar-menu[open]")' in DOCS_JS
    assert 'editorTokenAt(textarea, "/")' in DOCS_JS
    assert 'editorSplice(textarea, bare.start, bare.start + 1, "")' in DOCS_JS


def test_list_markers_are_a_fixed_hanging_indent():
    # Measured in the browser (probe: first-line words vs the wrapped line, 1280, 700 and 420):
    # bullets, numbers and tasks all start the words at the hang (0px apart; 11px, 9px and 4px before).
    assert '".cm-md-li-bullet": { display: "inline-block", width: "1.6em" }' in DOCS_JS
    assert '".cm-md-li-num": { display: "inline-block", minWidth: "1.6em" }' in DOCS_JS
    css = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")
    hit = css[css.index(".cm-md-task-hit {") :]
    assert "width: 1.6em;" in hit[: hit.index("}")]


def test_narrow_gutter_and_table_menu_stay_compact():
    # Measured: gutter 57px to 47px at 700; table menu 28px at 1280, 700 and 480 (44px before);
    # add-row plus sits 2px under the table instead of far below.
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    assert "@media (max-width: 819.98px)" in css and ".cm-lineNumbers .cm-gutterElement" in css
    assert ".cm-editor .cm-md-table-menu > button" in css
    assert "geo.box.bottom + 2" in DOCS_JS


def test_history_dialog_keeps_the_head_to_title_and_close():
    # Measured at 1280, 700 and 420: no horizontal overflow (scrollWidth == clientWidth);
    # the filter and "Name this version" share a row that wraps at 420.
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    dlg = html[html.index('id="doc-history-dialog"') :]
    dlg = dlg[: dlg.index("</dialog>")]
    head = dlg[: dlg.index("</div>")]
    assert "doc-history-name" not in head
    bar = dlg[dlg.index('class="doc-history-bar"') :]
    assert "doc-history-filter" in bar and "doc-history-name" in bar
