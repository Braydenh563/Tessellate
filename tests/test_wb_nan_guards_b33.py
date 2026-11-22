"""B33 (audit 1028 board): a non-number never reaches a board coordinate.

`wbSnap` rounds a coordinate to the grid; a NaN in came a NaN out, and NaN in
a transform or an `x` attribute is invalid where it is used, far from where it
was set."""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import shutil
import subprocess

import pytest

BOARD = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = BOARD.index(f"function {name}(")
    return BOARD[start : BOARD.index("\n}\n", start) + 3]


def _snap(value, snap_on: bool):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        "const WB_GRID_SPACING = 24;"
        f"function wbSnapOn() {{ return {str(snap_on).lower()}; }}"
        + _function("wbSnap")
        + f"console.log(JSON.stringify(wbSnap({value}, false)));"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout.strip()
    return json.loads(out)


@pytest.mark.parametrize("snap_on", [True, False])
def test_a_non_finite_coordinate_comes_back_as_zero(snap_on: bool) -> None:
    for bad in ("NaN", "Infinity", "undefined"):
        assert _snap(bad, snap_on) == 0, bad


def test_a_real_coordinate_is_snapped_or_left_alone() -> None:
    assert _snap(30, True) == 24
    assert _snap(30, False) == 30
