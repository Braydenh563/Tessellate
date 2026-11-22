"""Audit 1028 board and mind map UI rows: U12, U14 to U17, U21 to U28, U30, B12."""

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
WB = frontend_text("whiteboard.js")
MISC = (CSS / "07-whiteboard-misc.css").read_text(encoding="utf-8")
# The boot stylesheets are at their gzip cap (tests/test_boot_budget.py): these rows' rules are lazy.
LAZY = (CSS / "library-lazy.css").read_text(encoding="utf-8")


def _block(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    return source[start : source.index(end_marker, start)]


# U12 ------------------------------------------------------------------------


def _tool_keys() -> dict[str, str]:
    """tool -> the key text the board's own key table binds it to."""
    keys = {}
    table = _block(WB, "const WB_TOOL_KEYS = {", "\n  };")
    for letter, tool in re.findall(r'^\s{4}(\w): "([\w-]+)",', table, re.M):
        keys.setdefault(tool, letter.upper())
    shifted = _block(WB, "const WB_TOOL_SHIFT_KEYS = {", "\n  };")
    for letter, tool in re.findall(r'^\s{4}(\w): "([\w-]+)",', shifted, re.M):
        keys[tool] = "Shift+" + letter.upper()
    keys["image"] = "I"  # WB_ACTION_KEYS: the picture button
    return keys


def test_every_insert_item_with_a_key_shows_that_key_and_none_shows_a_wrong_one():
    menu = _block(HTML, 'id="wb-insert-menu"', 'id="wb-edit-menu"')
    keys = _tool_keys()
    seen = {}
    for item in re.findall(r'<button[^>]*data-wb-insert="([\w-]+)"[^>]*>(.*?)</button>', menu, re.S):
        tool, body = item
        hint = re.search(r"<kbd>(.*?)</kbd>", body)
        seen[tool] = hint.group(1) if hint else None
        assert seen[tool] == keys.get(tool), f"{tool}: menu shows {seen[tool]!r}, keys say {keys.get(tool)!r}"
    # The three the audit named (U12): the sticky said "click", the picture and the connector said nothing.
    assert seen["sticky"] == "N" and seen["image"] == "I" and seen["link-curved"] == "Shift+C"


# U14 ------------------------------------------------------------------------


def test_delete_stands_apart_from_undo_and_redo_in_the_dock_but_not_in_the_side_grid():
    rule = _block(LAZY, '.wb-tool-section-row > [data-tool="delete"] {', "}")
    assert "margin-inline-end: var(--space-3)" in rule  # 2px gap + 8px = 10px, over the 8px the audit asks
    side = _block(LAZY, '[data-dock="side"] .wb-tool-section-row > [data-tool="delete"] {', "}")
    assert "margin-inline-end: 0" in side  # the side dock is a four-cell grid that spaces its own cells


# U24 ------------------------------------------------------------------------

MAP = frontend_text("whiteboard-map.js")


def test_a_topic_inside_the_slide_margin_of_the_edge_is_revealed_not_left_there():
    start = MAP.index("function wbMapRevealTopic(")
    reveal = MAP[start : MAP.index("\n}\n", start)]
    # One margin, declared once, used for both the "is it at the edge" test and the slide to it.
    assert reveal.count("const m = 24;") == 1
    assert reveal.index("const m = 24;") < reveal.index("wbRectEscapes(el.getBoundingClientRect(), inset)")
    assert "right: free.right - m" in reveal and "left: free.left + m" in reveal
    assert "wbRectEscapes(el.getBoundingClientRect(), free)" not in reveal


# U16 ------------------------------------------------------------------------


def test_the_sidebar_tabs_are_32px_and_keep_the_touch_floor():
    rule = _block(LAZY, "#wb-sidebar .wb-side-tab {", "}")
    # max() so a coarse pointer keeps its 44px (--target-min) and a mouse gets 32 (--button-min-h), not the 28 floor.
    assert "min-width: max(var(--button-min-h), var(--target-min))" in rule
    assert "min-height: max(var(--button-min-h), var(--target-min))" in rule
    tokens = (CSS / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert "--button-min-h: 2rem;" in tokens


# U22 ------------------------------------------------------------------------


def test_the_phone_bar_is_one_row_and_the_format_panel_stays_reachable_from_more():
    start = LAZY.index("@media (max-width: 599.98px) {\n  .wb-topbar #wb-format-btn")
    rule = LAZY[start : LAZY.index("\n}\n", start) + 3]
    assert ".wb-topbar #wb-format-btn" in rule and ".wb-menu-caret" in rule and "display: none" in rule
    assert ".wb-topbar .wb-topbar-right {\n    gap: 0;" in rule
    # The button goes, the command stays: More lists every command the bar does not carry (wbPhoneCarries).
    commands = (JS / "whiteboard-commands.js").read_text(encoding="utf-8")
    assert 'id: "format-panel"' in commands and 'menu: "Format panel"' in commands
    # The picker's phone face is the name alone and its tooltip the whole row.
    assert "opt.dataset.faceNarrow = board.title;" in WB


# U25 ------------------------------------------------------------------------


def test_the_fold_chevron_and_count_start_outside_the_topics_edge():
    side = _block(LAZY, ".wb-map-collapse {\n  right: auto;", "}")
    assert "left: calc(100% + var(--space-1))" in side
    # Scaled from the inner edge: the zoom floor grows it away from the topic, never over it.
    assert "transform-origin: 0 50%" in side
    down = _block(LAZY, ".wb-map-down .wb-map-collapse {\n  right: auto;", "}")
    assert "top: calc(100% + var(--space-1))" in down and "left: 50%" in down and "translate: -50% 0" in down
    assert "transform-origin: 50% 0" in down
    count = _block(LAZY, ".wb-map-count {\n  right: auto;", "}")
    assert "left: calc(100% + var(--space-1))" in count


# U27 ------------------------------------------------------------------------


def test_every_layout_option_names_an_icon_and_a_menu_row_draws_it():
    layout = _block(HTML, 'id="wb-map-layout"', "</select>")
    options = re.findall(r'<option value="([\w-]+)" data-icon="([\w-]+)"', layout)
    assert len(options) == len(re.findall(r"<option ", layout)) == 10
    # One glyph each: a row you cannot tell from its neighbour at a glance is the text-only menu again.
    assert len({icon for _, icon in options}) == 10
    vendor = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "vendor").rglob("*.css"))
    for _, icon in options:
        assert f".ph-{icon}:before" in vendor, icon
    selects = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    row = _block(selects, "const buildOptionRow = (option) => {", "row.addEventListener")
    # The glyph is built by `optionGlyph`, shared with the opener's face; the row must prepend it.
    glyph = _block(selects, "const optionGlyph = (option) => {", "return glyph;")
    assert "optionGlyph(option)" in row and "row.prepend(glyph)" in row
    assert "option?.dataset.icon" in glyph and "ph-lead" in glyph and 'setAttribute("aria-hidden", "true")' in glyph


# U28 ------------------------------------------------------------------------


def test_the_size_readout_is_one_scale_never_pixels():
    import json
    import shutil
    import subprocess

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = MAP.index("function wbMapSizeName(")
    fn = MAP[start : MAP.index("\n};\n", start) + 2] + "\n"
    steps = "[{name:'S',px:12},{name:'M',px:14},{name:'L',px:19},{name:'XL',px:25}]"
    script = fn + f"console.log(JSON.stringify([12,14,19,25,22,17,30,10,16].map((n) => wbMapSizeName(n, {steps}))));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    # On a step: its name. Between two: the step below with a plus. Under the smallest: the smallest.
    assert json.loads(out) == ["S", "M", "L", "XL", "L+", "M+", "XL+", "S", "M+"]
    stepper = MAP[MAP.index("function wbMapSizeStepper(") :]
    assert "`${size}px`" not in stepper[: stepper.index("\n}\n")].split("const nameOf")[1].split("\n")[0]


# U21 ------------------------------------------------------------------------


def test_the_tools_sheet_puts_each_tools_name_under_its_icon_and_takes_it_out_on_close():
    sheet = WB[WB.index("function wbOpenToolsSheet(") :]
    sheet = sheet[: sheet.index("\n  }\n")]
    assert 'className = "wb-tool-word"' in sheet and 'classList.add("wb-tool-worded")' in sheet
    # The key hint in the tooltip is not part of the word, and the rail is untouched above the sheet.
    assert r'.replace(/\s*\(.*$/, "")' in sheet
    close = sheet[sheet.index("onClose:") :]
    assert 'classList.remove("wb-tool-worded")' in close and "word.remove()" in close
    tile = _block(LAZY, ".wb-tools-palette button.wb-tool-worded {", "}")
    assert "flex-direction: column" in tile and "aspect-ratio: auto" in tile and "max-width: 4.75rem" in tile
    word = _block(LAZY, ".wb-tool-word {", "}")
    assert "text-overflow: ellipsis" in word and "var(--text-xs)" in word
    # Two lines then cut, centred in a box of its own width: a one-line nowrap word was cut on both sides.
    assert "line-clamp: 2" in word and "width: 100%" in word and "text-align: center" in word
    # The two sentence-length names get one short word each, which the full name still contains.
    for full, word in re.findall(r'^\s+"([\w ]+)": "(\w+)",$', _block(sheet, "const short = {", "};"), re.M):
        assert word.lower() in full.lower()
    assert '"Upload an image onto the board": "Image"' in sheet and '"Lasso select": "Lasso"' in sheet



# U26 ------------------------------------------------------------------------


def test_the_template_offers_close_button_is_a_real_target_and_the_strip_keeps_its_scroll_cue():
    rule = _block(LAZY, "#wb-map-templates-dismiss {", "}")
    # 32px with a mouse (the button floor), 44px under touch (the target floor): it was 28px.
    assert "min-width: max(var(--button-min-h), var(--target-min))" in rule
    assert "min-height: max(var(--button-min-h), var(--target-min))" in rule
    # A tile cut at the strip's right edge is the cue that the row scrolls: the fade is what says so.
    assert 'class="wb-map-templates-row edge-fade scroll-row" id="wb-map-template-row"' in HTML


# B12 ------------------------------------------------------------------------


def test_the_shortcut_sheet_reads_each_commands_surface_so_a_shared_key_is_never_ambiguous():
    commands = (JS / "whiteboard-commands.js").read_text(encoding="utf-8")
    render = _block(commands, "function renderWbShortcutSheet(list) {", "\n}\n")
    # With a board open: that surface's keys only. Otherwise every key, a shared one naming its surface.
    assert 'wbIsMap() ? "map" : "board"' in render
    assert 'command.surface !== "both" && command.surface !== here' in render
    assert '" (mind map)" : " (board)"' in render
    # The ambiguity is real in the table: a key bound on both surfaces (M, Ctrl+Shift+S).
    by_key: dict[str, set[str]] = {}
    for keys, surface in re.findall(r'keys: "([^"]+)", surface: "(board|map)"', commands):
        by_key.setdefault(keys, set()).add(surface)
    assert any(len(s) == 2 for s in by_key.values())
