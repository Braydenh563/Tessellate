"""Find and replace on a board (INBOX 797, canvasdepth; WHITEBOARD_PLAN
section 9 and "canvasdepth, ranked" row 6). The board's find looked in cards
and text boxes only, so a shape's or a connector's label was never found, and
nothing could be replaced. Find now reads labels; Replace all rewrites text
boxes, shape labels and connector labels in one undo step (a card is a note,
edited in the note). The browser half is `scratchpad/ui-sweeps/wbreplace.js`."""

from tests._app_js import frontend_text
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = frontend_text("whiteboard.js")


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
    #: One undo step and one save for the lot (BD2): `wbCommitMoves` saves the rows
    #: and pushes the batch; `wbReplaceWrite` writes a hit into a sketch or an object.
    assert "wbCommitMoves(" in replace and "wbReplaceWrite(" in replace
    write = WB[WB.index("function wbReplaceWrite(") :]
    write = write[: write.index("\n}\n")]
    assert "wbSketchSetProps(" in write and 'kind === "object"' in write


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

    # The Format panel's rules moved to the board's lazy sheet (INBOX 1510a).
    css = "".join((ROOT / "frontend" / "css" / f).read_text(encoding="utf-8") for f in ("07-whiteboard-misc.css", "library-lazy.css"))

    def z(selector: str) -> int:
        return int(re.search(r"\n" + re.escape(selector) + r" \{[^}]*?z-index: (\d+);", css).group(1))

    assert z(".wb-search-bar") > z(".wb-format")


def _replace_one_source() -> str:
    start = WB.index("wbBoardSearch.replaceOne = async")
    return WB[start : WB.index("\n};\n", start) + 4]


def _replace_one(matches, index, changed, still_matching=()):
    """Run `wbBoardSearch.replaceOne` against a stand-in for the find bar: `changed` is what Replace all reports, and
    `still_matching` are matches that remain after it (a card, or words that hold the needle)."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"""
const wbBoardSearch = {{ matches: {json.dumps(matches)}, index: {index} }};
const log = [];
const wbBoardSearchGo = (d) => {{ const t = wbBoardSearch.matches.length; wbBoardSearch.index = wbBoardSearch.index < 0 ? 0 : (wbBoardSearch.index + d + t) % t; log.push(['go', wbBoardSearch.index]); }};
const wbBoardReplaceAll = async (find, to, only) => {{
  log.push(['all', find, to, only]);
  const keep = {json.dumps(list(still_matching))};
  wbBoardSearch.matches = wbBoardSearch.matches.filter((m) => m.id !== only.id || keep.includes(m.id));
  wbBoardSearch.index = -1;
  return {json.dumps(changed)};
}};
{_replace_one_source()}
wbBoardSearch.replaceOne("ship", "send").then((n) => console.log(JSON.stringify({{ n, index: wbBoardSearch.index, log }})));
"""
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_replace_one_first_goes_to_the_first_match_then_replaces_in_the_one_it_is_on():
    matches = [{"kind": "sketch", "id": 1}, {"kind": "sketch", "id": 2}, {"kind": "sketch", "id": 3}]
    first = _replace_one(matches, -1, 1)
    assert first["n"] == 0 and first["log"] == [["go", 0]]
    #: On the second match: only it is replaced, and the bar moves to what is now second (the old third).
    second = _replace_one(matches, 1, 1)
    assert second["log"][0] == ["all", "ship", "send", {"kind": "sketch", "id": 2}]
    assert second["n"] == 1 and second["index"] == 1
    #: On the last one: it wraps round to the first.
    assert _replace_one(matches, 2, 1)["index"] == 0


def test_replace_one_steps_past_an_item_that_still_matches():
    matches = [{"kind": "node", "id": 7}, {"kind": "sketch", "id": 2}]
    got = _replace_one(matches, 0, 0, still_matching=[7])
    assert got["n"] == 0 and got["index"] == 1


def test_the_replace_row_has_a_replace_button_before_replace_all():
    assert 'one.id = "wb-replace-one";' in WB and "row.append(field, one, all);" in WB
    assert "if (only && (only.kind !== kind || only.id !== item.id)) continue;" in WB
