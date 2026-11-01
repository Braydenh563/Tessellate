"""Audit 1031 class 49 (UX5, UX6): the control scale and the strips that scroll.

UX5: a control is one of four heights (28, 32, 36 and 40 px as tokens); a fifth
token is a new height, so the set is pinned. Measured at 1440 on Notes,
Library, Timeline, Reminders and the Dashboard: 24 (a segment inside its
well), 28, 32 and 36 px, the 14, 21 and 26 of the audit are gone.
UX6: a strip that scrolls fades at the edge it scrolls toward and brings the
tab you choose into view, one recipe (`edgeFadeWire`)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = sorted((ROOT / "frontend" / "css").glob("*.css"))


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_a_control_has_one_of_four_heights():
    declared: dict[str, list[str]] = {}
    for path in CSS:
        for name, value in re.findall(r"(--control-h-[a-z]+):\s*([^;]+);", path.read_text(encoding="utf-8")):
            declared.setdefault(name, []).append(value.strip())
    # Dense is the touch height on a coarse pointer (its second declaration).
    assert declared == {
        "--control-h-lg": ["2rem"],
        "--control-h-dense": ["1.75rem", "var(--control-h-touch)"],
        "--control-h-touch": ["2.5rem"],
        "--control-h-body": ["2.25rem"],
    }, f"a control height was added or moved: {declared}"


def test_every_strip_that_scrolls_has_the_one_recipe():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for strip in ('id="library-filters"', 'id="library-subtabs"', 'id="notes-subtabs"'):
        tag = html.split(strip, 1)[1].split(">", 1)[0]
        head = html.split(strip, 1)[0].rsplit("<", 1)[1]
        assert "edge-fade" in head + tag, strip
    # The rows a script builds say it and wire themselves.
    for name in ("app-features.js", "quick-access.js"):
        text = _js(name)
        assert 'launch-row launch-row-start' in text and "edge-fade" in text
        assert "window.edgeFadeWire?.(row);" in text


def test_the_recipe_fades_with_the_scroll_and_shows_the_chosen_tab():
    wire = _js("shell-reminders.js").split("function edgeFadeWire(bar)", 1)[1].split("\n}\n", 1)[0]
    assert 'addEventListener("scroll", () => syncEdgeFade(bar)' in wire
    assert 'scrollIntoView({ block: "nearest", inline: "nearest" })' in wire
    # Read from the classes the last sync left: a strip that fits costs no layout.
    assert "fade-(start|end)" in wire
    css = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")
    assert ".edge-fade.fade-end {" in css and "mask-image: linear-gradient(to right, #000 calc(100% - var(--tab-fade))" in css
