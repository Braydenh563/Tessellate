"""Documents audit 1102 DX20: the sidebar's "Recent" heading was cut to "Rec...".

Measured at 1440 and 1920: the text is 53.44px and the box it was shrunk to was
53px, because the heading is the shrinkable part of a row whose actions are not.
"""

from __future__ import annotations

from pathlib import Path

CSS = Path("frontend/css/07-whiteboard-misc.css").read_text(encoding="utf-8")


def test_the_recent_heading_keeps_its_own_width():
    rule = CSS.split("#doc-sidebar-list .sidebar-head h2 {")[1].split("}")[0]
    assert "flex: none" in rule
