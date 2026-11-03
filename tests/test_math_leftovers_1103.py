"""The 1579 calculator agent's leftovers (a30z-1103): `\\boxed` and `\\cancel`
are drawn and offered, big operators stack their limits, and the palette's
search finds a structure by the TeX command it inserts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / "frontend" / "js" / "math-editor.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")


def test_the_palette_offers_a_box_and_a_strike():
    assert '["box", "\\\\boxed{#@}", "\\\\boxed{x}"]' in EDITOR
    assert '["cancel", "\\\\cancel{#@}", "\\\\cancel{x}"]' in EDITOR


def test_a_structure_is_found_by_its_commands_not_its_sample():
    body = EDITOR[EDITOR.index("function mathEditorPalette") :][:2000]
    assert "item.tex.match(/\\\\[A-Za-z]+/g)" in body
    assert '${group.structures ? "" : item.tex}' not in body


def test_the_frame_and_strike_are_drawn_by_classes_the_renderer_sets():
    for cls in ("math-boxed", "math-cancel", "math-bcancel", "math-xcancel"):
        assert re.search(rf"math \.{cls} \{{", CSS), cls
