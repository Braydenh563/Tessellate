"""A board point read back to the screen (wb5, the paste chip).

Measured (session scratchpad b2c.js, a canvas hidden and shown with no pointer
event between): `wbBoardToClient` read 16px left and 60px high of the painted
item at zoom 1, 0.5 and 2 and after a pan, and `wbClientToBoard` the same
amount the other way, because the origin cache is dropped only by pointer
events. The canvas now drops it when it resizes (it is shown, a panel opens),
and the chip reads the origin fresh.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start) + 3]


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "".join(_function(WB, n) for n in ("wbScreenToBoard", "wbBoardToScreen"))
    out = subprocess.run([node, "-e", script + f"\nconsole.log(JSON.stringify({expr}));"], capture_output=True, text=True, check=True)
    return json.loads(out.stdout.strip())


@pytest.mark.parametrize("t", ["{ x: 0, y: 0, k: 1 }", "{ x: 100, y: 50, k: 0.5 }", "{ x: -200, y: -100, k: 2 }", "{ x: 120, y: 80, k: 1 }"])
@pytest.mark.parametrize("scale", [1, 0.5])
def test_the_screen_and_the_board_are_each_others_inverse(t: str, scale: float) -> None:
    origin = f"{{ left: 16, top: 60, scale: {scale} }}"
    back = _run(f"wbScreenToBoard(...wbBoardToScreen(300, 200, {origin}, {t}), {origin}, {t})")
    assert back == pytest.approx([300, 200])


def test_a_board_point_lands_on_the_origin_plus_the_pan_and_zoom() -> None:
    at = _run("wbBoardToScreen(300, 200, { left: 16, top: 60, scale: 1 }, { x: -200, y: -100, k: 2 })")
    assert at == [416, 360]


def test_the_chip_reads_the_origin_fresh_through_the_one_conversion() -> None:
    body = _function(CMD, "wbBoardToClient")
    assert "wbClearCanvasRectCache()" in body
    assert "wbBoardToScreen(" in body


def test_a_canvas_that_resizes_drops_its_cached_origin() -> None:
    assert "new ResizeObserver(wbClearCanvasRectCache).observe(canvas)" in WB
