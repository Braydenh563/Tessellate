"""Inline `[text](url)` links in a map topic's text (L375): drawn by
`wbMapInlineText` as real anchors for http, https and mailto addresses only,
so a `javascript:` or `data:` address stays the words typed. A plain click
selects the topic as on any other; Ctrl/Cmd or a topic already selected opens
it through `window.open` with `noopener`. Driven in Chromium 2026-11-12: the
link drew, the first click did not open, the second did, the `javascript:`
text stayed plain."""

from __future__ import annotations

from tests._app_js import frontend_text
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_JS = frontend_text("whiteboard-map.js")


def _fn() -> str:
    start = MAP_JS.index("function wbMapInlineText(el, raw) {")
    return MAP_JS[start : MAP_JS.index("\n}\n", start)]


def test_the_split_takes_a_link_as_its_own_piece() -> None:
    line = next(row for row in MAP_JS.splitlines() if row.startswith("const WB_MAP_INLINE"))
    script = line + """
const parts = "see [the docs](https://a.b/c) and `x` ok".split(WB_MAP_INLINE).filter(Boolean);
console.log(JSON.stringify(parts));"""
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert out.strip() == '["see ","[the docs](https://a.b/c)"," and ","`x`"," ok"]'


def test_only_the_three_schemes_become_anchors_and_it_opens_safely() -> None:
    body = _fn()
    assert "WB_MAP_LINK_SCHEMES.test(linked[2])" in body
    assert 'anchor.rel = "noopener noreferrer"' in body
    assert 'window.open(linked[2], "_blank", "noopener,noreferrer")' in body
    assert "ev.preventDefault()" in body and "wasSelected" in body
    assert "innerHTML" not in body
