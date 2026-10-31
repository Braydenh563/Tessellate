"""The document status strip is one row at every width (E2E editor-keys,
"at 700px wide the formatting toolbar is one row"): the file type picker
(INBOX 1482) wrapped it to a second 44px row at 700px and the editor fell
under its 260px floor. The counts give way with an ellipsis instead."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "frontend" / "css"


def _rule(css: str, selector: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    match = re.search(rf"(?m)^{re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match, selector
    return match.group(1)


def test_the_strip_never_wraps_at_any_width():
    base = (CSS / "05-sidebars-themes.css").read_text(encoding="utf-8")
    assert "flex-wrap: nowrap" in _rule(base, ".doc-statusbar")
    counts = _rule(base, "#doc-counts")
    assert "min-width: 0" in counts and "text-overflow: ellipsis" in counts


def test_no_stylesheet_lets_the_strip_wrap_again():
    for path in CSS.glob("*.css"):
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for body in re.findall(r"\.doc-statusbar\s*\{([^}]*)\}", css):
            assert "flex-wrap: wrap" not in body, path.name
