"""Blind-test fixes on the finished builder (DOCUMENTS_PLAN 22.4 R11): picture click modifiers, the drag hint, help."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
MULTI = (JS / "diagram-multi.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_modified_click_on_the_picture_adds_to_the_pick():
    assert "S.pickAt = (key, shift)" in MULTI
    assert "S.pickAt(key, event.shiftKey" in BUILDER


def test_drag_hint_says_the_picture_lays_itself_out():
    assert "the picture lays itself out" in BUILDER


def test_chosen_row_does_not_spend_its_width_on_connect_words():
    assert '.dgm-block[aria-selected="true"] > .dgm-card .dgm-connect .ph-text' not in CSS


def test_document_help_names_the_diagram():
    start = INDEX.index('id="doc-dock-help"')
    body = INDEX[start : start + 6000]
    assert "A diagram (.mmd) opens the builder" in body and "exclamation mark" in body


def test_the_walkthrough_names_the_first_block_and_stays_with_ticks_until_the_first_arrow():
    """INBOX 1679: step 1 added a block called Step with nothing typing and hid the list at once. Now step 1 opens the name, the list
    stays (a tick on each step done) until an arrow exists, and step 3 arms the picked block's handle on the picture."""
    steps = (JS / "diagram-steps.js").read_text(encoding="utf-8")
    assert 'use.add(S, { shape: "rect", edit: true })' in steps
    assert "m.edges.length > 0" in steps and "dgm-done" in steps and "S.arm(" in steps
    assert "diagramModel.steps.sync(S, layout.length)" in BUILDER
    assert 'S.empty.classList.toggle("hidden", Boolean(layout.length))' not in BUILDER
    assert "S.arm = (from) => arm(from," in (JS / "diagram-edges.js").read_text(encoding="utf-8")
    assert ".dgm-empty.dgm-started .dgm-example" in CSS
    assert "Double-click a name, or press Enter, to rename it." in BUILDER
