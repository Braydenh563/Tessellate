"""INBOX 1400: the graph's Options panel says what its controls do, and fits.

The owner: the graph's tools and controls "aren't really easy to understand".
Every section of the panel has a '?' (`data-help-for`) whose body names each of
its controls, and the sections that are set once and left are folds, so the
panel with every fold closed fits its cap. The fit itself is measured in a
browser (`scratchpad` sweep, 520px of list in a 520px box at 1440x900); here
the structure that makes it possible is held.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
PANEL = HTML[HTML.index('id="graph-options"') : HTML.index("<!-- Trace: the one question")]

#: section id -> (its '?' panel, the control names the panel must say)
SECTIONS = {
    "graph-physics": ("graph-physics-help", ("Gravity", "Spread", "Link force", "Length by similarity", "Group by category", "Unpin all", "Reshuffle layout")),
    "graph-toggle-group": ("graph-show-help", ("Similarity", "Documents", "Boards", "Tags", "Attachments", "Unwritten links")),
    "graph-display": ("graph-display-help", ("Labels", "Curved links", "Cluster glow", "Label backgrounds", "Arrows", "Fit on view change", "Text fade", "Link thickness")),
    "graph-filter-section": ("graph-filter-help", ("Kinds of link", "Properties")),
    "graph-temporal": ("graph-time-help", ("slider", "Play")),
    "graph-groups-section": ("graph-groups-help", ("Add", "legend")),
    "graph-minimap-section": ("graph-minimap-help", ("Position", "Size", "Off")),
}


def _help_body(help_id: str) -> str:
    start = PANEL.index(f'id="{help_id}"')
    return PANEL[start : PANEL.index("</div>", start)]


def test_every_options_section_has_a_question_mark_that_names_its_controls() -> None:
    for section, (help_id, names) in SECTIONS.items():
        at = PANEL.index(f'id="{section}"')
        # A fold's '?' is the first child of its wrapper, just before the `<details>`.
        wrap = PANEL.rfind('<div class="graph-fold-wrap">', 0, at)
        block = PANEL[wrap if 0 <= wrap and "<details" not in PANEL[wrap:at].replace("<details", "", 1) else at :]
        assert f'data-help-for="{help_id}"' in block[:3500], f"{section} has no '?' for {help_id}"
        body = _help_body(help_id)
        for name in names:
            assert name in body, f"{help_id} does not say what {name} does"


def test_the_sections_that_are_set_once_are_folds_and_the_help_rides_in_the_head_row() -> None:
    """The '?' is the wrapper's first child, beside the fold's `<summary>` and not in it (a button
    inside a summary is a control inside a control), and it is still drawn in the head, closed."""
    for section in ("graph-physics", "graph-toggle-group", "graph-display", "graph-filter-section", "graph-temporal", "graph-groups-section", "graph-minimap-section"):
        tag = re.search(rf"<details[^>]*id=\"{section}\"", PANEL)
        assert tag, f"{section} is not a fold, so the closed panel is taller than its cap"
        head = PANEL[: tag.start()]
        head = head[head.rindex('<div class="graph-fold-wrap">') :]
        assert "data-help-for" in head and "<details" not in head, f"{section}: the '?' belongs in the fold's head row, beside its summary"
        summary = PANEL[tag.start() :]
        summary = summary[summary.index("<summary>") : summary.index("</summary>")]
        assert "data-help-for" not in summary, f"{section}: a '?' inside the summary is a control inside a control"


def test_the_help_copy_follows_the_house_style() -> None:
    for section, (help_id, _names) in SECTIONS.items():
        body = _help_body(help_id)
        assert chr(0x2014) not in body and "!" not in re.sub(r"<[^>]*>", "", body), f"{help_id}: no em-dashes or exclamation marks"


def test_folds_are_remembered_and_mirrored() -> None:
    mirrored = (ROOT / "frontend" / "js" / "ai-tools.js").read_text(encoding="utf-8")
    for section in SECTIONS:
        if section == "graph-toggle-group" or section.startswith("graph-") and section != "graph-view-section":
            assert f'"graph-fold-{section}"' in mirrored, f"the {section} fold's open state is not mirrored"


def test_trace_and_legend_and_the_foot_actions_share_a_row() -> None:
    css = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    assert ".graph-options .graph-view-tools,\n.graph-options .graph-options-foot {\n  display: flex;\n  flex-direction: row;" in css


def test_the_guide_says_every_section_has_a_question_mark() -> None:
    from tessellate.ai import help_chat

    topics = {t["id"]: t for t in help_chat.HELP_TOPICS} if hasattr(help_chat, "HELP_TOPICS") else {}
    body = topics.get("graph-options-help", {}).get("body", "") if topics else (ROOT / "src/tessellate/ai/help_chat.py").read_text(encoding="utf-8")
    assert "beside its name" in str(body)


def test_a_toast_over_the_map_stands_above_the_legend_and_left_of_the_zoom() -> None:
    """INBOX 1400: the toast met the legend row's box at 1440 and the zoom strip
    at 390 (measured, `scratchpad` toast sweep: 0 intersections after, at 1440,
    1024, 820 and 390). The graph lifts the toast box by the legend's distance from the
    window's bottom (on the box, not a page property); the stylesheet steps it left."""
    css = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    assert "right: calc(var(--space-4) + 4.5rem);" in css
    js = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
    body = js[js.index("function initGraphToastClearance()") :]
    body = body[: body.index("\n}\n")]
    # The legend row rides the popups' observer (`watchGraphPopupSize`): a second ResizeObserver
    # in graph.js fails the wake-source ratchet (tests/test_frontend_wake_sources.py).
    assert "box.style.bottom" in body and "watchGraphPopupSize(row, write)" in body and '"resize"' in body
    assert js.count("initGraphToastClearance();") == 1, "the clearance is wired once, at load"
