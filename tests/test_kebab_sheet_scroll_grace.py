"""A phone's action sheet is not closed by a scroll that was already on its way.

`closeActionMenusOnScroll` ignores a scroll within 200ms of `window._menuOpenedAt`,
which only `openActionMenu` stamped. `openKebabSheet` (every kebab below 600px,
the App menu included) did not, so the scroll left over from the page settling
after a note opened closed the reopened sheet about 100ms in: deepflows' Find at
390 (traced: CLOSE from closeActionMenusOnScroll at 110ms after the open).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_kebab_sheet_stamps_menu_opened_at():
    text = (ROOT / "frontend" / "js" / "gesture-kit.js").read_text(encoding="utf-8")
    start = text.index("function openKebabSheet(")
    body = text[start : text.index("\n}\n", start)]
    assert "window._menuOpenedAt = performance.now();" in body
    # Before the sheet is built, so the grace covers the whole open.
    assert body.index("_menuOpenedAt") < body.index("openSheet({")
