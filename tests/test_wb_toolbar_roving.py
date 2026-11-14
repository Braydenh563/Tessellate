"""L269: the tool rail is one tab stop per section (a roving tabindex), arrows walk a section, Home and End jump.

The key arithmetic runs in node; the wiring is read from the source, and the live count is
`scratchpad/ui-sweeps/wbtouch3.js` (rail 17 tab stops before, 7 after on an empty board; whole board 37 before)."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from tests import _js_scope
from tests._app_js import frontend_text, script_file_text


def _step(calls: list[list]) -> list[int]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"""
const onSurface = () => {{}};
const wbFmtState = {{}};
{frontend_text("whiteboard-toolbar.js")}
console.log(JSON.stringify({json.dumps(calls)}.map(([n, from, key, vertical]) => wbFmtState.toolbar.step(n, from, key, vertical))));
"""
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_arrows_walk_a_section_and_wrap_and_home_end_jump():
    got = _step([
        [4, 0, "ArrowRight", False], [4, 3, "ArrowRight", False], [4, 0, "ArrowLeft", False], [4, 2, "ArrowLeft", False],
        [4, 2, "Home", False], [4, 1, "End", False],
    ])
    assert got == [1, 0, 3, 1, 0, 3]


def test_up_and_down_walk_only_in_a_column_and_other_keys_are_not_ours():
    got = _step([[4, 1, "ArrowDown", False], [4, 1, "ArrowDown", True], [4, 1, "ArrowUp", True], [4, 1, "a", True], [0, 0, "Home", False], [3, -1, "Home", False]])
    assert got == [-1, 2, 0, -1, -1, -1]


def test_the_rail_wires_one_stop_per_section_and_leaves_the_shapes_menu_alone():
    src = script_file_text("whiteboard-toolbar.js")
    assert _js_scope.is_wrapped(src) and _js_scope.global_names(src) == set()
    assert "/js/whiteboard-toolbar.js" in script_file_text("lazy-entries.js")
    assert 'closest(".wb-shape-menu")' in src and "tabIndex = button === keep ? 0 : -1" in src
    # Home on a rail tool is the rail's, not "back to the top left" of the canvas.
    assert "#wb-tool-group" in script_file_text("whiteboard-keys.js")
