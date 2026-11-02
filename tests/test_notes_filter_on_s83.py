"""Audit 1028 S83: the Notes Filter button says when a filter is on.

The Library's Filter button already turned accent (`is-on`, aria-pressed)
when meaning search or the bin was on; the Notes one, whose only filter is
meaning search, looked the same on and off once its menu closed. Both now
mark their summary from their checkbox, the one style `.dock-menu > summary.is-on`.
"""

from __future__ import annotations

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_notes_filter_summary_follows_meaning_search():
    src = (JS / "phone-shell.js").read_text(encoding="utf-8")
    handler = src[src.index('$("semantic-search-toggle")?.addEventListener("change", () => {') :]
    handler = handler[: handler.index("\n});\n")]
    assert 'const summary = $("notes-filter-menu")?.firstElementChild;' in handler
    assert 'summary?.classList.toggle("is-on", on);' in handler
    assert 'summary?.setAttribute("aria-pressed", String(on));' in handler
