"""Linked stickers (MINDMAP_PLAN 14.4): one placed icon or emoji edited, every copy follows."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MORE = (ROOT / "frontend" / "js" / "whiteboard-map-more.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
PLAN = (ROOT / "docs" / "roadmap" / "WHITEBOARD_PLAN.md").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = MORE.index(f"function {name}(")
    return MORE[start : MORE.index("\n  }\n", start) + 5]


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    code = "function wbSketchData(s) { try { return JSON.parse(s.data); } catch { return null; } }" + _function("wbStickerKey") + _function("wbStickerCopiesOf") + f"console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)


def test_a_sticker_is_known_by_its_icon_or_its_glyph() -> None:
    assert _run('wbStickerKey("sketch", {data: JSON.stringify({icon: "star"})})') == "icon:star"
    assert _run('wbStickerKey("object", {kind: "text", data: {sticker: true, content: "🔥"}})') == "emoji:🔥"
    assert _run('wbStickerKey("object", {kind: "text", data: {content: "plain"}})') is None
    assert _run('wbStickerKey("sketch", {data: JSON.stringify({d: "M0"})})') is None


def test_copies_are_every_item_with_the_same_key() -> None:
    expr = (
        'wbStickerCopiesOf("emoji:🔥", {sketches: [{id: 1, data: JSON.stringify({icon: "star"})}, {id: 2, data: JSON.stringify({icon: "star"})}],'
        ' objects: [{id: 3, kind: "text", data: {sticker: true, content: "🔥"}},'
        ' {id: 4, kind: "text", data: {sticker: true, content: "🔥"}}, {id: 5, kind: "text", data: {content: "🔥"}}]}).map((e) => e.item.id)'
    )
    assert _run(expr) == [3, 4]


def test_the_copies_follow_through_one_undo_step_and_the_ui_offers_it() -> None:
    match = MORE.split("async function wbStickerMatch(")[1].split("\n  }\n")[0]
    assert "wbRecordGesture" in match and "wbSaveMany" in match
    swap = MORE.split("async function wbStickerSwap(")[1].split("\n  }\n")[0]
    assert "wbRecordGesture" in swap and "wbSaveMany" in swap
    for command in ("sticker-match", "sticker-swap"):
        assert f'id: "{command}"' in CMD and f'data-wb-cmd="{command}"' in HTML
    assert "wbMapLazy.stickerMatch()" in CMD and "wbMapLazy.stickerSwap()" in CMD


def test_decision_25_points_at_the_plan_that_supersedes_it() -> None:
    block = PLAN.split("25. **The object library is independent copies**")[1].split("\n26.")[0]
    assert "MINDMAP_PLAN" in block and "14.4" in block
