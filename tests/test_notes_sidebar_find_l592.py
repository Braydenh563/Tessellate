"""L592: a search field in the Notes sidebar that hands its words to Find anything."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_the_sidebar_holds_the_search_field_recipe_above_the_categories():
    index = _read("frontend/index.html")
    sidebar = index[index.index('<aside class="card sidebar-panel" id="sidebar">') :]
    sidebar = sidebar[: sidebar.index("</aside>")]
    assert 'id="sidebar-find"' in sidebar
    field = sidebar[sidebar.rindex("<div", 0, sidebar.index('id="sidebar-find"')) :]
    assert field.startswith('<div class="search-field sidebar-search"')
    assert "search-field-icon" in field and "search-field-input" in field
    assert sidebar.index('id="sidebar-find"') < sidebar.index('id="category-list"')


def test_the_field_is_wired_in_the_lazy_search_file_not_the_boot_scripts():
    search = _read("frontend/js/search.js")
    assert "sidebar-find" in search and "openFinder(" in search
    wire = search[search.index("box.dataset.wired") :]
    assert '"Enter"' in wire and '"Escape"' in wire
    assert "sidebar-find" not in _read("frontend/js/wiring.js")
