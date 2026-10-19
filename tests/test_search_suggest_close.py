"""The search suggestions close on scroll of what is behind them, not on their
own scroll or the browser's scroll-into-view after a keystroke (INBOX 1330)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "frontend" / "js" / "search-suggest.js").read_text(encoding="utf-8")


def test_scroll_closes_instead_of_repositioning():
    assert 'window.addEventListener("scroll", onScroll, true)' in JS
    assert 'window.removeEventListener("scroll", onScroll, true)' in JS
    assert 'addEventListener("scroll", onWindow' not in JS


def test_scroll_handler_spares_the_box_and_the_settling_window():
    body = JS.split("const onScroll = (event) => {", 1)[1].split("\n  };", 1)[0]
    assert "state.box.contains(event.target)" in body
    assert "performance.now() - state.touched < 400" in body
    assert "state.quiet = true" in body


def test_blur_and_escape_still_close():
    assert 'input.addEventListener("blur", onBlur)' in JS
    assert 'event.key !== "Escape"' in JS


def test_help_names_the_ways_to_close():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "close on Escape, on a click outside" in " ".join(html.split())
