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
        block = PANEL[PANEL.index(f'id="{section}"') :]
        assert f'data-help-for="{help_id}"' in block[:3500], f"{section} has no '?' for {help_id}"
        body = _help_body(help_id)
        for name in names:
            assert name in body, f"{help_id} does not say what {name} does"


def test_the_sections_that_are_set_once_are_folds_and_the_help_rides_in_the_summary() -> None:
    for section in ("graph-physics", "graph-toggle-group", "graph-display", "graph-filter-section", "graph-temporal", "graph-groups-section", "graph-minimap-section"):
        tag = re.search(rf"<details[^>]*id=\"{section}\"", PANEL)
        assert tag, f"{section} is not a fold, so the closed panel is taller than its cap"
        summary = PANEL[PANEL.index(f'id="{section}"') :]
        summary = summary[summary.index("<summary>") : summary.index("</summary>")]
        assert "data-help-for" in summary, f"{section}: the '?' belongs in the fold's head, where it shows closed"


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
