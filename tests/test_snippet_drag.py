"""Drag a snippet into the text (INBOX 904 B19).

The owner: "I can drag the snippet from the library and paste it where I drag
it to and there'll be a ghost cursor under my dragging cursor where it will
place and if I drag my mouse to the bottom or top of the document then it
will begin to scroll up or down". Click-to-insert at the caret stays. The
pure part (the scroll speed) runs here in node; the drag itself, in Chromium,
is `scratchpad/ui-sweeps/snippetdrag1018.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KIT = (ROOT / "frontend" / "js" / "documents-codekit.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = KIT.index(f"function {name}(")
    return KIT[start : KIT.index("\n}\n", start) + 3]


def test_a_row_is_draggable_and_carries_its_text() -> None:
    row = _body("docSnippetRow")
    assert "draggable = true" in row
    assert "docSnippetDragStart(event, entry)" in row
    start = _body("docSnippetDragStart")
    assert 'setData("text/plain"' in start and "docSnippetPlain(entry)" in start


def test_the_drop_inserts_at_the_pointer_and_stops_the_editors_own_paste() -> None:
    assert "docSnippetInsert(entry, { at: pos })" in KIT
    drop = KIT[KIT.index('"drop",') :][:700]
    assert "stopPropagation()" in drop and "preventDefault()" in drop and "posAtCoords" in drop
    assert "at == null" in _body("docSnippetInsert")


def test_a_ghost_caret_follows_the_pointer_and_the_edges_scroll() -> None:
    assert "doc-drop-ghost" in KIT and ".doc-drop-ghost" in CSS
    frame = _body("docSnippetDragFrame")
    assert "docSnippetScrollSpeed(" in frame and "scrollDOM.scrollTop" in frame
    assert "requestAnimationFrame" in frame
    rule = CSS[CSS.index(".doc-drop-ghost {") :][:500]
    assert "pointer-events: none" in rule and "var(--accent)" in rule


def test_a_drag_that_ends_leaves_nothing_behind() -> None:
    end = _body("docSnippetDragEnd")
    assert "cancelAnimationFrame" in end and ".remove()" in end
    assert '"dragend"' in KIT


def test_the_help_says_a_row_can_be_dragged() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "drag it into the text" in html
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "drag a row into the text" in topics


def _speed(values: list[list[float]]) -> list[int]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    match = re.search(r"function docSnippetScrollSpeed\(.*?\n}\n", KIT, re.S)
    assert match, "docSnippetScrollSpeed is missing"
    script = match.group(0) + f"\nprocess.stdout.write(JSON.stringify({json.dumps(values)}.map((v) => docSnippetScrollSpeed(...v))));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_scroll_speed_is_zero_in_the_middle_and_grows_toward_each_edge() -> None:
    #: (pointer y, editor top, editor bottom): a 300px editor from 100 to 400, band 48.
    got = _speed([[250, 100, 400], [100, 100, 400], [60, 100, 400], [110, 100, 400], [399, 100, 400], [380, 100, 400], [152, 100, 400]])
    assert got[0] == 0, "the middle never scrolls"
    assert got[1] < 0 and got[2] <= got[1], "above the top edge scrolls up, faster the further out"
    assert got[2] == -20, "the speed is capped"
    assert got[3] < 0 and abs(got[3]) < abs(got[1]), "inside the band, slower than at the edge"
    assert got[4] > 0 and got[5] > 0 and got[5] < got[4], "the bottom band scrolls down"
    assert got[6] == 0, "just outside the band"


def test_the_no_editor_toast_is_worded_per_document_kind() -> None:
    """Review note on PR 191: a text document was told to open a code document."""
    helper = _body("docNeedsDocument")
    assert '"Open a document first."' in helper and '"Open a code document first."' in helper
    assert "docNeedsDocument()" in _body("docSnippetDragStart")
    assert "docNeedsDocument()" in _body("docSnippetInsert")
