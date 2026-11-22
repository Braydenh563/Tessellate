"""The diagram builder's ... menu is five submenus, not 15 flat rows (the owner, 2026-11).

Spacing and Lines are radio rows (the chosen one is `current`, pressing it again goes back to the usual), Look holds two
checkbox rows, Save as and Copy as hold the exports, and Keyboard shortcuts and a danger Clear close the top level.
The flyout, keys, aria and phone nested level are the shared submenu recipe (menus.js `buildMenuGroupButton`).
"""

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")
KINDBAR = (JS / "diagram-kindbar.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
MENUS = (JS / "menus.js").read_text(encoding="utf-8")


def _labels(block: str) -> list[str]:
    return re.findall(r'"ph:[a-z-]+ ([^"]+)"', block)


def test_the_host_menu_holds_three_settings_submenus_and_slots_for_save_and_clear() -> None:
    menu = EMBED.split("get menu() {", 1)[1].split("get canUndo()", 1)[0]
    for label, items in (("Spacing", "spacingRows()"), ("Lines", "curveRows()"), ("Look", "[lookRow(), wrapRow()]")):
        assert re.search(rf'label: "ph:[a-z-]+ {label}", group: "view", items: {re.escape(items)}', menu), label
    assert 'slot: "save"' in menu and 'slot: "clear", danger: true' in menu
    spacing = EMBED.split("function spacingRows() {", 1)[1].split("function lookRow()", 1)[0]
    assert _labels(spacing) == ["Compact", "Roomy"] and "current: level === now" in spacing
    lines = EMBED.split("function curveRows() {", 1)[1].split("//: The spacing rows", 1)[0]
    assert _labels(lines) == ["Straight", "Curved", "Stepped"] and "current: shape === now" in lines
    look = EMBED.split("function lookRow() {", 1)[1].split("const apply", 1)[0]
    assert _labels(look) == ["Hand-drawn look"] and "current: hand" in look
    assert '"ph:text-align-left Wrap long lines"' in EMBED and 'current: field.getAttribute("wrap") !== "off"' in EMBED


def test_the_top_level_ends_with_shortcuts_then_clear_as_a_separated_danger_row() -> None:
    more = KINDBAR.split("function more(", 1)[1].split("diagramModel.kindbar =", 1)[0]
    assert _labels(more.split("...folded", 1)[1].split("Save as", 1)[0]) == []
    assert re.search(r'"ph:download-simple Save as", group: "out", items: \[item\("ph:file-svg SVG", "svg"\), item\("ph:file-png PNG", "png"\), \.\.\.slot\("save"\)\]', more)
    assert re.search(r'"ph:copy Copy as", group: "out", items: \[item\("ph:image Picture", "picture"\), item\("ph:code Mermaid", "mermaid"\), item\("ph:file-svg SVG", "svgtext"\)\]', more)
    order = [more.index(w) for w in ("Save as", "Copy as", "Keyboard shortcuts", 'slot("clear")')]
    assert order == sorted(order), "Clear is not last"
    assert 'group: "danger"' in more and 'group: "help"' in more
    assert "kindbar.more(S, DIRS, suggestMenu" in BUILDER and "kebabMenu(rows," in BUILDER
    #: A state change without a redraw (Wrap) rebuilds the menu, and a chosen row is part of the rebuild key.
    assert 'root.addEventListener("dgm:menu"' in BUILDER and 'row.current ? "*"' in KINDBAR


def test_a_submenu_row_can_be_marked_current() -> None:
    row = MENUS.split("function buildMenuItemButton(", 1)[1].split("\n}\n", 1)[0]
    assert 'item.current) button.setAttribute("aria-current", "true")' in row
