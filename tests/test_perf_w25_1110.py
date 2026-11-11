"""W25 (OPEN.md, 2026-11-09 work order): palette ranking kept per word, no layout read on a hidden dashboard."""

from tests._app_js import frontend_text
from tests import _js_scope


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_the_palette_keeps_its_ranking_for_the_same_words():
    # The notes arriving 150 ms after a key redrew the palette and ranked ~700 rows again.
    js = _js_scope.unwrapped(frontend_text("app-palette.js"))
    body = _between(js, "function paletteMatches(query) {", "//: \"timer 10 minutes\"")
    assert "paletteGen.memo.q === lowered" in body
    assert "memo ? [...memo.commands]" in body
    # Anything that can change the order drops the memo.
    open_body = _between(js, "async function openPalette() {", "function closePalette()")
    assert 'paletteGen.memo.q = ""' in open_body
    assert 'document.addEventListener("meaning-ready", () => {\n  paletteGen.memo.q = "";' in js
    assert 'paletteUsage.clear();\n      paletteGen.memo.q = "";' in js


def test_the_nearest_word_scan_splits_each_row_once():
    js = _js_scope.unwrapped(frontend_text("app-palette.js"))
    scan = _between(js, "function paletteNearest(rows, typed) {", "//: Edits between two words")
    assert "paletteGen.words.get(text)" in scan and "paletteGen.words.set(text, words)" in scan


def test_the_dashboard_sizer_reads_the_class_before_the_layout():
    # `checkVisibility` needs a clean style tree: asked as the tab went hidden it cost 129 ms at 4x.
    js = frontend_text("dashboard.js")
    sizer = _between(js, "function sizeDashWidgets() {", "const styles = getComputedStyle(grid);")
    assert sizer.index('grid.closest(".hidden")') < sizer.index("checkVisibility()")
