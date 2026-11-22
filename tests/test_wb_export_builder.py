"""L272: the export SVG is built from board data; one function reads the page.

`wbBuildExportSvg` used to call `getComputedStyle`, `querySelector` and
`getBoundingClientRect` all through its 354 lines. Now every read of the drawn
page is a method of `wbExportLook`, answering in plain data, and the builder
touches no element. Behaviour is pinned by `scratchpad/ui-sweeps/wbexport-parity.js`
(a fixed board and a fixed map: element counts per tag, rounded bounding boxes
and the SVG text, before and after: 20 of 20 identical).
"""

from __future__ import annotations

from tests._app_js import frontend_text
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WB = frontend_text("whiteboard.js")


def _function(name: str) -> str:
    start = WB.index(f"function {name}(")
    nxt = re.search(r"^(?:async )?function \w+\(", WB[start + 10 :], re.MULTILINE)
    return WB[start : start + 10 + nxt.start()] if nxt else WB[start:]


def test_the_builder_touches_no_element() -> None:
    body = "\n".join(ln for ln in _function("wbBuildExportSvg").splitlines() if not ln.lstrip().startswith("//"))
    for read in ("getComputedStyle", "querySelector", "getBoundingClientRect", "offsetWidth", "offsetHeight", "cloneNode", "document.", "classList", ".dataset"):
        assert read not in body, f"{read} is a live-page read; it belongs in wbExportLook"
    assert "wbExportLook()" in body


def test_the_look_is_where_the_reads_are() -> None:
    look = _function("wbExportLook")
    assert look.count("getComputedStyle(") >= 6
    for method in ("frame(", "structure(", "mapEdges(", "sketch(", "card(", "radii(", "topic(", "text(", "table("):
        assert f"\n    {method}" in look, method


def test_the_parity_sweep_exists() -> None:
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "wbexport-parity.js").read_text(encoding="utf-8")
    assert "wbBuildExportSvg" in sweep and "COMPARE" in sweep
