"""The map's View menu keeps under its 450px ceiling (L-general-57)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/index.html").read_text(encoding="utf-8")


def test_the_branch_rows_sit_behind_one_submenu_row():
    """Source text: L-general-57, mapviewmenu.js: the map's View menu was 587px
    and 25 rows against a 450px ceiling. The seven branch and report rows fold
    into one `data-wb-submenu` row (the markup-menu fold recipe), 427px measured."""
    start = HTML.index('data-wb-submenu="ph:git-branch Branches and reports"')
    block = HTML[start:].split("</div>", 1)[0]
    for row in ("wb-map-numbered", "wb-map-dim", "wb-map-expand-all", "wb-map-fold-all",
                "wb-map-filter-item", "wb-map-gantt-item", "wb-map-stats-item"):
        assert f'id="{row}"' in block, row
    section = HTML[HTML.index('id="wb-view-map-section"'):start]
    assert 'id="wb-map-theme-item"' in section
    assert 'data-wb-fn="present" data-wb-surface="map"' in section
