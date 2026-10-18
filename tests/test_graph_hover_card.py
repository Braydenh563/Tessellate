"""INBOX 1300 C11: "I wanna be able to hover over and click graph nodes and see
their values and dates etc".

Before: a hovered note answered with the browser's own title tooltip (one line
of category, connections and uses, after a second's wait, never from the
keyboard), and the click popup's info line had the created date only. Now a
hover card stands beside the note (from the pointer or the arrow keys) with
its dates, links, views, length, properties and tags; a click still opens the
note's popup, whose info line carries the same dates.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
CANVAS = (JS / "graph-canvas.js").read_text(encoding="utf-8")
GRAPH = (JS / "graph.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    run = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


FACTS = (
    "const GC_ENTITY_HELP = 'An entity is a person';\n"
    + _function(CANVAS, "gcHoverCardFacts")
)


def test_a_notes_card_has_its_dates_links_views_length_values_and_tags() -> None:
    script = FACTS + """
const node = { id: 7, preview: "Gym Routine Overview", category: "Health", created_at: "2026-10-01T09:00:00+00:00",
  updated_at: "2026-10-18T09:00:00+00:00", edited_at: "2026-10-17T09:00:00+00:00", access_count: 3, words: 120, tags: ["gym", "plan"], _links: 4 };
const entry = { properties: { status: ["done"], due: ["2026-10-20"], who: ["[[Sam]]", "[[Alex]]"] } };
const day = (iso) => "D" + iso.slice(5, 10);
const ago = (iso) => "A" + iso.slice(5, 10);
console.log(JSON.stringify(gcHoverCardFacts(node, entry, day, ago)));
"""
    card = _run(script)
    facts = dict(card["facts"])
    assert card["title"] == "Gym Routine Overview" and card["sub"] == "Health"
    assert facts["Created"] == "D10-01" and facts["Edited"] == "A10-17"
    assert facts["Links"] == "4" and facts["Views"] == "3" and facts["Words"] == "120"
    props = dict(card["props"])
    assert props == {"status": "done", "due": "2026-10-20", "who": "Sam, Alex"}
    assert card["tags"] == "#gym #plan"


def test_a_card_says_never_edited_and_never_opened_plainly() -> None:
    script = FACTS + """
const node = { id: 1, preview: "Sleep log", category: "Health", created_at: "2026-10-01T09:00:00+00:00",
  updated_at: "2026-10-09T09:00:00+00:00", edited_at: null, access_count: 0, words: 0, tags: [], _links: 0 };
console.log(JSON.stringify(gcHoverCardFacts(node, null, (i) => "d", (i) => "a")));
"""
    facts = dict(_run(script)["facts"])
    assert "Edited" not in facts, "never edited by a person: the app's own writes are not an edit"
    assert facts["Views"] == "Not opened yet" and facts["Links"] == "None"


def test_a_node_that_is_not_a_note_says_what_it_is() -> None:
    script = FACTS + """
console.log(JSON.stringify(gcHoverCardFacts({ id: "e1", type: "entity", preview: "Kyoto", category: "Entity" }, null, (i) => "", (i) => "")));
"""
    card = _run(script)
    assert card["title"] == "Kyoto" and card["note"].startswith("An entity is")
    assert card["facts"] == []


def test_the_card_follows_the_pointer_and_the_keyboard_and_the_title_is_gone() -> None:
    frame = _function(CANVAS, "gcHoverCardFrame")
    assert "gcKeyboardId(s)" in frame and "s.hoveredId" in frame
    assert "gcHoverCardFrame(s)" in _function(CANVAS, "gcDraw")
    # The native tooltip no longer doubles the card for a note on the tab.
    assert "s.canvas.title = node ? gcTooltip(node, s)" not in CANVAS
    card = _function(CANVAS, "gcHoverCardEl")
    assert 'role", "tooltip"' in card or "role = \"tooltip\"" in card
    assert "aria-describedby" in frame


def test_the_popup_info_line_carries_the_edit_date() -> None:
    info = _function(GRAPH, "renderGraphPopupInfo")
    assert "edited_at" in info and "updated_at" not in info and "Edited" in info


def test_the_card_is_on_the_recipe_and_styled_with_tokens() -> None:
    rule = CSS[CSS.index(".graph-hovercard {") :][:900]
    assert "var(--modal-bg-opaque)" in rule and "backdrop-filter" not in rule
    assert "px" not in rule.split("}")[0].replace("1px solid", ""), "sizes and shadows from tokens; the hairline is the one px"
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "`gcHoverCardFacts`" in design


def test_the_help_says_hover_shows_the_card() -> None:
    help_panel = HTML[HTML.index('id="graph-help-panel"') :][:3400]
    assert "dates" in help_panel and "Hover a note" in help_panel
