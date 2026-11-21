"""Reaction stamps on board items (MINDMAP_PLAN 14.4): the topic's stamps, reused on stickies and cards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MORE = (ROOT / "frontend" / "js" / "whiteboard-map-more.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def test_a_board_item_paints_stamps_through_the_topic_patch() -> None:
    assert "wbMapLazy.paintStamps(el, d)" in WB.split("function wbPaintVotes(")[1].split("\n}\n")[0]
    body = MORE.split("function wbStampPaint(")[1].split("\n  }\n")[0]
    assert "WB_MAP_STAMPS" in body and "stopPropagation" in body
    assert "wbMapStampPatch(" in MORE.split("async function wbStampSet(")[1].split("\n  }\n")[0]
    set_body = MORE.split("async function wbStampSet(")[1].split("\n  }\n")[0]
    assert "wbRecordGesture" in set_body and "wbSaveMany" in set_body


def test_stamps_have_a_command_a_menu_row_and_a_clear() -> None:
    assert 'id: "react"' in CMD and "wbMapLazy.stampMenu()" in CMD
    assert 'id: "clear-stamps"' in CMD
    assert 'data-wb-cmd="react"' in HTML and 'data-wb-cmd="clear-stamps"' in HTML


def test_stamps_travel_in_an_svg_export_and_have_a_style() -> None:
    assert "wbMapLazy.svgStamps(" in WB
    assert ".wb-stamps {" in CSS
