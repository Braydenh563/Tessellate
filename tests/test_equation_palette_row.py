"""Ctrl+K has an "Insert equation" row (DOCUMENTS_PLAN 16, the last open item).

Over a note, Chat or a board's text it opens the equation editor over the box the palette was opened over; an
open document already has its own "Insert an equation" row, so this one steps aside there rather than listing twice.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import help_chat

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_palette_row_opens_the_editor_over_the_palette_box_and_yields_to_a_documents_own() -> None:
    src = (JS / "app-features.js").read_text(encoding="utf-8")
    row = src[src.index("ph:function Insert equation") : src.index("ph:closed-captioning Live captions")]
    assert "openMathEditor({ target: popupToolMaths.box(paletteCaughtNow().target) })" in row
    assert 'keys: "Alt+="' in row
    lead = src[src.rindex("\n", 0, src.index("ph:function Insert equation")) :]
    assert "editor.some((c) => /equation/i.test(c.label)) ? []" in lead.split("Insert equation")[0]


def test_the_guide_names_the_row() -> None:
    topics = {t["id"]: t for t in help_chat.HELP_TOPICS}
    body = topics["equation-editor"]["body"]
    assert "Ctrl+K, Insert equation" in body and len(body) < 1900
