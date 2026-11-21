"""Source text: the behaviour is CSS and front-end script that only a browser renders, and pytest has none, so these pin the rules' text.

The Timeline calendar's head is one row at one control height.

The owner, 2026-11-12, from a screenshot: "these two elements arent aligned in
the timeline". Add sat 4px below the Month/Week/Day strip and 4.4px shorter
than it (1280 and 1024, dark): `.seg` carries a 0.5rem bottom margin and its
own padding, so in a centred flex row its centre rode up and its height grew.
The cure is the Library head's recipe (`.library-head`): every control in the
row is `--control-h` with no margin. `scratchpad/ui-sweeps/calheadalign.js`
measures the centres to within 1px at 1280, 1024 and 360 (`gate.sh --sweeps`).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "timeline-calendar-lazy.css").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    found = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert found, f"{selector} has no rule in timeline-calendar-lazy.css"
    return found.group(1)


def test_the_heads_controls_are_one_height_with_no_margin():
    body = _rule(".timeline-cal-head > :is(button, .seg)")
    assert "height: var(--control-h)" in body and "margin: 0" in body


def test_the_span_strip_fills_that_height_rather_than_padding_past_it():
    assert "padding-block: 0" in _rule(".timeline-cal-head > .seg")
    seg_buttons = _rule(".timeline-cal-head > .seg > button")
    assert "height: 100%" in seg_buttons and "padding-block: 0" in seg_buttons


def test_the_title_keeps_no_heading_margin_in_the_row():
    assert "margin: 0" in _rule(".timeline-cal-head > .timeline-cal-title")


def test_the_alignment_sweep_is_in_the_gate():
    assert (ROOT / "scratchpad" / "ui-sweeps" / "calheadalign.js").is_file()
    assert "calheadalign" in (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
