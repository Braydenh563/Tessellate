"""L180's last part: the enlarged view mirrors the corner, and a framed Atlas
is clipped to its round frame (HISTORY, Brief 34 second part: "the enlarged
view mirroring the corner, the framed Atlas clipped to its oval"; measured
built in uxfix5-1018 and ai1518-1101; INBOX 1840)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
MENU = (ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", CSS)
    assert m, selector
    return m.group(1)


def test_a_framed_atlas_is_clipped_to_its_round_mark():
    assert "border-radius: 50%" in _rule("\n.atlas-mark ")
    assert "overflow: hidden" in _rule(".atlas-mark:has(> .nm-atlas)")
    assert "overflow: hidden" in _rule(".rich-picker-tile-face > .nm-atlas")


def test_the_enlarged_view_shows_the_corner_companion_itself_not_a_redraw():
    # The companion's own element moves into the card, so its act, face and
    # pose are the corner's; closing sends it back to the perch it left.
    assert "host.appendChild(buddy)" in MENU
    assert "nmb.visit = { home: buddy.parentNode, next: buddy.nextSibling" in MENU
