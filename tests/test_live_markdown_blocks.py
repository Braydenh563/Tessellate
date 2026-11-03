"""A streaming answer re-renders only its open block (audit 1028 E34).

`liveMarkdownRenderer` used to rebuild the whole answer from raw markdown on
every flush, so a 10 KB answer cost 38 renders and 4.1 s of long tasks at 4x
CPU throttle. Finished blocks are now drawn once and kept; only the text after
the last safe block break is drawn again. The break finder is a pure function
(`liveMarkdownRenderer.blockBreak`, between the LIVE-BLOCKS markers) so what may and may not be
frozen is checked here without a DOM.

What must *not* freeze: anything inside a code fence, a line that would
continue a list or a table, an indented line, a half-typed line.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASK_JS = ROOT / "frontend" / "js" / "capture-ask.js"


def region() -> str:
    text = ASK_JS.read_text(encoding="utf-8")
    begin, end = "// LIVE-BLOCKS-BEGIN", "// LIVE-BLOCKS-END"
    start, stop = text.find(begin), text.find(end)
    assert start != -1 and stop > start, "LIVE-BLOCKS markers are missing from capture-ask.js"
    return text[start + len(begin) : stop]


DRIVER = r"""
const cases = {
  none: liveMarkdownRenderer.blockBreak("one paragraph still going", 0),
  twoParas: liveMarkdownRenderer.blockBreak("First.\n\nSecond starts\n", 0),
  heading: liveMarkdownRenderer.blockBreak("Intro.\n\n## Next\nmore", 0),
  halfLine: liveMarkdownRenderer.blockBreak("Intro.\n\nSecon", 0),
  fenceOpen: liveMarkdownRenderer.blockBreak("Intro.\n\n```js\ncode\n\nmore code\n", 0),
  fenceClosed: liveMarkdownRenderer.blockBreak("Intro.\n\n```js\ncode\n\nmore\n```\n\nAfter\n", 0),
  listContinues: liveMarkdownRenderer.blockBreak("Intro.\n\n- a\n\n- b\n", 0),
  orderedContinues: liveMarkdownRenderer.blockBreak("Intro.\n\n1. a\n\n2. b\n", 0),
  indented: liveMarkdownRenderer.blockBreak("- a\n\n    nested para\n", 0),
  tableRow: liveMarkdownRenderer.blockBreak("Intro.\n\n| a | b |\n", 0),
  quote: liveMarkdownRenderer.blockBreak("Intro.\n\n> quoted\n", 0),
  afterList: liveMarkdownRenderer.blockBreak("- a\n- b\n\nPlain after\n", 0),
  fromOffset: liveMarkdownRenderer.blockBreak("One.\n\nTwo.\n\nThree\n", 6),
  maths: liveMarkdownRenderer.blockBreak("Intro.\n\n$$\nx\n\ny\n$$\n\nAfter\n", 0),
  footnote: liveMarkdownRenderer.blockBreak("Intro[^1].\n\nNext\n", 0),
  columns: liveMarkdownRenderer.blockBreak("Intro.\n\n:::columns\nA\n\nB\n:::\n\nAfter\n", 0),
};
console.log(JSON.stringify(cases));
"""


@pytest.fixture(scope="module")
def cases() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    proc = subprocess.run([node, "-e", "function liveMarkdownRenderer() {}\n" + region() + DRIVER], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_no_break_while_the_first_block_is_open(cases):
    assert cases["none"] == 0  # 0 is "no break yet"; -1 is "do not split"
    assert cases["halfLine"] == 0  # a half-typed line is never a block start


def test_breaks_at_the_start_of_the_last_block(cases):
    assert cases["twoParas"] == len("First.\n\n")
    assert cases["heading"] == len("Intro.\n\n")
    assert cases["afterList"] == len("- a\n- b\n\n")


def test_nothing_inside_a_fence_freezes(cases):
    assert cases["fenceOpen"] == len("Intro.\n\n")  # the fence itself starts a block
    assert cases["fenceClosed"] == len("Intro.\n\n```js\ncode\n\nmore\n```\n\n")


def test_lines_that_continue_an_earlier_block_do_not_freeze(cases):
    #: A list item, a table row, a quote or an indented line may belong to the
    #: block above, so none of them starts a frozen block.
    for name in ("listContinues", "orderedContinues", "indented", "tableRow", "quote"):
        assert cases[name] == 0, name


def test_resumes_from_the_frozen_offset(cases):
    assert cases["fromOffset"] == len("One.\n\nTwo.\n\n")


def test_blocks_that_span_blank_lines_are_never_split(cases):
    #: Maths, columns and footnotes keep blank lines inside one block, or
    #: refer back to an earlier one: the whole text is drawn as before.
    assert cases["maths"] == -1
    assert cases["footnote"] == -1
    assert cases["columns"] == -1


def test_the_renderer_draws_only_the_open_block():
    text = ASK_JS.read_text(encoding="utf-8")
    start = text.index("function liveMarkdownRenderer")
    body = text[start : text.index("function stopAnswer", start)]
    assert "liveMarkdownRenderer.blockBreak(" in body
    #: Finished blocks are drawn into a scratch box and kept, so the box is
    #: never emptied by `renderMarkdown` itself while streaming.
    assert "renderMarkdown(box," not in body
