"""Source text: layout and placement are measured in a browser the suite does not run (probe numbers below); the rule is held as its CSS or JS text. L384: on a phone Ask's header buttons share the title's line; only the
model picker takes a line of its own (measured at 390: three lines before,
two after; probe ask390.js)."""

from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css" / "10-responsive.css"


def test_ask_actions_join_the_title_line_on_a_phone():
    """Source text: under 600 the actions group is display: contents and the title grows."""
    text = CSS.read_text(encoding="utf-8")
    block = text.split("#ask .ask-header-actions {", 1)[1].split("}", 1)[0]
    assert "display: contents;" in block
    h2 = text.split("#ask h2 {", 1)[1].split("}", 1)[0]
    assert "flex: 1;" in h2
