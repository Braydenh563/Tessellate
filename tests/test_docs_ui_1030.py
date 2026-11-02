"""Small Documents UI rows of audit 1028, read from the code they changed."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend"


def _rule(css: str, selector: str) -> str:
    start = css.index("\n" + selector + " {")
    return css[start : css.index("\n}", start)]


def test_download_is_the_first_row_of_the_more_menu_u32():
    js = (ROOT / "js" / "documents.js").read_text(encoding="utf-8")
    assert "const docDownloadGroup = foldDocMenuGroup(" in js
    assert "docDownloadGroup?.parentElement?.prepend(docDownloadGroup);" in js
    # moved after the three folds' sources are known, and before any other group is inserted
    assert js.index("docDownloadGroup?.parentElement?.prepend") < js.index('foldDocMenuGroup("ph:layout')


def test_crumbs_and_counts_are_at_least_the_target_floor_u35():
    """WCAG 2.5.8: 22.8px crumbs and a 16.8px counts button measured before."""
    crumb = _rule((ROOT / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8"), ".doc-crumb")
    link = _rule((ROOT / "css" / "library-lazy.css").read_text(encoding="utf-8"), ".doc-statusbar-link")
    for rule in (crumb, link):
        assert re.search(r"min-height:\s*var\(--target-min\)", rule)
