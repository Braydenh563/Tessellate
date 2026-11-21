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

from tests._css_paths import FORMER_10, sheets

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
SELECTS = (ROOT / "frontend" / "js" / "sheets-selects.js").read_text(encoding="utf-8")
MISC = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
RESPONSIVE = sheets(*FORMER_10)

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
def test_a_phone_canvas_frames_at_a_scale_where_a_topic_reads_at_11px():
    # Owner 2026-11-09: fit down to a readable floor (11px of a 17px topic),
    # then centre the root; the old 0.72 left a 5-topic map 1 of 5 in view.
    scales = _scales(364)
    assert scales["min"] == scales["open"]
    assert 17 * scales["min"] >= 11
    assert scales["min"] < 0.72
    assert scales["centre"] is True and scales["pad"] == 16


@needs_node
def test_a_phone_fallback_centres_the_root_where_desktop_starts_at_the_content_edge():
    start = WB.index("function wbMapOpenTarget(")
    fn = WB[start : WB.index("\n}\n", start) + 3]
    free = {"left": 0, "top": 0, "right": 372, "bottom": 700}
    b = {"minX": 0, "minY": 0, "maxX": 2000, "maxY": 1500}
    r = {"minX": 0, "minY": 0, "maxX": 200, "maxY": 44}

    def run(centre: str) -> dict:
        script = fn + f"console.log(JSON.stringify(wbMapOpenTarget({json.dumps(b)}, {json.dumps(r)}, {json.dumps(free)}, 0.65, 48, {centre})));"
        return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)

    edge, centred = run("false"), run("true")
    assert edge["x"] > 0  # content edge: the root sits near the left
    assert abs(centred["x"] + 0.65 * 100 - 186) < 1 and abs(centred["y"] + 0.65 * 22 - 350) < 1


@needs_node
def test_a_wide_canvas_keeps_the_fit_floor_and_the_1_to_1_fallback():
    assert _scales(1200) == {"min": 0.45, "open": 1, "pad": 64, "centre": False}


def test_the_frame_uses_the_scales_and_a_tidy_that_spills_frames_a_narrow_canvas_the_same_way():
    start = WB.index("function wbFrameMapOnOpen(")
    body = WB[start : WB.index("\n}\n", start)]
    assert "scales.min" in body and "scales.open" in body
    # Review: desktop keeps the plain fit; only a narrow canvas takes the phone
    # frame, through wbFrameSpilledMap (tests/test_polish5_1031.py).
    assert "wbMapSpillsOffCanvas()) wbFrameSpilledMap();" in MAP


def test_the_boards_picker_face_is_the_name_alone_on_a_phone():
    assert "opt.dataset.faceNarrow = board.title;" in WB
    assert "option.dataset.faceNarrow" in SELECTS and "(max-width: 599.98px)" in SELECTS
    assert "#wb-map-chip {\n    display: none;" in MISC


def test_the_notes_list_ends_above_the_floating_button():
    rule = "padding-bottom: max(var(--scroll-top-clearance), calc(var(--target-min) + var(--space-5) + var(--space-3)));"
    assert rule in RESPONSIVE
