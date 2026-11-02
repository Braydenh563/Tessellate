"""Frames are the pages, and a locked item answers the pointer (Phase C).

WHITEBOARD_PLAN decision 22: the sidebar lists the board's frames as its pages
and their order is the presentation's. Decision 28 (INBOX 557a): a locked item
lets the pointer through, so a board-level hit test shows a lock on hover and
the first press says how to unlock it; right-click on it unlocks that one.
The browser half is `scratchpad/ui-sweeps/wb1005-pages.js`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
LIBRARY = (ROOT / "frontend" / "js" / "whiteboard-library.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _order(frames):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        f"let wbState = {{ objects: {json.dumps(frames)} }};\n"
        + _function(BOARD, "wbFramesInOrder")
        + "console.log(JSON.stringify(wbFramesInOrder().map((f) => f.id)));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


def _frame(fid, x, y, page=None):
    data = {"content": f"F{fid}"}
    if page is not None:
        data["page"] = page
    return {"id": fid, "kind": "frame", "x": x, "y": y, "width": 200, "height": 100, "data": data}


def test_without_page_numbers_the_order_is_reading_order() -> None:
    assert _order([_frame(1, 300, 0), _frame(2, 0, 0), _frame(3, 0, 300)]) == [2, 1, 3]


def test_page_numbers_win_and_an_unnumbered_frame_follows() -> None:
    frames = [_frame(1, 0, 0, page=3), _frame(2, 300, 0, page=1), _frame(3, 0, 300, page=2), _frame(4, 600, 0)]
    assert _order(frames) == [2, 3, 1, 4]


def test_the_pages_tab_is_on_the_sidebar_and_named() -> None:
    assert 'data-side-tab="pages"' in INDEX
    section = INDEX[INDEX.index('data-side-panel="pages"') :]
    section = section[: section.index("</section>")]
    assert 'role="tree"' in section and 'aria-label="Pages, in presentation order"' in section
    for name in ("wbRenderPages", "wbPageMove", "wbPageGo", "wbPagePresent"):
        assert f"function {name}(" in LIBRARY, name
    move = _function(LIBRARY, "wbPageMove")
    assert "wbRecordGesture(" in move, "a reorder is one undo step"


def test_a_page_number_is_kept_by_the_server(ai_client):
    board = ai_client.post("/whiteboard/boards", json={"name": "Pages", "type": "board"}).json()
    made = ai_client.post("/whiteboard/objects", json={
        "kind": "frame", "data": {"content": "One", "page": 2}, "board_id": board["id"], "x": 0, "y": 0, "width": 200, "height": 100,
    })
    assert made.status_code in (200, 201), made.text
    assert made.json()["data"]["page"] == 2
    bad = ai_client.post("/whiteboard/objects", json={
        "kind": "frame", "data": {"content": "One", "page": 0}, "board_id": board["id"], "x": 0, "y": 0, "width": 200, "height": 100,
    })
    assert bad.status_code == 422


def test_a_locked_item_answers_the_pointer() -> None:
    for name in ("wbLockedItemAt", "wbPaintLockBadges", "wbOnLockPress"):
        assert f"function {name}(" in BOARD, name
    # Audit 1028 B20: the lock is a persistent badge, not a hover-only pin.
    assert "wbPaintLockBadges();" in _function(BOARD, "wbPaintLocks")
    assert "wbPaintLockHover" not in BOARD and "wbOnLockHoverMove" not in BOARD
    assert 'addEventListener("pointerdown", wbOnLockPress, true)' in BOARD
    assert "Locked. Right-click to unlock it." in BOARD
    assert "Unlock this item" in BOARD
    hit = _function(BOARD, "wbLockedItemAt")
    assert "wbItemHidden(" in hit, "a hidden item is not under the pointer"
