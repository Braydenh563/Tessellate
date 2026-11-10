"""The map's find bar reads a topic's note (MINDMAP gap 13, OPEN F3).

Driven in Chromium 2026-11-10: a map topic "Alpha" given the note "Remember the zebra crossing", Find "zebra": 0 matches before, 1 after
(`wbSearchTextFor` returned "alpha" before and "alpha\\nremember the zebra crossing" after).
"""

from pathlib import Path

WB = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def test_an_object_search_text_ends_with_its_note():
    start = WB.index("function wbSearchTextFor(")
    body = WB[start : start + 2400]
    assert 'const note = typeof data.note === "string" ? `\\n${data.note}` : "";' in body
    assert "${wbPropsText(data.props)}${note}`.toLowerCase()" in body


def test_replace_all_leaves_a_note_alone():
    # The replace walks `data.content`, cells and props only (wbReplaceText, wbReplaceInProps, wbReplaceInCells): a note is found, not rewritten.
    assert "data.note" not in WB[WB.index("async function wbBoardReplaceAll") : WB.index("function wbBoardSearchRun")]
