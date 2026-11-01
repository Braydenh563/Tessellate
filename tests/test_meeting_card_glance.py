"""A meeting card shows a glance, not its raw `## Agenda` text (ledger
libr-1011 row 1238). `meetingGlance` is run in node on the writer's own shape
(`entry/meetings.py`); the card wiring and CSS are read as source."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CARDS = ((ROOT / "frontend/js/note-cards.js").read_text(encoding="utf-8") + (ROOT / "frontend/js/entry-card.js").read_text(encoding="utf-8"))
REMINDERS = (ROOT / "frontend/js/shell-reminders.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/css/03-dashboard-widgets.css").read_text(encoding="utf-8")

MEETING = """---
type: Meeting
date: 2026-10-11 14:00
---
# Weekly sync

## Agenda
- budget review
- hiring

## Notes
we talked

## Decisions
- ship on friday
- drop the beta

## Action items
- [ ] Send the deck @Sam by Friday
- [x] Book the room
- [ ] Call Priya
"""


def _block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    return source[begin : source.index(end, begin) + len(end)]


def _glance(content: str, types=("Meeting",)):
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = (
        _block(REMINDERS, "function stripFrontmatter(text) {", "\n}\n")
        + _block(CARDS, "const MEETING_GLANCE_SECTIONS = {", "};\n")
        + _block(CARDS, "function meetingGlance(entry) {", "\n}\n")
        + "\nconst [content, types] = JSON.parse(process.argv[1]);\n"
        "process.stdout.write(JSON.stringify(meetingGlance({ content, properties: { type: types } })));\n"
    )
    out = subprocess.run([node, "-e", script, json.dumps([content, list(types)])], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_four_sections_read_for_one_line_each():
    rows = _glance(MEETING)
    assert rows == [
        {"label": "Agenda", "text": "budget review (+1)"},
        {"label": "Decisions", "text": "2: ship on friday"},
        {"label": "Open actions", "text": "2: Send the deck @Sam by Friday"},
    ]


def test_a_finished_list_says_so_and_an_empty_meeting_says_nothing_yet():
    done = "## Action items\n- [x] one\n- [x] two\n"
    assert _glance(done) == [{"label": "Actions", "text": "all 2 done"}]
    assert _glance("# Standup\n\n## Agenda\n\n## Notes\n\n## Decisions\n\n## Action items\n") == [{"label": "", "text": "Nothing written yet."}]


def test_only_a_meeting_gets_one():
    assert _glance("## Agenda\n- x", types=("Recipe",)) is None
    assert _glance("## Agenda\n- x", types=()) is None


def test_the_card_holds_glance_and_body_and_a_class_says_which_shows():
    assert "const glance = meetingGlance(entry);" in CARDS
    assert "const isLong = !glance && (" in CARDS
    assert 'li.classList.toggle("meeting-open", expandedNotes.has(entry.id) || searchHighlightTerms().length > 0);' in CARDS
    assert ".meeting-card:not(.meeting-open):not(.row-expanded) > .entry-content" in CSS
    assert ".meeting-card.row-expanded > .meeting-glance" in CSS
    glance_code = _block(CARDS, "if (glance) {", "li.appendChild(content);\n  }")
    assert "innerHTML" not in glance_code
