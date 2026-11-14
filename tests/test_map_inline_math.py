"""Source text: the behaviour is front-end script that pytest cannot run without a browser, so these pin the code's text.

Equations and inline code in a map topic (L-mindmap-2). `$formula$` is cut
out of the topic's text before the bold, code and link grammar, by the notes'
own `INLINE_MATH_RE` and drawn by `mdInlineMathElement` (TeX to MathML, the
notes' renderer; no KaTeX is vendored). Inline code was already drawn by
`wbMapInlineText`. Driven in Chromium 2026-11-12: `Energy $E=mc^2$ and **b**
`code`` drew a `<math>` span, a `strong` and a `code`, and "Cost $5 and $10
both" stayed plain text."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")


def _fn() -> str:
    start = MAP_JS.index("function wbMapInlineText(el, raw) {")
    return MAP_JS[start : MAP_JS.index("\n}\n", start)]


def test_math_goes_through_the_notes_rule_and_renderer() -> None:
    body = _fn()
    assert "INLINE_MATH_RE.source" in body
    assert "mdInlineMathElement(hit[1].trim())" in body
    # The global may be absent in a slim bundle: the text then stays as typed.
    assert 'typeof INLINE_MATH_RE === "undefined"' in body


def test_the_gaps_between_formulas_still_get_bold_code_and_links() -> None:
    body = _fn()
    assert "run(text.slice(cursor, hit.index))" in body and "run(text.slice(cursor))" in body
    assert "innerHTML" not in body


def test_the_rule_is_the_one_that_keeps_money_plain() -> None:
    notes = (ROOT / "frontend" / "js" / "notes-list.js").read_text(encoding="utf-8")
    assert "(?<!\\$)\\$(?!\\$|\\s)" in notes and "(?!\\$|\\d)/g" in notes
