"""L199 (Brief 86): the search suggestions take meaning.js's words for what was
typed (`meaningAlts`), never a copy, after everything that starts with the
words. Measured 2026-11-13 in the Notes box: "trash" suggested nothing, now
the note "Old drafts to bin"."""

from __future__ import annotations

from pathlib import Path

JS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "js"
SUGGEST = (JS_DIR / "search-suggest.js").read_text(encoding="utf-8")
APP = (JS_DIR / "app.js").read_text(encoding="utf-8")


def test_the_bundle_loads_meaning_first():
    assert 'searchSuggest: ["/js/meaning.js", "/js/search-suggest.js"]' in APP


def test_the_suggest_code_asks_meaning_alts_and_ranks_it_after_the_prefix_hits():
    assert "meaningAlts(query)" in SUGGEST
    assert "? 2 : -1" in SUGGEST
    for kind in ("tag", "name", "title"):
        assert f"searchSuggestRankMeant({kind}, " in SUGGEST, kind
