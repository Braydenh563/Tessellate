"""Audit 1028 S87: a count on the dashboard opens the notes it counts.

The Stats widget drew its top categories as plain chips ("Work · 12"), so
the number could be read but not followed, while the Categories widget's rows
already opened the category. Both now go through `showCategoryNotes`, the one
door the chip menu and the day summary use; the Categories row no longer
keeps its own copy of the filter steps.
"""

from __future__ import annotations

from pathlib import Path

DASH = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_the_stats_widget_category_counts_open_their_notes():
    stats = _body(DASH, "async function renderStatsWidget(body) {")
    assert "chip(`${category.name} · ${category.count}`, \"\", () => showCategoryNotes(category.name))" in stats


def test_the_categories_widget_uses_the_same_door():
    js = DASH
    start = js.index('row.className = "cat-row";')
    rows = js[start : js.index("list.appendChild(row);", start)]
    assert 'row.addEventListener("click", () => showCategoryNotes(name));' in rows
    assert "activeCategory = name" not in rows
