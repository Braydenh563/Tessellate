"""INBOX 1300 C44: a rendered section break in the documents live view clashed
with the line numbers. The rule was a 0.6em box, so the gutter gave its number
an 8.8px element and numbers 1 and 2 overlapped; the line is a full line now
(the `c44` Playwright sweep (kept out of the repo, which is at its scratchpad file cap) measures the gutter in the app)."""

from __future__ import annotations

import re

from tests._app_js import documents_text  # noqa: E402


def test_the_live_rule_keeps_a_full_line_height() -> None:
    js = documents_text()
    #: Ends at the rule's own closing brace (its own indent), not at the end of the whole block: the
    #: rules and comments after it (the gap note names `height`) are not this rule's body.
    rule = re.search(r'(?m)^( *)"\.cm-md-rule": \{(.*?)\n\1\},', js, re.S)
    assert rule, ".cm-md-rule moved"
    body = rule.group(2)
    assert "height" not in body and "margin" not in body, "a shorter box than the number puts line numbers on top of each other"
    assert "linear-gradient" in body, "the rule is drawn in the middle of its line"
