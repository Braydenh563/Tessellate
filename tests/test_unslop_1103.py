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
