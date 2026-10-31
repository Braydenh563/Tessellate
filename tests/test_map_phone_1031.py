"""The mind map at 390px after a template (blind test 1031, item 11).

Measured before: the Trip plan template framed at zoom 0.242 (topic text 17px
drawn at 4px, pills 44x11 under 24px add handles), the boards picker read
"Min..." and the Notes list ended under the floating New note. The browser half
is run by hand against a served build (390x844, touch); these hold the rules.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
SELECTS = (ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
MISC = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
RESPONSIVE = (ROOT / "frontend" / "css" / "10-responsive.css").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _scales(width: int) -> dict:
    start = WB.index("const WB_MAP_OPEN_MIN_SCALE")
    consts = WB[start : WB.index("\n", start) + 1]
    start = WB.index("const WB_MAP_PHONE_MAX_WIDTH")
    consts += WB[start : WB.index("\n", WB.index("const WB_MAP_PHONE_SCALE", start)) + 1]
    start = WB.index("function wbMapFrameScales(")
    fn = WB[start : WB.index("\n}\n", start) + 3]
    script = consts + fn + f"console.log(JSON.stringify(wbMapFrameScales({{clientWidth: {width}}})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_phone_canvas_frames_at_a_scale_where_a_topic_reads_at_12px():
    scales = _scales(364)
    assert scales["min"] == scales["open"]
    assert 17 * scales["min"] >= 12


@needs_node
def test_a_wide_canvas_keeps_the_fit_floor_and_the_1_to_1_fallback():
    assert _scales(1200) == {"min": 0.45, "open": 1}


def test_the_frame_uses_the_scales_and_a_tidy_that_spills_frames_the_same_way():
    start = WB.index("function wbFrameMapOnOpen(")
    body = WB[start : WB.index("\n}\n", start)]
    assert "scales.min" in body and "scales.open" in body
    assert "wbFrameMapOnOpen();" in MAP[MAP.index("wbMapSpillsOffCanvas()) wbFrame") :][:80]
    assert "if (onlyBranch == null && wbMapSpillsOffCanvas()) wbZoomToFit" not in MAP


def test_the_boards_picker_face_is_the_name_alone_on_a_phone():
    assert "opt.dataset.faceNarrow = board.title;" in WB
    assert "option.dataset.faceNarrow" in SELECTS and "(max-width: 599.98px)" in SELECTS
    assert "#wb-map-chip {\n    display: none;" in MISC


def test_the_notes_list_ends_above_the_floating_button():
    rule = "padding-bottom: max(var(--scroll-top-clearance), calc(var(--target-min) + var(--space-5) + var(--space-3)));"
    assert rule in RESPONSIVE
