"""L228, INBOX 1843: Ask below the phone band (600px) and at half width.

Measured at 390 in the notes Ask tab (scratch sweep askhalf.js): the answer
head's icon group ended at 510px in a 390px window (card scroll width 497
against 358, nine elements past the viewport), the composer's second control
row sat at the left with Ask at x 88, and Matching records stood 569px tall.
After: scroll width 358 = client width, 0 elements past the viewport, Ask the
full 312px row, the records one 44px row. The pixel numbers are the sweep's;
here the rules that give them are pinned."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "js" / "ask-compose.js").read_text(encoding="utf-8")


LAZY = (ROOT / "frontend" / "css" / "ask-compose-lazy.css").read_text(encoding="utf-8")


def _phone_block() -> str:
    return CSS[CSS.index("/* Ask below 600px") :] + LAZY[LAZY.index("/* Ask below 600px") :]


def test_the_composer_stacks_with_a_full_width_ask():
    block = _phone_block()
    assert re.search(r"\.ask-composer \.ask-controls \{[^}]*flex: 1 1 100%", block)
    assert re.search(r"\.ask-composer \.ask-controls #ask-btn \{[^}]*flex: 1 1 100%", block)


def test_the_answer_head_wraps_and_the_badge_takes_its_own_line():
    block = _phone_block()
    assert re.search(r"\.chat-half h3\.answer-head \{[^}]*flex-wrap: wrap", block)
    assert re.search(r"\.answer-model \{[^}]*order: 3;[^}]*flex: 1 1 100%", block)


def test_matching_records_is_one_closed_row_on_a_phone():
    block = _phone_block()
    assert 'id="ask-records-fold"' in HTML and 'aria-expanded="false"' in HTML.split('id="ask-records-fold"', 1)[1][:200]
    assert re.search(r"#ask \.ask-records-fold \{\s*display: none", block)
    assert "[aria-expanded=\"false\"]) > #raw-results" in block
    assert "min-height: max(var(--control-h-lg), var(--target-min))" in block
    assert '$("ask-records-count").textContent = String(meta.raw_results.length)' in JS


def test_the_breakpoint_is_the_phone_band_not_a_new_width():
    assert "@media (max-width: 599.98px)" in _phone_block()
    assert "520" not in re.sub(r"/\*.*?\*/", "", _phone_block(), flags=re.S)
