"""INBOX 1679 review findings: picked block beats hover, handles say their side, blank names restore, names are capped."""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
EDGES = (JS / "diagram-edges.js").read_text(encoding="utf-8")
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
OPS = (JS / "diagram-ops.js").read_text(encoding="utf-8")


def test_picked_block_wins_over_hover():
    assert "conn?.from || armed || sole() || hover" in EDGES


def test_each_handle_names_its_edge():
    assert "Connect from the ${side} edge to another block" in EDGES


def test_empty_name_draws_the_old_one_back():
    # The refusal still draws the old name back; slice 15 also sets the label's own text first, because `render` can keep the
    # same element when nothing changed and the emptied label stayed blank (blind pass). Same intent, one more statement.
    assert "if (!diagramOps.relabel(S.m, key, text)) return (label.textContent = nameOf(S, key)), render(S);" in BUILDER


def test_names_are_capped():
    assert ".trim().slice(0, 120)" in OPS and "input.maxLength = 120" in EDGES
