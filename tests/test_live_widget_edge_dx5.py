"""Audit 1102 DX5: arrowing the caret onto a rendered block does not move the page.

Measured before (scratchpad sweep p16c.js, the rich probe plus a picture, an
embed and a second display formula, walked down and back up by line after a
warm-up pass): onto `[TOC]` the content shrank 235 px and grew back 235 px on
leaving, onto `$$...$$` 55 and 47 px, onto the picture 53 to 113 px, onto the
embed 12 to 20 px. An arrow key that lands on a widget lands on its edge (a
widget has no inside to put a caret in), and the edge revealed it. The rule is
now: a caret shows a widget's source only from strictly inside it, which is
where Left or Right from the edge steps; a selection that starts in it or at
its edge still shows it (INBOX 1547's drag rule), and a selection crossing it
leaves it drawn.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
DOCS = (JS / "documents.js").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _rule() -> str:
    start = DOCS.index("function docLiveSpanTouched(")
    end = DOCS.index("\n}\n", start) + 3
    anchor = DOCS.index("docLiveSpanTouched.anchorIn = ")
    return DOCS[start:end] + DOCS[anchor : DOCS.index(";\n", anchor) + 2]


@needs_node
def test_a_caret_on_a_widgets_edge_leaves_it_drawn_and_one_inside_shows_it():
    script = (
        _rule()
        + """
const caret = (at) => [{ anchor: at, head: at, from: at, to: at, empty: true }];
const sel = (anchor, head) => [{ anchor, head, from: Math.min(anchor, head), to: Math.max(anchor, head), empty: anchor === head }];
const held = docLiveSpanTouched.anchorIn;
console.log(JSON.stringify({
  before: held(caret(10), 10, 15),
  after: held(caret(15), 10, 15),
  inside: held(caret(12), 10, 15),
  outside: held(caret(9), 10, 15),
  dragFromEdge: held(sel(10, 30), 10, 15),
  dragFromInside: held(sel(12, 30), 10, 15),
  crossing: held(sel(2, 30), 10, 15),
  spanEdge: docLiveSpanTouched(caret(15), 10, 15),
}));
"""
    )
    got = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout)
    assert got["before"] is False and got["after"] is False, "an arrow key landing on the edge moved the page"
    assert got["inside"] is True, "stepping in with Left or Right shows the source to edit"
    assert got["outside"] is False
    assert got["dragFromEdge"] is True and got["dragFromInside"] is True
    assert got["crossing"] is False, "INBOX 1547: a selection crossing a widget leaves it drawn"
    assert got["spanEdge"] is True, "an inline span's marks still show beside the caret (INBOX 1473 b)"
