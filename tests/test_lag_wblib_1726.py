"""The board Library panel draws the groups that are open, and the rest when they are opened (INBOX 1726).

The owner's log: `frame 219ms on library: whiteboard-library.js Response.json.then 94ms`. The continuation
after the set files arrive drew every group's tiles, 220 of them with their thumbnails, 196 of those behind a
closed fold (`display: none`). Reproduced at 4x CPU, a fresh board with the Library side open: `wbRenderLibrary`
86.7ms (220 `wbLibTile` calls); a closed group now costs its header only.
"""

from __future__ import annotations

from pathlib import Path

LIB = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")


def _group() -> str:
    start = LIB.index("function wbLibGroup(")
    return LIB[start : LIB.index("\nfunction wbRenderLibrary()", start)]


def test_a_closed_group_builds_no_tiles_until_it_is_opened() -> None:
    body = _group()
    assert "const fill = () => {" in body
    assert "if (details.open) fill();" in body, "an open group is drawn at once, as it was"
    assert 'details.addEventListener("toggle", fill, { once: true })' in body, "a closed one, on its first opening"
    assert body.count("wbLibTile(entry)") == 1, "the loop lives in fill only"


def test_the_fold_is_remembered_before_the_tiles_are_drawn() -> None:
    body = _group()
    assert body.index('details.addEventListener("toggle", fill, { once: true })') < body.index('details.addEventListener("toggle", () => {')
