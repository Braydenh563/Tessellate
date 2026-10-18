"""INBOX 1300 C44: a rendered section break in the documents live view clashed
with the line numbers. The rule was a 0.6em box, so the gutter gave its number
an 8.8px element and numbers 1 and 2 overlapped; the line is a full line now
(the `c44` Playwright sweep (kept out of the repo, which is at its scratchpad file cap) measures the gutter in the app)."""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents.js"


def test_the_live_rule_keeps_a_full_line_height() -> None:
    js = DOCS.read_text(encoding="utf-8")
    rule = re.search(r'"\.cm-md-rule": \{(.*?)\n      \},', js, re.S)
    assert rule, ".cm-md-rule moved"
    body = rule.group(1)
    assert "height" not in body and "margin" not in body, "a shorter box than the number puts line numbers on top of each other"
    assert "linear-gradient" in body, "the rule is drawn in the middle of its line"
