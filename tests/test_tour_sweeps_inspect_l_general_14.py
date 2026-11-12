"""Source text: the tour sweeps run in a browser this suite does not start
(L-general-14). tour.js keeps its state in a closure, so a sweep that names a
closure function bare stops on a ReferenceError; they read `openTour.inspect`."""

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def _closure_names() -> set[str]:
    js = frontend_text("tour.js")
    found = set(re.findall(r"^(?:async )?function (\w+)|^(?:const|let) (\w+)", js, re.M))
    names = {a or b for a, b in found}
    exported = {"openTour", "TOUR_ENABLED", "renderTourReplay"}
    return names - exported


def test_every_tour_sweep_reaches_the_closure_through_inspect():
    names = _closure_names()
    assert {"tourRun", "tourNext", "TOUR_SECTIONS"} <= names
    for sweep in sorted((ROOT / "scratchpad" / "ui-sweeps").glob("*.js")):
        text = sweep.read_text(encoding="utf-8")
        for name in names:
            bare = re.search(rf'(?<![.\w"]){name}\b(?! reads)', text)
            assert not bare, f"{sweep.name} names {name} bare"


def test_inspect_offers_what_the_sweeps_read():
    js = frontend_text("tour.js")
    block = js[js.index("openTour.inspect = {"):]
    block = block[: block.index("};")]
    for key in ("get run()", "sections:", "needs:", "place:", "activeTab:", "blockPanels:", "context:", "next:", "back:", "close:"):
        assert key in block, key
