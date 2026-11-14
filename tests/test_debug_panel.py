"""The debugger's panel, gutter and keys (DOCUMENTS_PLAN 23, I2; Brief 70).

The four views (Variables, Watch, Call stack, Breakpoints) and the five
actions (Continue, Step over, Step in, Step out, Stop) on VS Code's keys, in
the run panel's Debug tab and the editor's breakpoint lane. Driven in
Chromium by `scratchpad/ui-sweeps/code-debug.js` (a session per language)
and measured for a finger by touch.js's "Debug tab" row; these hold the
shape the sweeps found working.
"""

from __future__ import annotations

from pathlib import Path
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / "frontend" / "js" / "documents-code.js").read_text(encoding="utf-8")
DOCS = documents_text()


def _function(text: str, name: str) -> str:
    start = text.index(f"function {name}(")
    return text[start : text.index("\n}\n", start) + 3]


def test_the_keys_are_vscodes_and_the_stepping_ones_wait_for_a_session():
    ext = _function(CODE, "docDebugExtension")
    for key in ('"F5"', '"Shift-F5"', '"F9"', '"F10"', '"F11"', '"Shift-F11"'):
        assert f"key: {key}" in ext, key
    #: F11 is Focus mode's (documents.js) unless a session is on, as VS Code
    #: shares it with full screen; F10 and Shift+F11 likewise wait.
    assert '{ key: "F11", run: () => docDebugOn() && docDebugAct("in") }' in ext
    focus = DOCS[DOCS.index('if (event.key !== "F11"') :]
    assert "if (docDebugOn()) return;" in focus[:400]


def test_the_palette_rows_name_the_same_keys():
    table = DOCS[DOCS.index("// DOC-COMMANDS-BEGIN") : DOCS.index("// DOC-COMMANDS-END")]
    for ident, keys in (("debug", "F5"), ("debug-breakpoint", "F9"), ("debug-over", "F10"),
                        ("debug-in", "F11 while debugging"), ("debug-out", "Shift+F11"), ("debug-stop", "Shift+F5")):
        row = table[table.index(f'id: "{ident}"') :]
        assert f'keys: "{keys}"' in row[: row.index("}")], ident


def test_the_debug_tab_is_a_tab_strip_and_four_views():
    panel = _function(CODE, "docRunPanel")
    #: Brief 71's dock: Debug is a row of `DOC_PANEL_TABS`, its pane the view.
    assert 'tabList.className = "tabs-line cm-panel-tabs";' in panel and 'tabList.setAttribute("role", "tablist");' in panel
    assert '["debug", pane("debug", debugView)]' in panel
    assert '{ id: "debug", label: "Debug", keys: "Ctrl+Shift+D" }' in CODE
    view = _function(CODE, "docDebugView")
    assert 'view.setAttribute("role", "tabpanel");' in view
    for title in ('"Variables"', '"Watch"', '"Call stack"', '"Breakpoints"'):
        assert title in view
    for cmd in ('"continue"', '"over"', '"in"', '"out"', '"stop"'):
        assert f"act({cmd}" in view


def test_what_a_program_said_is_shown_as_text():
    for name in ("docDebugRender", "docDebugValueRow", "docDebugLineButton", "docDebugEmpty"):
        body = _function(CODE, name)
        assert "innerHTML" not in body, name
    assert "v.textContent = value;" in _function(CODE, "docDebugValueRow")


def test_debug_says_why_in_one_line_where_it_cannot_run():
    assert "const DOC_DEBUG_CANNOT = {" in CODE
    run = _function(CODE, "docRunCode")
    assert "!self.crossOriginIsolated ? DOC_DEBUG_CANNOT.isolation" in run
    #: A stop holds the run's ten seconds; a step starts them again.
    assert "docRunArmTimeout(docRun.id);" in _function(CODE, "docDebugAct")


def test_the_session_is_one_object_not_lets():
    assert CODE.count("\nconst DOC_DEBUG = {") == 1
    assert "\nlet docDebug" not in CODE


def test_the_debug_tabs_chord_has_a_row_so_the_sheet_lists_it():
    """OPEN row 1062: Ctrl+Shift+D was answered by the editor but had no row
    in the command table, so the keys sheet and the palette did not list it."""
    table = DOCS[DOCS.index("// DOC-COMMANDS-BEGIN") : DOCS.index("// DOC-COMMANDS-END")]
    row = table[table.index('id: "debug-panel"') :]
    row = row[: row.index("},")]
    assert 'keys: "Ctrl+Shift+D"' in row and 'docPanelToggle("debug")' in row


def test_the_lane_under_a_finger_outranks_the_theme_and_is_the_touch_floor():
    """L886: the coarse rule named the lane at two classes and the editor theme's
    0.875rem at three, so the 1.5rem never applied (14px measured at 390 under
    touch emulation, docsverify-lane.js). It names four and takes the floor."""
    css = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")
    at = css.index("@media (pointer: coarse) {\n  .cm-editor .cm-gutters .cm-debug-gutter .cm-gutterElement")
    rule = css[at : css.index("}\n}", at)]
    assert "width: var(--target-min);" in rule
