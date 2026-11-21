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


def test_the_goal_and_findings_labels_give_way_before_the_type_picker():
    """L-general-43: with the mono font at 390 the strip's items needed 373px
    of 330 (goal 104, findings 133, type 90), and the type picker ended at 397
    of a 390 window, past the strip's clip. The two labels shrink with an
    ellipsis (their titles say the rest), so the picker keeps its place.
    A CSS rule, because the fit is measured by fontmatrix.js in a browser."""
    base = (CSS / "05-sidebars-themes.css").read_text(encoding="utf-8")
    buttons = _rule(base, "#doc-word-goal,\n#doc-prose")
    assert "flex: 0 1 auto" in buttons and "min-width: 0" in buttons
    labels = _rule(base, "#doc-goal-label,\n#doc-prose-count")
    for decl in ("min-width: 0", "overflow: hidden", "text-overflow: ellipsis", "white-space: nowrap"):
        assert decl in labels, decl
