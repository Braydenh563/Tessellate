"""The 1103 unslop audit's twelve findings, held at source level.

Each test names the finding (docs/roadmap/agent-remaining/unslop-1103.md) and
the one fact in the stylesheet or markup that, if it drifts back, reproduces
it. The measured numbers live in the commit bodies.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    text = (CSS_DIR / name).read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(css: str):
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css):
        yield " ".join(match.group(1).split()), match.group(2)


def _body(css: str, selector: str) -> str:
    return "\n".join(b for s, b in _rules(css) if selector in [x.strip() for x in s.split(",")])


def test_1_reminder_time_is_its_own_phone_line():
    """Beside the words the time took 185px of 301 and left 48px for the text."""
    css = _css("08-consistency.css")
    grid = _body(css, "#reminder-groups .entry-list li > .entry-meta")
    assert '"tick text"' in grid and '"tick when"' in grid and '"acts acts"' in grid


def test_2_skills_dock_has_a_menu_to_fold_into():
    """Without a `.dock-more` the dock cannot fold: the title sat under the select."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    dock = html[html.index('data-dock-name="library-skills"') :]
    dock = dock[: dock.index("</section>")]
    assert 'class="doc-dock-menu dock-menu dock-more" id="skills-more-menu"' in dock
    assert '<div class="doc-dock-menu-list dock-menu-list"></div>' in dock
    assert ".dock-more:has(> .dock-menu-list:empty)" in _css("08-consistency.css")


def test_3_dashboard_spans_are_pixel_rows_with_the_card_gap_in_the_span():
    """An 8px unit and a 16px row gap rounded every card up in 24px steps."""
    grid = _body(_css("01-forms-settings.css"), "#dash-grid")
    assert "grid-auto-rows: 1px" in grid and "row-gap: 0" in grid
    js = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    start = js.index("function sizeDashWidgetSpan(")
    body = js[start : js.index("\n}\n", start)]
    assert "cardGap" in body and "rowGap" in body


def test_4_dashboard_find_label_drops_its_scope_on_a_phone():
    """93px of text room cut "Search your notes, ..." to "Search your..."."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<span class="dash-find-scope"> your notes, documents, files and the app</span>' in html
    assert "display: none" in _body(_css("10-responsive.css"), ".dash-find-scope")


def test_5_map_toolbar_selects_take_the_quiet_inset_not_radius_inner():
    """`--radius-inner` is 0 at the default corner: square, ink-edged selects."""
    body = _body(_css("07-whiteboard-misc.css"), ".wb-rail .select-shell > .select-opener")
    assert "radius-inner" not in body
    assert "border-radius: var(--radius-md)" in body and "var(--field-inset)" in body
    assert "border: 1px solid transparent" in body


def test_6_dock_search_is_the_docks_control_height():
    """The search was 32 (`--control-h-lg`) in a bar of 28s; DESIGN says 28."""
    body = _body(_css("08-consistency.css"), ".dock .dock-search")
    assert "height: max(var(--control-h), var(--target-min))" in body
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "(32px, 44 under touch; refresh" not in design


def test_7_chat_sidebar_search_is_the_quiet_inset():
    """It was the one search field drawn as a form field (ink edge, white fill)."""
    body = _body(_css("02-chat-graph.css"), ".search-field.chat-sidebar-search")
    assert "border-color: transparent" in body and "background: var(--field-inset)" in body
    inner = _body(_css("02-chat-graph.css"), ".search-field.chat-sidebar-search > .search-field-input")
    assert "font-size: var(--text-md)" in inner


def test_8_library_sections_grow_into_their_ring_room():
    """Padding with a negative margin nets zero only if the box widens."""
    css = _css("07-whiteboard-misc.css")
    body = _body(css, ".tab-page > .library-view-section")
    assert "width: calc(100% + 2 * var(--ring-room))" in body
    assert "max-width: calc(var(--content-max) + 2 * var(--ring-room))" in body


def test_9_settings_peek_is_beside_the_title_not_among_the_utilities():
    """Peek shown only on Appearance moved the utilities 91px between sections."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    head = html[html.index('<h2 class="dialog-head-title"><i class="ph ph-gear'):]
    head = head[: head.index('id="settings-close"')]
    assert head.index('id="settings-peek"') < head.index('id="settings-profile-btn"')
    assert "margin-inline-end: auto" in _body(_css("08-consistency.css"), ".dialog-head > #settings-peek")


def test_10_settings_rail_head_wraps_instead_of_clipping_its_toggle():
    css = _css("06-timeline-dialogs.css")
    assert "flex-wrap: wrap" in _body(css, ".settings-nav-groups-head")
    assert "white-space: nowrap" in _body(css, ".settings-nav-groups-head > *")
    link = _body(css, ".settings-nav-groups-head .linklike")
    assert "overflow: visible" in link and "text-overflow: clip" in link


def test_11_dashboard_has_one_filled_button_and_no_tinted_edge_at_rest():
    tinted = _body(_css("03-dashboard-widgets.css"), ".quick-link-tinted")
    assert "border-color" not in tinted
    js = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert js.count("Generate this week's digest") == 2
    assert 'smallButton("Generate this week\'s digest", "", runGeneration)' in js
    assert 'runGeneration, false' not in js


def test_12_reminder_when_row_takes_the_fields_height_and_corner():
    css = _css("08-consistency.css")
    assert "--button-min-h: var(--control-h-body)" in _body(css, "#reminder-due-row")
    for selector in ("#reminder-due-row > details > summary", "#reminder-due-row .stepper"):
        assert "border-radius: var(--radius-md)" in _body(css, selector)
        assert "radius-pill" not in _body(css, selector)
    assert "border-radius: var(--radius-in-md)" in _body(css, "#reminder-due-row .stepper-btn")
