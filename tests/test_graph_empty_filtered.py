"""A map whose notes are all filtered out says so, and offers them back.

The graph had one empty state, "Nothing to map yet: save a few notes and link
some together", and it drew it for two different facts: a notebook with no
notes, and a notebook whose every note is hidden by the map's own filters (the
legend's categories or rule keys, a group switched off, notes hidden from the
node menu, or "Hide unlinked" on a notebook with no links). The second is a
claim about the person's notes that is false, and its one button (Capture a
note) does nothing for them. Found 2026-09-26, measured in
`scratchpad/ui-sweeps/graphemptyfilter.js`.

The suite cannot open the map, so this holds the shape as text: the markup has
a second variant with its own action, the renderer chooses between them on
whether the data had notes, and the action clears every filter that can take
a note off the map.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parent.parent
HTML = index_html_text()


def test_the_empty_state_has_a_filtered_variant_with_its_own_action():
    block = HTML.split('id="graph-empty"')[1].split("</section>")[0]
    assert 'id="graph-empty-filtered"' in block
    assert 'id="graph-empty-show-all"' in block
    assert 'id="graph-empty-fresh"' in block


def test_the_renderer_tells_a_filtered_map_from_an_empty_notebook():
    js = frontend_text("graph-canvas.js")
    assert "gcShowEmpty(" in js
    body = js.split("function gcShowEmpty(")[1].split("\nfunction ")[0]
    assert "graph-empty-filtered" in body and "graph-empty-fresh" in body


def test_show_all_clears_every_filter_that_hides_a_note():
    js = frontend_text("graph-canvas.js")
    body = js.split("function gcShowEveryNote(")[1].split("\nfunction ")[0]
    for filt in ("graphHiddenCategories", "graphHiddenKeys", "hiddenIds", "hiddenOnMap", "graph-hide-orphans"):
        assert filt in body, f"Show every note leaves {filt} in force"


def test_an_empty_notebook_never_gets_the_filtered_variant():
    """INBOX 472, the first-run walk: a fresh notebook opened the map on
    "Every note is hidden. All 0 notes are filtered out by the map's
    settings." with a Show every note button that could show nothing. The
    renderer drew the fresh variant, carried on, found no visible nodes and
    took the filtered branch. The filtered call is only made for data that had
    notes in it."""
    js = frontend_text("graph-canvas.js")
    body = js.split("async function renderGraphCanvas(")[1].split("\nasync function ")[0]
    at = body.index("gcShowEmpty(true, ")
    call = body[at : body.index(";", at)]
    assert "data.nodes.length" in call, call
