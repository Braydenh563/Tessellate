"""The dashboard's Quick access row (INBOX 461).

The owner, of the Start something row: "make this start something section on
the dashboard customisable like a quick access section?? what is there can be
default". The five tiles are the default; a person adds commands from the
palette's own catalogue, removes, reorders (drag, or Move left and right in the
tile's menu) and resets. Stored per user in preferences, not in the browser.

Three layers, one test group each: the stored list (the API), the choice of
what to draw from it (the dashboard's pure resolver, run in node), and the
ratchets that keep the row drawing from the catalogue rather than from a list
somebody typed into the dashboard.
"""

from __future__ import annotations

import json
from tests._app_js import with_pieces
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.api.routes_settings import QUICK_ACCESS_MAX

ROOT = Path(__file__).resolve().parents[1]
DASH = with_pieces("dashboard.js")
EDIT = (ROOT / "frontend" / "js" / "quick-access.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")

DEFAULT_IDS = ["new-note", "ask-ai", "sketch", "remind-me", "meeting-notes"]


# --- the stored list ----------------------------------------------------------


def test_a_fresh_notebook_has_no_stored_list(client):
    assert client.get("/preferences").json()["dashboard_quick_access"] == []


def test_the_list_round_trips_in_order(client):
    ids = ["tab:graph", "new-note", "reveal:doc-new"]
    put = client.put("/preferences", json={"dashboard_quick_access": ids}).json()
    assert put["dashboard_quick_access"] == ids
    assert client.get("/preferences").json()["dashboard_quick_access"] == ids


def test_the_server_cleans_what_it_stores(client):
    """Strings only, trimmed, no repeats, short, and no more than the row holds."""
    dirty = ["a", " a ", "", "   ", "b", "x" * 81] + [f"k{i}" for i in range(20)]
    saved = client.put("/preferences", json={"dashboard_quick_access": dirty}).json()
    ids = saved["dashboard_quick_access"]
    assert ids[:2] == ["a", "b"]
    assert len(ids) == QUICK_ACCESS_MAX
    assert len(set(ids)) == len(ids) and all(ids) and all(len(i) <= 80 for i in ids)


def test_reset_is_an_empty_list_and_survives_a_reload(client):
    client.put("/preferences", json={"dashboard_quick_access": ["tab:graph"]})
    assert client.put("/preferences", json={"dashboard_quick_access": []}).json()["dashboard_quick_access"] == []
    assert client.get("/preferences").json()["dashboard_quick_access"] == []


def test_other_preferences_do_not_touch_it(client):
    client.put("/preferences", json={"dashboard_quick_access": ["tab:graph"]})
    client.put("/preferences", json={"display_name": "Sam"})
    assert client.get("/preferences").json()["dashboard_quick_access"] == ["tab:graph"]


# --- what is drawn from it ----------------------------------------------------


def _block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(end, begin) + len(end)]


def _resolve(saved, catalogue_ids):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = (
        f"const QUICK_ACCESS_MAX = {QUICK_ACCESS_MAX};\n"
        + _block(DASH, "const QUICK_START = [", "\n];\n")
        + "\n"
        + _block(DASH, "function quickAccessItems(", "\n}\n")
        + "\nconst [saved, ids] = JSON.parse(process.argv[1]);\n"
        "const catalogue = new Map(ids.map((id) => [id, { id, label: id }]));\n"
        "process.stdout.write(JSON.stringify(quickAccessItems(saved, catalogue).map((l) => l.id)));\n"
    )
    out = subprocess.run(
        [node, "-e", script, json.dumps([saved, catalogue_ids])],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_default_is_the_five_tiles_it_replaced():
    assert _resolve([], []) == DEFAULT_IDS
    assert _resolve(None, []) == DEFAULT_IDS


def test_a_saved_list_is_drawn_in_its_order_from_both_sources():
    saved = ["tab:graph", "ask-ai", "reveal:doc-new"]
    assert _resolve(saved, ["tab:graph", "reveal:doc-new"]) == saved


def test_unknown_ids_are_dropped_and_repeats_collapse():
    saved = ["gone:x", "ask-ai", "ask-ai", "tab:graph", "tab:renamed-away"]
    assert _resolve(saved, ["tab:graph"]) == ["ask-ai", "tab:graph"]


def test_a_list_that_resolves_to_nothing_is_the_default():
    assert _resolve(["gone:x", "gone:y"], []) == DEFAULT_IDS
    assert _resolve("not a list", []) == DEFAULT_IDS


def test_the_row_never_draws_more_than_eight():
    many = [f"tab:t{i}" for i in range(12)]
    assert len(_resolve(many, many)) == QUICK_ACCESS_MAX == 8


# --- the ratchets -------------------------------------------------------------


def test_the_default_ids_are_the_only_hard_coded_tiles():
    start = _block(DASH, "const QUICK_START = [", "\n];\n")
    assert re.findall(r'\bid: "([^"]+)"', start) == DEFAULT_IDS
    assert re.findall(r'label: "([^"]+)"', start) == ["New note", "Ask AI", "Sketch", "Remind me", "New meeting"]


def test_an_act_row_is_a_tile_only_when_it_opts_in_with_quick():
    """Live captions is a palette act (no tab, no reveal), so it was never a
    tile (libr-1011 row 1220). An act row names itself with `quick`, which is
    its stable `act:` id; an act without it stays out of the picker."""
    catalogue = _block(DASH, "function quickCatalogue()", "\n}\n")
    assert "row.quick ? `act:${row.quick}`" in catalogue
    panes = (ROOT / "frontend" / "js" / "settings-panes.js").read_text(encoding="utf-8")
    row = panes[panes.index('label: "ph:closed-captioning Live captions"') :].split("\n", 1)[0]
    assert 'quick: "captions"' in row and "act: () => toggleLiveCaptions()" in row
    assert len(re.findall(r'\bquick: "', panes)) == 1


def test_the_row_draws_from_the_command_catalogue_not_a_list_of_its_own():
    """Added tiles come from `paletteCommands` rows that declare a `tab` or a
    `reveal`, with the line the row already says: no second list of what the
    app can do, and no new closures."""
    catalogue = _block(DASH, "function quickCatalogue()", "\n}\n")
    assert "paletteCommands()" in catalogue and "paletteRowParts(" in catalogue
    assert "row.tab" in catalogue and "row.reveal" in catalogue and "run: row.run" in catalogue
    assert "=>" not in catalogue.replace("run: row.run", "")
    draw = _block(DASH, "function renderQuickLinks()", "\n}\n")
    assert "quickAccessCurrent()" in draw and "QUICK_START" not in draw
    assert "quickCatalogue()" in _block(DASH, "function quickAccessCurrent()", "\n}\n")
    # And the picker reads the same catalogue.
    assert "quickCatalogue()" in EDIT


def test_customise_and_reset_are_rows_of_the_dashboard_customise_menu():
    """INBOX 488: the row's own ⋯ sat under the dock's ⋯, whose menu opened
    over it. Editing and resetting the row are rows of the dock's Customise
    menu now, beside the view, the widgets and the layout."""
    draw = _block(DASH, "function renderQuickLinks()", "\n}\n")
    #: Since 2026-10-10 the heading's line carries the same rows as a ⋯ (the
    #: owner's ask); it is the Customise items, never a menu of its own.
    assert draw.count("kebabMenu(") == 1 and "kebabMenu(dashCustomiseItems().filter(" in draw
    custom = _block(DASH, "function dashCustomiseItems()", "\n}\n")
    assert "Edit quick access" in custom and "Reset quick access" in custom
    assert "saveQuickAccess([])" in custom and "quickEditing = true" in custom


def test_the_row_view_has_a_keyboard_route_and_no_hand_built_menu():
    assert "Move left" in EDIT and "Move right" in EDIT and "Remove" in EDIT
    assert "kebabMenu(" in EDIT and "dashDragOverCard(" in EDIT
    # No hand-built menu or option list in the editing view.
    assert 'role="menu"' not in EDIT and 'setAttribute("role", "menu")' not in EDIT


# --- the manager (INBOX 524) --------------------------------------------------


def _node_helpers(expr: str):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = (
        _block(EDIT, "function quickAccessMoved(", "\n}\n")
        + "\n"
        + _block(EDIT, "function quickAccessReslotted(", "\n}\n")
        + f"\nprocess.stdout.write(JSON.stringify({expr}));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_move_swaps_with_the_neighbour_you_can_see():
    """Alt+Up on the second tile swaps it with the first; with a search narrowing
    the list, the neighbour is the next visible one, not the next stored one."""
    assert _node_helpers('quickAccessMoved(["a","b","c"], ["a","b","c"], "b", -1)') == ["b", "a", "c"]
    assert _node_helpers('quickAccessMoved(["a","b","c"], ["a","c"], "c", -1)') == ["c", "b", "a"]
    assert _node_helpers('quickAccessMoved(["a","b"], ["a","b"], "a", -1)') == ["a", "b"]
    assert _node_helpers('quickAccessMoved(["a","b"], ["a","b"], "b", 1)') == ["a", "b"]


def test_a_drag_puts_the_visible_tiles_back_in_the_slots_they_held():
    assert _node_helpers('quickAccessReslotted(["a","b","c","d"], ["c","a"])') == ["c", "b", "a", "d"]
    assert _node_helpers('quickAccessReslotted(["a","b","c"], ["c","b","a"])') == ["c", "b", "a"]


def test_the_manager_is_one_list_you_check_drag_and_save_once():
    """What the owner asked: which are added is visible (a check on each row),
    several can be toggled at once, the added set reorders by drag and by
    Alt+Up and Alt+Down, the search stays, and there is one Done."""
    manage = _block(EDIT, "function quickAccessManage(", "\n}\n")
    assert 'type = "checkbox"' in manage and "note-picker-check" in manage
    assert "draggable" in manage and "dragover" in manage and "dragend" in manage
    assert "event.altKey" in manage and '"ArrowUp"' in manage and '"ArrowDown"' in manage
    assert 'type = "search"' in manage and "QUICK_ACCESS_MAX" in manage
    # Nothing is saved until Done: one commit in the whole manager, and it is Done's.
    assert manage.count("quickAccessCommit(") == 1
    assert "closes the picker and adds" not in manage
    # A refusal (a ninth tile, the last one off) is a line in the dialog, never an
    # error toast with "Report this": it is validation, not a fault.
    assert "toast(" not in manage and "notice-warn" in manage
    # The row view's Add tile opens it.
    assert "quickAccessManage(" in _block(EDIT, "async function quickAccessEdit()", "\n}\n")
    # A drag has an alternative that needs no dragging (WCAG 2.5.7).
    assert "Move ${" in manage and "quick-manage-move" in manage


def test_it_is_stored_in_preferences_not_only_the_browser():
    save = _block(DASH, "async function saveQuickAccess(", "\n}\n")
    assert "/preferences" in save and "dashboard_quick_access" in save
    assert "localStorage" not in save and "localStorage" not in EDIT


def test_the_editing_view_is_lazy_and_reachable_before_it_loads():
    assert 'quickAccess: ["/css/quick-access-lazy.css", "/js/quick-access.js"]' in APP
    assert 'quickAccess: ["quickAccessEdit"]' in APP
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "quick-access.js" not in page, "it loads on first use, not at boot"
    assert "QUICK_ACCESS_MAX = 8;" in DASH


def test_the_section_is_named_quick_access():
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="dash-quicklinks" role="group" aria-label="Quick access"' in page
    assert 'heading.textContent = "Quick access"' in DASH


# --- highlights (INBOX 589) ---------------------------------------------------
#
# The owner: "only the new note link widget is a different colour. should the
# one in the first position be highlighted by default with the option to
# highlight the others other colours too??" The first tile carries the accent
# by its position, whatever it is; any tile can be given one of the category
# hues, the accent, or no highlight, and an explicit choice wins.


def test_highlights_round_trip_and_default_to_none_stored(client):
    assert client.get("/preferences").json()["dashboard_quick_tints"] == {}
    tints = {"ask-ai": "teal", "new-note": "none", "tab:graph": "accent"}
    assert client.put("/preferences", json={"dashboard_quick_tints": tints}).json()["dashboard_quick_tints"] == tints
    assert client.get("/preferences").json()["dashboard_quick_tints"] == tints


def test_the_server_keeps_only_known_highlights(client):
    """A tint ends up in a CSS custom property, so only the palette's keys, the
    accent and "none" are stored: no hex, no named CSS colour, nothing else."""
    dirty = {"a": "teal", "b": "#ff0000", "c": "red; x: y", "": "teal", "x" * 81: "teal", "d": 3, "e": "accent"}
    saved = client.put("/preferences", json={"dashboard_quick_tints": dirty}).json()["dashboard_quick_tints"]
    assert saved == {"a": "teal", "e": "accent"}
    many = {f"k{i}": "blue" for i in range(40)}
    assert len(client.put("/preferences", json={"dashboard_quick_tints": many}).json()["dashboard_quick_tints"]) <= 32


def _tint(expr: str):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = (
        'const CATEGORY_PALETTE = { teal: "#159172", blue: "#387fe3" };\n'
        + _block(DASH, "function quickTintKey(", "\n}\n")
        + f"\nprocess.stdout.write(JSON.stringify({expr}));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_first_tile_is_highlighted_by_position_not_by_name():
    # Whatever is first carries the accent; nothing else does by default.
    assert _tint('["sketch", "new-note", "ask-ai"].map((id, i) => quickTintKey(id, i, {}))') == ["accent", "", ""]
    assert _tint('["new-note", "ask-ai"].map((id, i) => quickTintKey(id, i, null))') == ["accent", ""]


def test_an_explicit_highlight_wins_over_the_position():
    tints = '{"sketch": "none", "ask-ai": "teal", "remind-me": "accent", "x": "nonsense"}'
    got = _tint(f'["sketch", "ask-ai", "remind-me", "x"].map((id, i) => quickTintKey(id, i, {tints}))')
    assert got == ["", "teal", "accent", ""]
    # An unknown stored value falls back to the position's default.
    assert _tint('quickTintKey("x", 0, {"x": "nonsense"})') == "accent"


def test_the_tile_is_painted_through_the_cssom_and_new_note_is_not_special():
    start = _block(DASH, "const QUICK_START = [", "\n];\n")
    assert "primary" not in start, "the highlight is the first position's, not New note's"
    button = _block(DASH, "function quickLinkButton(", "\n}\n")
    assert "quick-link-primary" not in button and "link.primary" not in button
    assert 'setProperty("--quick-tint"' in button and "quick-link-tinted" in button
    assert "quickTintKey(" in _block(DASH, "function renderQuickLinks()", "\n}\n")


def test_the_highlight_is_chosen_with_the_swatch_picker_from_the_tile_menu():
    tile = _block(EDIT, "function quickAccessTile(", "\n}\n")
    assert "Highlight" in tile
    assert "swatchPicker(" in EDIT and "swatch-option" not in EDIT
    assert "dashboard_quick_tints" in DASH
    assert "No highlight" in EDIT
    assert "Start something" not in _block(DASH, "function renderQuickLinks()", "\n}\n")


def test_ticking_a_row_in_the_manager_does_not_scroll_the_list():
    # INBOX 904 B13: an unticked row moves to "More commands", far below, and
    # focusing it there scrolled the list 454px down; each further untick meant
    # scrolling back up. Measured with scratchpad/ui-sweeps/quickmanage904.js.
    manage = _block(EDIT, "function quickAccessManage(", "\n}\n")
    change = manage[manage.index('box.addEventListener("change"'):]
    change = change[: change.index("const lines =")]
    assert "preventScroll: true" in change
    assert "scroll.scrollTop = top" in change
