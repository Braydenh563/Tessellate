"""1107 diagram builder, round 2 (docs/roadmap/agent-remaining/diagbuild-1107.md): DD-6, DD-8a, DD-8, DD-4, DD-5, DD-10 to DD-13.

Source assertions for what the code must hold; the browser numbers (rects, key counts) are in each commit and in the remaining file.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


EMBED = _js("diagram-embed.js")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _phone_css() -> str:
    start = CSS.index("/* A phone's builder is a full-screen sheet")
    return CSS[start - 120 : start + 2600]


def test_a_phone_builder_is_a_full_screen_sheet_with_the_views_on_top_and_a_one_row_foot():
    # DD-6: 390 x 844 measured before: dialog 342 wide, dock 18 px outside it, foot three rows (153 px), Source under the foot.
    assert 'const viewbar = el("div", "dgm-viewbar")' in EMBED
    assert 'matchMedia("(max-width: 599.98px)")' in EMBED and "(phone.matches ? viewbar : foot).prepend(seg)" in EMBED
    assert "dialog.append(head, viewbar, body, foot)" in EMBED
    css = _phone_css()
    assert ".modal-overlay > .card.dgm-dialog" in css and "max-width: none" in css and "max-height: none" in css
    # Out of the notch and off the home indicator, as 10-responsive.css band 2 does for every other dialog.
    assert "env(safe-area-inset-top, 0px)" in css and "env(safe-area-inset-bottom, 0px)" in css
    assert ".dgm-dialog .space-dialog-actions" in css and "flex-wrap: nowrap" in css
    # The door's "Open an existing diagram" is its glyph on a phone, and keeps its name.
    assert ".dgm-known .ph-text" in css and 'known.setAttribute("aria-label", "Open an existing diagram")' in EMBED
    # An empty diagram's picture is a strip so the steps and the template button stay on the screen.
    assert ".dgm-picture-empty" in css[css.index("grid-template-rows: auto minmax(0, 1fr)") - 200 :]


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _math(expr: str):
    script = (
        "const vm=require('vm');const ctx={diagramModel:{}};vm.createContext(ctx);"
        f"vm.runInContext(require('fs').readFileSync({json.dumps(str(JS / 'diagram-view.js'))},'utf8'),ctx);"
        f"const m=ctx.diagramModel.view.math;process.stdout.write(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


MODEL = (
    "{nodes:[{id:'A',text:'Start',shape:'rect'},{id:'B',text:'Check',shape:'diamond'},{id:'C',text:'Done',shape:'rect'},{id:'D',text:'Lone',shape:'round'}],"
    "edges:[{from:'A',to:'B'},{from:'B',to:'C'}]}"
)
BOXES = "[{id:'A',x:50,y:20},{id:'B',x:50,y:100},{id:'C',x:150,y:180},{id:'D',x:-40,y:180}]"


@needs_node
def test_an_arrow_key_on_the_picture_reaches_the_nearest_box_that_way_or_the_top_left_one():
    # DD-8a: nothing picked starts at the top left; a box straight below beats one far to the side; no box that way is null.
    assert _math(f"m.reach({BOXES}, '', 0, 1).id") == "A"
    assert _math(f"m.reach({BOXES}, 'A', 0, 1).id") == "B"
    assert _math(f"m.reach({BOXES}, 'B', 0, 1).id") in ("C", "D")
    assert _math(f"m.reach({BOXES}, 'C', -1, 0).id") == "D"
    assert _math(f"m.reach({BOXES}, 'A', 0, -1)") is None
    assert _math(f"m.reach({BOXES}, 'A', 1, 0)") is None or _math(f"m.reach({BOXES}, 'A', 1, 0).id") == "C"


@needs_node
def test_the_picture_names_every_box_and_arrow_and_a_picked_box_names_its_arrows():
    # DD-8a: the alt text lists every box (a lone one too) and every arrow; the live region reads the box and its edges.
    said = _math(f"m.summary({MODEL})")
    assert said.startswith("Flowchart, 4 boxes (Start, Check, Done, Lone), 2 arrows: Start to Check, Check to Done")
    assert _math(f"m.said({MODEL}, 'B')") == "Check, decision. In from Start. Out to Done."
    assert _math(f"m.said({MODEL}, 'D')") == "Lone, pill. No arrows." or "No arrows." in _math(f"m.said({MODEL}, 'D')")
    assert _math("m.summary({nodes:[],edges:[]})") == "Flowchart, empty"


def test_the_picture_arrows_pick_and_shift_pans_and_the_description_is_on_the_figure():
    view = _js("diagram-view.js")
    assert "if (move && !event.shiftKey && choose(event.key)) return event.preventDefault();" in view
    assert 'fig.setAttribute("aria-description", (img.alt = math.summary(S.m)))' in view
    assert "diagramModel.builder.select(S, `n:${to.id}`)" in view and "tell(math.said(S.m, to.id))" in view
    # A kind's pane has no boxes, so its arrows still pan.
    assert "!S.k && S.m && S.hit?.boxes?.length" in view


def test_only_the_picked_row_keeps_tab_stops_so_the_picture_is_within_six_stops():
    # DD-8: five rows of four buttons put the first picture stop at 23 (1440, five boxes). Now the picked row's buttons only.
    builder = _js("diagram-builder.js")
    assert 'for (const c of b.querySelectorAll(":scope > .dgm-card button, :scope > .dgm-joins button"))' in builder
    assert "add.tabIndex = connect.tabIndex = -1;" in _js("diagram-steps.js")
