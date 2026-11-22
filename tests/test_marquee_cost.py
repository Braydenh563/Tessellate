"""The selection rectangle does not re-layerize the page (INBOX 410: "drag
selection on the whiteboard and mindmap is laggy as well").

`scratchpad/ui-sweeps/marqueeperf.js` is the measurement: a real 80-move drag
over a board of text boxes and a map of topics, traced. The rectangle was an
SVG `<rect>` whose attributes were rewritten on every pointermove, and every
such write re-layerizes the whole page, a cost that grows with the board. On
a map of 200 topics, 60 frames of `<rect>` writes cost 445ms of Layerize, and
so did 60 frames of `transform` writes to promoted boxes (419ms), which is why
the fix is not that; 60 frames of canvas drawing cost 8.7ms.

The suite cannot trace a browser, so this holds the shape the trace came from:
the rectangle is drawn on a canvas, at most once a frame, with no style or
attribute write per move; and the release restyles only what changed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "js").glob("*.js")))
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def _inner(name: str) -> str:
    """A function nested in `initWhiteboard`, from its line to the next one."""
    match = re.search(rf"^\s+function {re.escape(name)}\(", JS, re.MULTILINE)
    assert match, f"{name} is gone; this lint is about its body"
    rest = JS[match.end():]
    end = re.search(r"^\s+function \w+\(|^\s+window\.addEventListener\(", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def test_the_rectangle_is_drawn_on_a_canvas() -> None:
    begin = _inner("wbBeginMarqueeRect")
    assert 'document.createElement("canvas")' in begin
    draw = _inner("wbDrawMarquee")
    assert 'getContext("2d")' in draw
    assert "setAttribute(" not in draw and ".style." not in draw, (
        "a style or attribute write per move re-layerizes the page"
    )


def test_the_rectangle_is_drawn_at_most_once_a_frame() -> None:
    assert "requestAnimationFrame(wbDrawMarquee)" in JS


def test_the_canvas_is_a_layer_of_its_own() -> None:
    rule = re.search(r"\.wb-marquee \{([^}]*)\}", CSS)
    assert rule and "will-change: transform" in rule.group(1) and "pointer-events: none" in rule.group(1)


def test_the_release_touches_only_what_changed() -> None:
    #: whiteboard-bar.js wraps it (L286), so it starts at its own indent and ends at the brace on that indent.
    match = re.search(r"^( *)function wbApplySelectionHighlight\(", JS, re.MULTILINE)
    assert match, "wbApplySelectionHighlight is gone; this lint is about its body"
    body = JS[match.end():].split("\n" + match.group(1) + "}\n", 1)[0]
    assert 'if (!wanted.has(el)) el.classList.remove("wb-selected"' in body
    assert '.forEach((el) => el.classList.remove("wb-selected", "wb-in-group"))' not in body
