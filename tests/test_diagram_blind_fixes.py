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
