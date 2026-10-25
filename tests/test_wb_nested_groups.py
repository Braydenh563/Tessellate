"""INBOX 1354: groups nest. `group_id` is a chain, outermost first, joined by
`>`; Group puts a new id in front, Ungroup takes the shared innermost off, so
ungrouping the outer group of a group of groups leaves the inner one.

The browser half is `scratchpad/ui-sweeps/paint1026-groups.js` (seven boxes,
reload, undo, redo, double-click into a group); this pins the pure functions.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOARD = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = BOARD.index(f"function {name}(")
    return BOARD[start : BOARD.index("\n}\n", start) + 3]


def _run(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = "const WB_GROUP_SEP = \">\";\n" + "".join(
        _function(n) for n in ("wbGroupChain", "wbTopGroup", "wbCommonGroupPrefix", "wbGroupButtonState")
    ) + f"\nconsole.log(JSON.stringify({expr}));\n"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.parametrize(
    ("groups", "can_group", "can_ungroup"),
    [
        (["o>i", "o>i", "o", "o"], False, True),  # the outer group: ungroup it
        (["o>i", "o>i"], False, True),  # drilled into the inner group
        (["i", "i", None, None], True, False),  # a group and two loose: group them
        (["a", "b"], True, False),  # two groups: a group of groups
    ],
)
def test_nested_group_buttons(groups, can_group, can_ungroup) -> None:
    items = json.dumps([{"group_id": g} for g in groups])
    assert _run(f"wbGroupButtonState({items})") == {"canGroup": can_group, "canUngroup": can_ungroup}


def test_common_prefix_and_top_group() -> None:
    assert _run('wbCommonGroupPrefix([{group_id: "o>i"}, {group_id: "o"}])') == ["o"]
    assert _run('wbCommonGroupPrefix([{group_id: "o>i"}, {group_id: "o>i"}])') == ["o", "i"]
    assert _run('wbTopGroup({group_id: "o>i"})') == "o"
    assert _run("wbGroupChain({group_id: null})") == []


def test_ungroup_takes_the_shared_innermost_off_and_group_prepends() -> None:
    ungroup = _function("wbUngroupSelection")
    assert "chain.splice(depth, 1)" in ungroup and "wbRecordGesture" in ungroup
    group = _function("wbGroupSelection")
    assert "[groupId, ...wbGroupChain(e.item)]" in group and "wbRecordGesture" in group
    # New ids are short so a chain five deep fits the 40-character column.
    assert "WB_GROUP_MAX_LEN = 40" in BOARD
