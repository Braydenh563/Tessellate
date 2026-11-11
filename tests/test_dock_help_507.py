"""WORLD_CLASS_PLAN item 507: the dock audit's open items, pinned.

Each step adds its own test here so the layout it fixed cannot quietly come
back. The audit is `scratchpad/dock-audit-479.md`.
"""

from __future__ import annotations

import re
from pathlib import Path

INDEX = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
HTML = INDEX.read_text(encoding="utf-8")


def test_library_all_documents_and_bookmarks_docks_carry_a_help_popover():
    # The `data-help-for` recipe (DESIGN.md): button, `.help-body` panel, and
    # the id the dock grammar reads as the help utility (`*-help-toggle`).
    for button_id, panel_id in (
        ("library-help-toggle", "library-help"),
        ("library-docs-help-toggle", "library-docs-help"),
        ("bookmark-help-toggle", "bookmark-help"),
    ):
        button = re.search(rf'<button[^>]*id="{button_id}"[^>]*>', HTML)
        assert button, button_id
        tag = button.group(0)
        assert f'data-help-for="{panel_id}"' in tag
        assert f'aria-controls="{panel_id}"' in tag
        assert 'aria-label="' in tag
        panel = re.search(rf'<div class="help-body hidden" id="{panel_id}"', HTML)
        assert panel, panel_id


def test_reminders_card_has_one_worded_add():
    # The magic field's button is the sparkle alone, named by title and
    # aria-label; the form's "Add" is the card's one worded Add.
    magic = re.search(r'<button[^>]*id="reminder-magic-add"[^>]*>(.*?)</button>', HTML, re.S)
    assert magic
    tag = re.search(r'<button[^>]*id="reminder-magic-add"[^>]*>', HTML).group(0)
    assert "icon-only" in tag
    assert 'aria-label="Add from this sentence"' in tag
    assert re.sub(r"<[^>]+>", "", magic.group(1)).strip() == ""
    card = HTML[HTML.index('id="reminder-compose"') : HTML.index('id="reminder-presets"')]
    worded = re.findall(r"<button[^>]*>(?:\s*<i[^>]*></i>)?\s*Add\s*</button>", card)
    assert len(worded) == 1


def test_boards_and_maps_dock_has_one_new_split_button():
    """INBOX 1520 (819): one press of New makes a blank board; the arrow beside
    it holds the kinds and the templates. The split button is DESIGN.md's
    recipe (`.split-button`, `.split-button-main`, a `.split-button-slot` the
    caret's `kebabMenu` fills), so the dock keeps its one filled control."""
    dock_start = HTML.index('data-dock-name="library-boards"')
    dock = HTML[dock_start : HTML.index('id="wb-boards-intro"', dock_start)]
    split = re.search(r'<div[^>]*id="wb-boards-new-menu"[^>]*>(.*?)</div>', dock, re.S)
    assert split, "the New split button is a div in the dock"
    assert 'class="split-button' in split.group(0)
    body = split.group(1)
    main = re.search(r'<button id="wb-boards-new"[^>]*split-button-main[^>]*>', body)
    assert main, "the default press is the board button, with the id every caller presses"
    assert 'aria-label="New board"' in main.group(0)
    assert re.search(r'<span id="wb-boards-new-slot"[^>]*split-button-slot', body)
    assert "<details" not in split.group(0), "no details menu: the caret is a kebabMenu"
    outside = dock.replace(split.group(0), "")
    assert 'id="wb-boards-new"' not in outside, "no second create button beside the split"


def test_the_new_caret_lists_both_kinds_and_the_templates_with_a_hint_each():
    """The caret's rows are built by `wbNewMenuMount` (whiteboard.js) and keep
    the ids the old rows had, so the Library's and the Dashboard's New board and
    New mind map reach them as before. Each row's hint is its title: a kebab
    row has one line, and the word says what it makes."""
    wb = (INDEX.parent / "js" / "whiteboard.js").read_text(encoding="utf-8")
    start = wb.index("function wbNewMenuMount(")
    body = wb[start : wb.index("\n}\n", start)]
    for text in ("Whiteboard", "Mind map", "From a template"):
        assert text in body, text
    for ident in ("wb-boards-new-template", "wb-boards-new-map"):
        assert ident in body, ident
    assert body.count("title:") >= 3, "every row carries its hint as the title"
    assert "split-button-caret" in body


def test_documents_refresh_folds_on_a_phone_so_the_help_does_not_cost_a_row():
    # Measured at 390 with the new '?': New document, refresh, '?' and the more
    # menu did not fit one row and the dock went from 114px to 198px. Refresh
    # is the control that folds into the more menu there (`foldDockActions`),
    # as it does on Boards and maps.
    tag = re.search(r'<button[^>]*id="library-docs-refresh"[^>]*>', HTML).group(0)
    assert "data-fold-narrow" in tag


def test_graph_view_menu_is_folded_into_the_gears_panel():
    assert 'id="graph-view-menu"' not in HTML, "one way in: the gear"
    dock_start = HTML.index('data-dock-name="graph"')
    dock = HTML[dock_start : HTML.index('id="graph-selection-dock"', dock_start)]
    assert not re.search(r"class=\"[^\"]*dock-arrange", dock), "the Graph dock has no arrange zone left"
    panel = HTML[HTML.index('id="graph-options"') : HTML.index('id="graph-trace"')]
    section = panel.index('id="graph-view-section"')
    # The view section is the panel's first, ahead of physics.
    assert section < panel.index('id="graph-physics"')
    # Every option the menu offered is still reachable, by the same ids.
    for ident in ("graph-layout", "graph-colour", "graph-size", "graph-trace-toggle", "graph-legend-toggle"):
        assert f'id="{ident}"' in panel, ident
    for value in ("force", "tree", "radial", "arc"):
        assert f'<option value="{value}"' in panel[panel.index('id="graph-layout"') : panel.index('id="graph-colour"')], value
    # INBOX 670: the layout is a list beside Colour and Size, not a radio well.
    assert '<select id="graph-layout"' in panel and 'type="radio"' not in panel
    colour = panel[panel.index('id="graph-colour"') : panel.index('id="graph-size"')]
    for value in ("category", "cluster", "kind", "age", "space", "tag", "file"):
        assert f'<option value="{value}">' in colour, value
    # Labelled for keyboard and screen reader users: a label bound to each select.
    assert 'for="graph-colour"' in panel and 'for="graph-size"' in panel and 'for="graph-layout"' in panel
    assert 'aria-labelledby="graph-layout-label"' in panel


def test_the_options_panel_stays_open_when_a_button_in_it_rewrites_its_own_label():
    # Legend and Trace sit in the gear's panel and rewrite their own icon and
    # word (`setLabel`) when pressed, so the clicked `<i>` is detached by the
    # time the document's outside-click listener runs. Without the
    # `isConnected` guard that read as a click outside and closed the panel
    # (found by driving it, graph507.js). The comment is here, not in
    # wiring.js, because that file sits within bytes of its gzip ratchet.
    wiring = (INDEX.parent / "js" / "wiring.js").read_text(encoding="utf-8")
    start = wiring.index('document.addEventListener("click", (event) => {\n  const panel = document.getElementById("graph-options");')
    assert "event.target.isConnected" in wiring[start : start + 500]


# WORLD_CLASS_PLAN A8 (2026-10-04): every tab's dock ends with a '?'. Dashboard
# and Reminders were the two without one; the lint keeps it that way.
#: Docks with no '?', each with its reason. Empty: the Settings Logs dock was
#: the last, and has its own now (`logs-help-toggle`).
HELPLESS_DOCKS: set[str] = set()


def _docks_with_help() -> dict[str, bool]:
    from html.parser import HTMLParser

    void = {"input", "img", "br", "hr", "meta", "link", "source", "col", "area", "base", "embed", "track", "wbr"}

    class Walk(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.stack: list[tuple[str, str | None]] = []
            self.found: dict[str, bool] = {}

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if a.get("data-dock-name"):
                self.found[a["data-dock-name"]] = False
            if tag not in void:
                self.stack.append((tag, a.get("data-dock-name")))
            if "graph-help-toggle" in (a.get("class") or "").split() or "data-help-for" in a:
                for _tag, dock in self.stack:
                    if dock:
                        self.found[dock] = True

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    return

    walk = Walk()
    walk.feed(re.sub(r"<!--.*?-->", "", HTML, flags=re.S))
    return walk.found


def test_every_dock_carries_a_help_button():
    found = _docks_with_help()
    assert len(found) >= 15, found
    missing = sorted(name for name, has in found.items() if not has and name not in HELPLESS_DOCKS)
    assert not missing, f"docks with no '?' (the data-help-for recipe, DESIGN.md): {missing}"
    stale = sorted(name for name in HELPLESS_DOCKS if found.get(name))
    assert not stale, f"has a '?' now, remove from HELPLESS_DOCKS: {stale}"


def test_dashboard_and_reminders_help_follow_the_recipe():
    for button_id, panel_id in (
        ("dash-help-toggle", "dash-help"),
        ("reminders-help-toggle", "reminders-help"),
        ("logs-help-toggle", "logs-help"),
    ):
        tag = re.search(rf'<button[^>]*id="{button_id}"[^>]*>', HTML).group(0)
        assert f'data-help-for="{panel_id}"' in tag and f'aria-controls="{panel_id}"' in tag
        assert 'aria-label="' in tag and 'aria-expanded="false"' in tag
        panel = re.search(rf'<div class="help-body hidden" id="{panel_id}"[^>]*>\s*<p>(.*?)</p>', HTML, re.S)
        assert panel, panel_id
        text = panel.group(1)
        assert "\N{EM DASH}" not in text and "!" not in text, "copy rules: no em-dash, no exclamation mark"
