"""The Calculator and equations UX audit (INBOX 1530 g, d231b19).

Static checks of the dialog's wiring, one block per finding; the measured side
(strip position, tab stops, widths) is the sweep named in each CHANGELOG line.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


# --- the stale caught box (popupToolMaths) --------------------------------------


def test_a_tool_is_handed_its_box_never_a_remembered_one() -> None:
    features = _read("app-features.js")
    head = features.split("async function popupToolMaths(", 1)[1].split("{", 1)[0]
    assert "paletteCaught" not in head, "popupToolMaths must not default to the palette's last box"
    body = features.split("async function popupToolMaths(", 1)[1].split("\n}\n", 1)[0]
    assert "paletteCaught" not in body


def test_the_palette_caught_box_is_live_only_while_the_palette_runs_a_row() -> None:
    palette = _read("app-palette.js")
    run = palette.split("function paletteRun(", 1)[1].split("\n}\n", 1)[0]
    assert "paletteCaught.live = true" in run and "paletteCaught.live = false" in run
    assert "finally" in run, "a row that throws must not leave the caught box live"
    panes = _read("settings-panes.js")
    now = panes.split("function paletteCaughtNow()", 1)[1].split("\n}\n", 1)[0]
    assert ".live" in now, "outside a palette run there is no caught box"


def test_the_palette_rows_read_the_caught_box_before_they_wait() -> None:
    features = _read("app-features.js")
    tools = next(line for line in features.splitlines() if "...POPUP_TOOLS.map((t) =>" in line)
    assert "t.open(paletteCaughtNow().target)" in tools
    count = next(line for line in features.splitlines() if "Count words" in line and "act:" in line)
    assert count.index("paletteCaughtNow()") < count.index("ensureModule"), "read after the wait, the palette's run is over"


def test_only_the_palette_and_its_reader_name_the_caught_const() -> None:
    for path in sorted(JS.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//", 1)[0]
            if re.search(r"\bpaletteCaught\b(?!Now)", code):
                assert path.name in {"app-palette.js", "settings-panes.js"}, f"{path.name}:{number} reads paletteCaught"


# --- one action row (H2, M1, L2, L6) and a still strip (M2) -------------------------


def _kit() -> str:
    return _read("reply-kit.js")


def test_the_three_tabs_share_one_action_row() -> None:
    kit = _kit()
    assert "function replyCalcActions(" in kit
    build = kit.split("function replyCalcBuild(", 1)[1].split("// CALC-TEX-BEGIN", 1)[0]
    assert "replyCalcActions(" in build and "calc-panes" in build
    for pane in ("replyCalcWorkPane", "replyCalcConvertPane", "replyCalcEquation"):
        assert pane in build
    #: No pane draws buttons of its own any more: the old Insert row, the Convert
    #: pane's none, and the editor's own foot with its Cancel.
    assert "calc-insert-row" not in kit and "calc-result-row" not in kit
    editor = _read("math-editor.js")
    assert "mathEditorFoot" not in editor and "math-editor-foot" not in editor
    assert "Cancel" not in editor
    css = (CSS / "reply-kit-lazy.css").read_text(encoding="utf-8")
    assert "calc-insert-row" not in css and "math-editor-foot" not in (CSS / "math-editor-lazy.css").read_text(encoding="utf-8")


def test_the_action_row_says_where_insert_writes_and_why_it_cannot() -> None:
    actions = _kit().split("function replyCalcActions(", 1)[1].split("\nfunction ", 1)[0]
    #: The reason is a line on screen, tied to the buttons, not a tooltip.
    assert "calc-where" in actions and "aria-describedby" in actions
    assert "writes into" in actions
    assert "No text box is open" in actions
    #: A button that cannot act stays reachable (aria-disabled) and says why when pressed.
    assert "aria-disabled" in actions and "toast(" in actions
    assert '"Copy"' in actions and '"Insert"' in actions and '"ph:function Insert as equation"' in actions
    #: Copy has its own tooltip, never the Insert one (the Equation tab's Copy kept it).
    editor = _read("math-editor.js")
    assert "Write the equation into the text (Ctrl+Enter)" not in editor
    assert "copyTitle: \"Copy the equation" in _kit()


def test_the_card_is_one_height_and_the_strip_is_pinned() -> None:
    css = (CSS / "reply-kit-lazy.css").read_text(encoding="utf-8")
    card = css.split(".sheet-card.calc-card", 1)[1].split("}", 1)[0]
    assert "height:" in card and "overflow: hidden" in card
    panes = css.split(".calc-panes {", 1)[1].split("}", 1)[0]
    assert "overflow-y: auto" in panes and "min-height: 0" in panes
    assert "card.classList.add(\"calc-card\")" in _kit()


def test_tab_labels_are_all_nouns() -> None:
    tabs = _kit().split("const replyCalc =", 1)[1].split("\n", 1)[0]
    assert '["work", "Sum"]' in tabs and '["convert", "Units"]' in tabs and '["equation", "Equation"]' in tabs


# --- tabs that name their panels (M3), an arrow that stays on the tab (M4) ----------


def _build() -> str:
    return _kit().split("function replyCalcBuild(", 1)[1].split("function replyCalcActions(", 1)[0]


def test_each_tab_controls_a_labelled_panel() -> None:
    build = _build()
    assert 'setAttribute("aria-controls"' in build and 'setAttribute("aria-labelledby"' in build
    assert "pane.id" in build and "button.id" in build
    #: Ids carry the dialog's number: a dialog still leaving never shares one with the next.
    assert "replyCalc.opened" in build


def test_an_arrow_onto_equation_leaves_focus_on_the_tab() -> None:
    build = _build()
    assert "const select = (key, { focus = true } = {})" in build
    keys = build.split('modes.addEventListener("keydown"', 1)[1].split("modes.append", 1)[0]
    assert "focus: false" in keys and ".click()" not in keys
    kit = _kit()
    assert "const mount = ({ focus = true } = {})" in kit
    editor = _read("math-editor.js")
    assert "function mathEditorMount({ host, target = null, done = () => {}, note = null, onTex = () => {}, focus = true, log = null })" in editor
    assert "if (focus) afterFrames(() => setTimeout(() => host.isConnected && pane.start()), 1);" in editor


# --- one Tab stop per palette group (M5) -------------------------------------------


def test_the_palette_tiles_are_a_roving_tab_stop_per_group() -> None:
    editor = _read("math-editor.js")
    #: A local of the mount, not a new name in the shared scope.
    assert "const roving = (list) =>" in editor and "function mathEditorRoving" not in editor
    palette = editor.split("function mathEditorPalette(", 1)[1].split("\n}\n", 1)[0]
    assert "firstChild.tabIndex = 0" in palette
    assert "button.tabIndex = -1" in editor.split("function mathEditorTile(", 1)[1].split("\n}\n", 1)[0]
    roving = editor.split("const roving = (list) =>", 1)[1].split("\n  };\n", 1)[0]
    for key in ("ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"):
        assert key in roving
    assert "focusin" in roving
    assert "roving(list);" in editor


# --- the head's '?' (M6) and Inline/Display as a .seg (L3) --------------------------


def test_the_dialog_has_one_head_help_and_the_editor_has_none_of_its_own() -> None:
    build = _build()
    assert 'setAttribute("data-help-for", helpId)' in build and 'setAttribute("aria-controls", helpId)' in build
    assert "dialog-head-btn" in build and "help-body hidden" in build
    assert "REPLY_CALC_HELP" in _kit()
    opener = _kit().split("function openCalculator(", 1)[1].split("function replyCalcBuild(", 1)[0]
    assert "sub:" not in opener, "the sub line is replaced by the help"
    editor = _read("math-editor.js")
    assert "math-editor-help" not in editor and "mathEditorHelp" not in editor and "initHelpToggles" not in editor


def test_inline_and_display_are_a_seg_of_pressed_buttons() -> None:
    editor = _read("math-editor.js")
    modes = editor.split("function mathEditorModes(", 1)[1].split("\n}\n", 1)[0]
    assert 'className = "seg math-editor-mode"' in modes and 'setAttribute("role", "group")' in modes
    assert "aria-pressed" in modes and "tablist" not in modes and '"tab"' not in modes


# --- a preview that says so, and a live region that waits (L1) ----------------------


def test_a_preview_is_worded_not_only_greyed() -> None:
    kit = _kit()
    result = kit.split("function replyCalcResult(", 1)[1].split("\n}\n", 1)[0]
    assert "calc-tag" in result and "Preview" in kit
    show = kit.split("function replyCalcShow(", 1)[1].split("\n}\n", 1)[0]
    assert ".calc-tag\").hidden = final" in show


def test_the_result_is_announced_once_it_settles_not_per_key() -> None:
    kit = _kit()
    result = kit.split("function replyCalcResult(", 1)[1].split("\n}\n", 1)[0]
    assert 'out.setAttribute("aria-live"' not in result, "the visible figure is not the live region"
    assert "visually-hidden" in result and 'role", "status"' in result.replace("'", '"') or 'setAttribute("role", "status")' in result
    show = kit.split("function replyCalcShow(", 1)[1].split("\n}\n", 1)[0]
    assert "setTimeout" in show and "clearTimeout" in show
    #: Enter and = announce at once; typing waits for a pause.
    assert "now" in show


# --- Convert: a row that fits (L5) ---------------------------------------------------


def test_convert_puts_the_amount_on_its_own_row_and_stacks_at_phone_width() -> None:
    css = (CSS / "reply-kit-lazy.css").read_text(encoding="utf-8")
    row = css.split(".calc-convert-row {", 1)[1].split("}", 1)[0]
    #: Units get a row of their own (the openers measured 86 px at 320, clipping "kilometres an hour").
    assert "minmax(0, 1fr) auto minmax(0, 1fr)" in row
    assert ".calc-convert-row .calc-amount" in css
    narrow = css.split("@media (max-width: 599.98px)", 1)[1]
    assert ".calc-convert-row" in narrow and "grid-template-columns: minmax(0, 1fr)" in narrow
    #: The DOM order is the visual order at every width: amount, from, swap, to.
    pane = _kit().split("function replyCalcConvertPane(", 1)[1]
    assert "row.append(amount, from, swap, to);" in pane
