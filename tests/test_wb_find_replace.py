"""Find and replace on a board (INBOX 797, canvasdepth; WHITEBOARD_PLAN
section 9 and "canvasdepth, ranked" row 6). The board's find looked in cards
and text boxes only, so a shape's or a connector's label was never found, and
nothing could be replaced. Find now reads labels; Replace all rewrites text
boxes, shape labels and connector labels in one undo step (a card is a note,
edited in the note). The browser half is `scratchpad/ui-sweeps/wbreplace.js`."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start : WB.index("\n}\n", start) + 3]


def _replace(text, find, to):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    #: `wbReplaceText` builds its pattern with `wbSearchPattern`, so both are cut out.
    script = _function("wbSearchPattern") + _function("wbReplaceText") + f"console.log(JSON.stringify(wbReplaceText({json.dumps(text)}, {json.dumps(find)}, {json.dumps(to)})));"
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_replace_is_literal_and_ignores_case():
    assert _replace("Ship it, then SHIP again", "ship", "send") == {"text": "send it, then send again", "count": 2}
    assert _replace("a.b a+b", "a.b", "x") == {"text": "x a+b", "count": 1}
    assert _replace("$1 and $&", "and", "$&$&") == {"text": "$1 $&$& $&", "count": 1}
    assert _replace("nothing", "zzz", "y") == {"text": "nothing", "count": 0}


def test_find_reads_labels_and_replace_is_one_step():
    find = _function("wbSearchTextFor")
    assert 'kind === "sketch"' in find and "label" in find
    #: A text box's `data` arrives parsed; parsing it again threw and found nothing.
    assert 'typeof item.data === "string"' in find
    run = _function("wbBoardSearchRun")
    assert '"sketch"' in run
    replace = WB[WB.index("async function wbBoardReplaceAll(") :]
    replace = replace[: replace.index("\n}\n")]
    assert "wbPushMoveBatch(" in replace and "wbSaveSketchProps(" in replace and "wbSaveObject(" in replace


def test_replace_all_rewrites_data_values_that_find_matches():
    """Review note on PR 191: Find counted a match inside a custom property value,
    Replace all skipped it (count 3 of 3, toast 1)."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = (
        _function("wbSearchPattern") + _function("wbReplaceText") + _function("wbReplaceInProps")
        + 'console.log(JSON.stringify(wbReplaceInProps({Owner: "Ship team", n: 3}, "ship", "send")));'
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out == {"props": {"Owner": "send team", "n": 3}, "count": 1}
    body = WB[WB.index("async function wbBoardReplaceAll(") :]
    assert "wbReplaceInProps(" in body[: body.index("\n}\n")]


def test_the_find_bar_sits_above_the_format_panel():
    """Review note on PR 191: at 1000px the Format panel covered the find bar's
    right end (elementFromPoint), at 700px its Replace row."""
    import re

    css = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")

    def z(selector: str) -> int:
        return int(re.search(r"\n" + re.escape(selector) + r" \{[^}]*?z-index: (\d+);", css).group(1))

    assert z(".wb-search-bar") > z(".wb-format")
