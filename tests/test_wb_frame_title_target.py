"""A frame's title keeps a target-sized hit area at any zoom (harness-wb-1004
item 1).

The title is board text, so at a phone's fitted zoom (k 0.24) it was about
7px tall and a press-drag aimed at it landed on the board and moved nothing.
Its box now grows upward to `--target-min` on screen, which needs the inverse
zoom published to it: a rule that reads `--wb-inv-zoom` without its selector
in `WB_INV_ZOOM_GRIPS` stays at the root's 1 (test_wb_navigator_cost.py keeps
the two lists equal; this keeps the title in both). Measured in a browser by
scratchpad/ui-sweeps/left1005-frametitle.js: 44px at k 0.21 on a phone, and
the frame, an inner frame and its sticky move by one delta with nothing, the
frame, everything or the inner pair selected.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
WB_JS = frontend_text("whiteboard.js")


def _rules(selector: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    return [body for sels, body in re.findall(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", text)
            if selector in [s.strip() for s in sels.split(",")]]


def test_the_frame_title_grows_to_a_target_on_screen():
    bodies = " ".join(_rules(".wb-object-frame .wb-frame-title"))
    assert "var(--target-min) * var(--wb-inv-zoom)" in bodies
    # A border, not a pseudo-element: the title clips its own overflow.
    assert re.search(r"border-top:\s*max\(0px,\s*calc\(var\(--target-min\) \* var\(--wb-inv-zoom\)", bodies)
    editing = " ".join(_rules(".wb-object-frame.wb-text-editing .wb-frame-title"))
    assert "border-top-width: 0" in editing


def test_the_inverse_zoom_is_published_to_the_title():
    listed = re.search(r"const WB_INV_ZOOM_GRIPS = \[(.*?)\];", WB_JS, re.S)
    assert listed and '".wb-object-frame .wb-frame-title"' in listed.group(1)
