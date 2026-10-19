"""INBOX 1319: the Statistics page is wider and taller, and its body is the
scroll pane, so the title and its close stay put (measured: card 826 of 826,
body 1153 over 730 at 1440x900, stats1319.js)."""

from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "frontend" / "css" / "utilities-lazy.css"


def _rule(text: str, selector: str) -> str:
    start = text.index(f"\n{selector} {{")
    return text[start:text.index("}", start)]


def test_the_body_scrolls_and_the_card_does_not():
    text = CSS.read_text(encoding="utf-8")
    card = _rule(text, ".stats-card")
    assert "min(72rem, 96vw)" in card and "overflow: hidden" in card and "92dvh" in card
    body = _rule(text, ".stats-body")
    assert "overflow-y: auto" in body and "min-height: 0" in body
