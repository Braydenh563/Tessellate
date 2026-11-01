"""INBOX 1508: the app's Ctrl +/- zoom frame was 240 to 430 ms at 4x CPU, and
the Dashboard tab click 185 to 239 ms. Traced at 4x (UpdateLayoutTree and
Layout events), the zoom frame was two whole-document style passes: one for the
root font size, and a second for `--header-h`, which the top bar's
ResizeObserver rewrote in px on every step (a custom property changed on
<html> restyles every element). Written in rem, a step that leaves the bar the
same height writes nothing. The Dashboard's year heatmap (373 of the reveal's
796 elements) is below the fold on a first visit and is skipped until near."""

from __future__ import annotations

import re

from tests._app_js import app_js_text
from tests._css_paths import css_text


def _token_body() -> str:
    js = app_js_text()
    start = js.index("function initHeaderHeightToken(")
    return js[start : js.index("\n}\n", start)]


def test_the_header_token_is_written_in_rem_and_skipped_when_it_still_fits():
    body = _token_body()
    assert '`${Math.round(written * 1000) / 1000}rem`' in body
    assert "px`" not in body.split("setProperty(")[1].split(")")[0]
    assert "Math.abs(h - written * em) <= 1" in body


def test_the_heatmap_is_skipped_until_it_nears_the_window():
    rule = re.search(r"\n\.heatmap \{([^}]*)\}", css_text())
    assert rule, ".heatmap rule moved"
    assert "content-visibility: auto" in rule.group(1)
    assert "contain-intrinsic-size: auto" in rule.group(1)


def test_the_keyboard_scroll_reset_reads_layout_on_touch_only():
    js = app_js_text()
    start = js.index('document.addEventListener("focusout", (event) => {\n    if (!touchy.matches')
    assert "window.scrollY" in js[start : start + 600]
