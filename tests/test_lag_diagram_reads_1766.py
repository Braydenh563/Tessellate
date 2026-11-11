"""INBOX 1766: the diagram's divider and hover outline read no box inside an event on a dirty page.

The owner's Windows lag log (Documents page, a diagram open, Atlas shown) kept `diagram-overlay.js` and
`diagram-split.js` among its forced layouts. Measured at 4x CPU: 20 drag moves of the divider were 239ms of forced
layout (`move@diagram-split.js`), because each move wrote `--dgm-list` and the next one began by reading the body's and
the handle's boxes. A pointer move over the picture read the picture's box in the event, after whatever a keystroke's
redraw or a pan had written. So a move works from widths measured when something outside it may have changed one, the
hover look is a task after a drawn frame, and the shelf button's offset reads before it writes, in such a task too.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"
SPLIT = (JS / "diagram-split.js").read_text(encoding="utf-8")
OVERLAY = (JS / "diagram-overlay.js").read_text(encoding="utf-8")

#: Everything that makes the browser bring style or layout up to date.
READS = re.compile(r"getComputedStyle\(|getBoundingClientRect\(|getClientRects\(|\.offset(?:Width|Height)\b|\.client(?:Width|Height|Left)\b")


def _code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))


def _block(src: str, head: str) -> str:
    """The braces-balanced text from `head` to the end of its first `{ ... }`."""
    start = src.index(head)
    depth = 0
    for i in range(src.index("{", start), len(src)):
        depth += src[i] == "{"
        depth -= src[i] == "}"
        if depth == 0:
            return src[start : i + 1]
    raise AssertionError(head)


def test_a_drag_move_and_an_arrow_key_read_no_box() -> None:
    apply = _code(_block(SPLIT, "const apply = (want, remember = true) =>"))
    assert not READS.search(apply), READS.search(apply).group(0)
    assert "math.clamp(want, size.body, size.handle)" in apply, "the ceiling comes from the widths kept"
    assert "size.pane = px;" in apply, "and the next step starts from the column just set"
    move = _code(_block(SPLIT, 'handle.addEventListener("pointerdown"'))
    # The press measures once; the move it installs reads nothing.
    assert move.count("measure();") == 1 and move.index("measure();") < move.index("const move =")
    assert not READS.search(move[move.index("const move =") :]), "a pointermove of the drag reads no box"
    keys = _code(_block(SPLIT, 'handle.addEventListener("keydown"'))
    assert not READS.search(keys) and "const now = size.pane;" in keys


def test_the_widths_are_measured_where_something_else_may_have_moved_them() -> None:
    measure = _block(SPLIT, "const measure = () =>")
    for box in ("body", "handle", "S.pane"):
        assert box in measure
    tight = _code(_block(SPLIT, "const tight = () =>"))
    assert tight.index("measure();") < tight.index("size.pane < TIGHT"), "a resize, a reset and a view change measure first"
    assert 'window.addEventListener("resize", tight);' in SPLIT


def test_the_shelf_button_reads_then_writes_in_a_task_after_a_drawn_frame() -> None:
    now = _code(_block(SPLIT, "const clearNow = () =>"))
    assert now.index("getComputedStyle(") < now.index("right.style.insetInlineEnd"), "reads, then the one write"
    assert now.count("right.style.insetInlineEnd") == 1, "a write before the reads laid the page out for each of them"
    ask = _code(_block(SPLIT, "const clear = () =>"))
    assert "afterFrames(() => setTimeout(clearNow), 1)" in ask and not READS.search(ask)
    assert "(S.fig.onzoom ||= []).push(clear);" in SPLIT and "(S.fig.onpaint ||= []).push(clear);" in SPLIT


def test_the_hover_outline_is_found_in_a_task_after_a_drawn_frame() -> None:
    move = _code(_block(OVERLAY, 'fig.addEventListener("pointermove"'))
    assert not READS.search(move), "the event keeps the pointer and asks once per frame"
    assert "at = [event.clientX, event.clientY];" in move and "afterFrames(() => setTimeout(look), 1)" in move
    assert "if (!looking)" in move, "one look per frame, however many moves"
    look = _code(_block(OVERLAY, "const look = () =>"))
    assert look.index("looking = 0;") < look.index("getBoundingClientRect("), "it can be asked for again from the next move"
    assert "at = null;" in _code(_block(OVERLAY, 'fig.addEventListener("pointerleave"'))


def test_a_draw_reads_the_picture_and_the_layer_once_each_before_it_writes() -> None:
    draw = _code(_block(OVERLAY, "const draw = () =>"))
    assert draw.count("img.getBoundingClientRect()") == 1 and draw.count("layer.getBoundingClientRect()") == 1
    assert draw.index("layer.getBoundingClientRect()") < draw.index("sync("), "every read comes before the first write"
