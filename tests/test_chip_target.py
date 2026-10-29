"""An interactive chip's target is `--target-min` whatever it paints (audit FE-14).

The category and "Add tags" chips on a note card were 24px targets under
DESIGN.md's 28px floor. They keep their 24px paint and take the floor through
a transparent overhang, the switches' pattern; a chip clipped to shrink with
its row is clipped across only, or the overhang goes with it.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def test_an_interactive_chip_overhangs_to_the_floor():
    text = (CSS / "01-forms-settings.css").read_text(encoding="utf-8")
    rule = re.search(r"\.chip-interactive::after[^{]*\{([^}]*)\}", text)
    assert rule, "the overhang is gone"
    body = rule.group(1)
    assert "position: absolute" in body
    assert "var(--target-min)" in body and "inset-block" in body


def test_a_shrinking_chip_is_not_clipped_above_and_below():
    text = (CSS / "08-consistency.css").read_text(encoding="utf-8")
    at = text.index(".entry-meta.note-meta:not(.is-measuring) > :is(.when, .refs")
    rule = text[at : text.index("}", at)]
    assert "overflow: clip visible" in rule
    assert "overflow: hidden" not in rule
