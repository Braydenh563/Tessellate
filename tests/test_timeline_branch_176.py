"""Source text: the branch drawing is read from the script text, as the unit suite has no browser to drive.

L-world-class-176: the timeline draws a thread as a branching line.

A row that continues a loaded note is an off-shoot (`data-branch`), with an
elbow from the spine to its mark. The parent is found by row key
(`note:<id>`), since the map holds keys; by bare id the "Continues" link was
never drawn. Measured with scratchpad/sw/branch176.js at 1440: elbow left on
the spine centre (61.39px), right on the mark's edge (65.19px), row stepped
12.8px.
"""

import re

from pathlib import Path

from tests._app_js import frontend_text
from tessellate.ai.help_topics_core import HELP_TOPICS


def _row_element() -> str:
    js = frontend_text("timeline.js")
    start = js.index("function timelineRowElement(row, density)")
    return js[start : js.index("\nfunction ", start + 10)]


def test_parent_is_found_by_row_key():
    body = _row_element()
    assert "timelineById.get(`note:${row.parentId}`)" in body
    assert "timelineById.get(row.parentId)" not in body


def test_a_continuing_row_is_marked_as_a_branch():
    body = _row_element()
    assert 'if (parent) li.dataset.branch = "1";' in body
    # The Continues link hangs off the same lookup, so the two cannot disagree.
    assert 'if (density === "full" && parent) {' in body


def test_the_branch_draws_an_elbow_from_the_spine():
    css = (Path(__file__).parents[1] / "frontend/css/06-timeline-dialogs.css").read_text()
    rule = re.search(r'\.timeline-feed \.timeline-row\[data-branch="1"\]::before \{([^}]*)\}', css)
    assert rule, "the off-shoot elbow rule is missing"
    body = rule.group(1)
    assert "border-left: 1px solid var(--divider)" in body
    assert "border-bottom: 1px solid var(--divider)" in body
    # The elbow starts where the spine is: the same calc, less the step.
    assert "left: calc(var(--space-3) + 1px + (var(--timeline-mark) / 2) - 0.5px - var(--space-5))" in body
    assert re.search(r'\.timeline-feed \.timeline-row\[data-branch="1"\] \{\s*margin-left: var\(--space-5\);', css)


def test_help_says_a_continuing_note_branches():
    timeline = next(t for t in HELP_TOPICS if t["id"] == "timeline")
    assert "branches off the line" in timeline["body"]
