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
