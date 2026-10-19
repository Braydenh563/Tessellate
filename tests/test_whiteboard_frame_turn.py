"""WHITEBOARD_PLAN decision 42: turning a frame turns what lies wholly inside it.

The grip's drag captures the frame's contents at its start (the rule a title
drag uses), turns each about the frame's centre by the same delta, carries the
frame and its contents in one Undo step, and Ctrl turns the frame alone. The
centre maths is pure, so it runs in node; the wiring is read from source.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def test_the_grip_captures_contents_at_start_and_turns_them_with_one_delta() -> None:
    rotate = WB[WB.index("function objectRotateDrag()") :][:3600]
    assert "wbFrameTurnOrigin(d," in rotate, "the start captures the contents once"
    assert "ctrlKey" in rotate and "metaKey" in rotate, "Ctrl turns the frame alone"
    assert "wbFrameTurnLive(d)" in rotate and "wbFrameTurnEnd(d" in rotate
    assert "wbFrameContents(frame)" in _fn("wbFrameTurnOrigin"), "the same rule a title drag uses"
    live = _fn("wbApplyFrameTurn")
    assert "wbTurnAbout(" in live and "wbTransformPathD(" in live
    assert "rotation" in live


def test_one_undo_step_covers_the_frame_and_its_contents() -> None:
    end = _fn("wbFrameTurnEnd")
    assert "wbPushDragUndo(" in end and "action: \"move\"" in end
    assert "before: entry.before" in end


def test_a_cancelled_turn_puts_the_contents_back() -> None:
    rotate = WB[WB.index("function objectRotateDrag()") :][:1800]
    assert "wbFrameTurnRevert(d)" in rotate


def test_the_grip_title_names_the_contents_and_ctrl() -> None:
    assert "wbRotateGripTitle(d.kind)" in WB
    assert "Ctrl turns the frame alone" in _fn("wbRotateGripTitle")


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_a_point_turns_about_the_frame_centre() -> None:
    fn = _fn("wbTurnAbout")
    script = fn + "\nconsole.log(JSON.stringify([wbTurnAbout(100,100,150,100,90), wbTurnAbout(100,100,100,100,45), wbTurnAbout(0,0,10,0,180)]));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    a, b, c = json.loads(out)
    assert [round(v, 6) for v in a] == [100, 150]  # a quarter turn clockwise on a y-down board
    assert [round(v, 6) for v in b] == [100, 100]
    assert [round(v, 6) for v in c] == [-10, 0]


def test_no_new_top_level_state() -> None:
    assert not re.search(r"^(let|var) wbFrameTurn", WB, re.M)
