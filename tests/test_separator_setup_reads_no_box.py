"""Source text: a forced layout is a browser cost with no runner here, so the setup is read as text for box reads.

L-documents-106: a resize grip's setup must not read a box (a forced layout of
the whole page at the Documents reveal, 110 ms); the observer reports it."""
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")


def _body() -> str:
    start = SRC.index("function trackSeparatorValue(")
    return SRC[start : SRC.index("function makeSidebarResizable(", start)]


def test_setup_reads_no_box_when_an_observer_exists() -> None:
    body = _body()
    setup = body[body.index("write(min);") - 80 : body.index("new ResizeObserver")]
    assert "write(min);" in setup
    assert "size()" not in setup.split("else {")[1]


def test_fallback_without_an_observer_still_reads_once() -> None:
    assert 'if (typeof ResizeObserver !== "function") write(size() || min);' in _body()
