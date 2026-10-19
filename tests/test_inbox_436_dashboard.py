"""The dashboard's first screen, made calm (INBOX 436).

User feedback, through the owner: "there is quite a lot going on visually on
the dashboard when the user opens the application ... I like the top hero
section though and I think the widgets section is fine". Measured before
(`scratchpad/ui-sweeps/dash436.js`, 1440x900, a 33-note notebook): 462px of
chrome between the hero and the first widget, 73 elements and 20 controls in
it, six bands and four kinds of chip; at 390x844 no widget on the first
screen at all. The hero, the Start something tiles (the owner: keep them) and
the grid stay; the search, Jump to, Run a skill, the stat strip and the
layout bar become one dock row: the search doorway and one grouped menu.
These pin what a static read can pin; the numbers are the sweep's.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.ai import help_chat

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
DASH = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
CSS = re.sub(
    r"/\*.*?\*/", "", "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css"))), flags=re.S
)


def _dashboard_markup() -> str:
    page = INDEX[INDEX.index('id="tab-dashboard"') :]
    page = page[: page.index("<!-- ======================= NOTES TAB")]
    return re.sub(r"<!--.*?-->", "", page, flags=re.S)


def _function(name: str) -> str:
    start = DASH.index(f"function {name}(")
    return DASH[start : DASH.index("\n}\n", start)]


def test_the_page_is_hero_dock_start_row_then_the_grid():
    page = _dashboard_markup()
    markers = ('id="dash-hero"', 'data-dock-name="dashboard"', 'id="dash-quicklinks"', 'id="dash-grid"')
    order = [page.index(marker) for marker in markers]
    assert order == sorted(order), "the dashboard reads hero, dock, Start something, widgets"
    for gone in ("dash-stats", "dash-toolbar", 'id="dash-density"'):
        assert gone not in page, f"{gone} is back on the first screen"


def test_the_dock_is_the_search_customise_and_one_menu():
    """INBOX 488: arranging the page is its own labelled menu (Customise)
    beside the ⋯, which keeps the things you do; the Quick access row has no
    ⋯ of its own any more, so no menu opens over another menu's button."""
    page = _dashboard_markup()
    dock = page[page.index('data-dock-name="dashboard"') : page.index('id="dash-quicklinks"')]
    assert 'id="dash-find"' in dock
    assert re.search(r'<span[^>]*id="dash-more"[^>]*class="[^"]*dock-more', dock)
    assert dock.index('id="dash-customise"') < dock.index('id="dash-more"')
    #: The one button besides the menus' own is the '?' (WORLD_CLASS row 14:
    #: every tab's dock ends with one).
    assert 'id="dash-help-toggle"' in dock
    assert len(re.findall(r"<button\b", dock)) == 2, "the dock is the search, two menus and the '?', nothing else"
    #: The owner (2026-10-10): a meatball on the heading's line, the same
    #: Customise rows; nothing of its own below the heading.
    quick = _function("renderQuickLinks")
    assert quick.count("kebabMenu(") == 1 and "head.append(heading, kebabMenu(dashCustomiseItems()" in quick


def test_the_start_row_is_kept_whole_with_one_primary():
    """The owner: keep Start something, five icon cards with a title and a
    one-line subtitle, five across."""
    start = DASH[DASH.index("const QUICK_START = [") :]
    start = start[: start.index("\n];\n")]
    labels = re.findall(r'label: "([^"]+)"', start)
    #: "New meeting", not the recorder (INBOX 644: a meeting note, recording inside it).
    assert labels == ["New note", "Ask your notes", "Sketch", "Remind me", "New meeting"]
    # One highlighted tile, the first by position (INBOX 589), not New note by name.
    assert len(re.findall(r'hint: "', start)) == 5 and "primary" not in start
    assert 'return index === 0 ? "accent" : "";' in _function("quickTintKey")
    assert "renderQuickLinks();" in _function("renderDashboard")
    assert "quick-link-hint" in _function("quickLinkButton")


def test_everything_else_that_left_the_first_screen_is_one_menu_away():
    """Every action the removed bands offered is a row of the dock's menu,
    and the figures the stat tiles showed are widgets in the picker."""
    items = _function("dashMoreItems")
    custom = _function("dashCustomiseItems")
    for row in ("Tools & features", "Commands", "All skills"):
        assert row in DASH, f"{row} is reachable from nowhere on the dashboard"
    assert "recentSkillLinks()" in items and "dashContinueNote(" in items and "QUICK_GO" in items
    assert "Widgets" in custom and "Edit layout" in custom and "applyDashDensity(" in custom
    assert "Edit quick access" in custom and "Reset quick access" in custom
    assert "Widgets" not in items and "applyDashDensity(" not in items, "the ⋯ mixes doing and arranging again"
    assert "QUICK_START" not in items, "the menu repeats the tiles under it"
    for widget in ("stats:", "streak:", "pace:"):
        assert re.search(rf"^\s+{widget} \{{ title:", DASH, re.M), f"the {widget} widget is gone"


def test_a_long_menu_is_grouped():
    items = _function("dashMoreItems")
    groups = set(re.findall(r'(?:group: |row\(link, )"([a-z]+)"', items))
    assert len(groups) >= 3, groups
    custom = set(re.findall(r'group: "([a-z]+)"', _function("dashCustomiseItems")))
    assert len(custom) >= 2, custom


def test_the_streak_still_reaches_atlas_and_the_companion():
    line = _function("renderDashSubmessage")
    assert "atlasStreak(streak)" in line and "nameMarkBuddyStreak(streak)" in line


def test_edit_mode_is_a_line_above_the_grid_with_its_way_out():
    page = _dashboard_markup()
    bar = page[page.index('id="dash-editbar"') : page.index('id="dash-grid"')]
    assert 'id="dash-hint"' in bar and 'id="dash-widgets-open"' in bar
    done = re.search(r'<button[^>]*id="dash-edit"[^>]*>([^<]*)</button>', bar)
    assert done and done.group(1).strip() == "Done"
    assert '$("dash-editbar").classList.toggle("hidden", !dashEditMode)' in DASH


def test_the_empty_notebook_card_draws_no_second_emblem():
    #: The card is the first steps now (first-run.js, WORLD_CLASS_PLAN 25c).
    steps = (ROOT / "frontend" / "js" / "first-run.js").read_text(encoding="utf-8")
    card = steps[steps.index("function firstStepsCard(") :].split("\n}\n")[0]
    assert "renderEmblem(" not in card and "emblem-centred" not in card


def test_the_removed_bands_left_no_styles_behind():
    for selector in (".stat-tile", ".stat-spark", ".quick-pill", ".launch-row-go", ".dash-toolbar", ".dash-density"):
        assert not re.search(rf"{re.escape(selector)}(?![\w-])", CSS), f"{selector} still has rules"


def test_the_guide_describes_the_dashboard_as_it_is():
    topic = next(t for t in help_chat.HELP_TOPICS if t["id"] == "dashboard-controls")
    body = topic["body"]
    assert "Quick access" in body and "Customise" in body and "... menu" in body
    for gone in ("quick start row", "Search notes"):
        assert gone not in body
