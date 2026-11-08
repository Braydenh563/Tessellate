"""A pull from the companion's drawing is a grab, not a text selection (INBOX 1696 bb).

The owner: "the screen scrolls again when I throw the in-app companion
(sometimes)". Sitting or standing, the handle ends at the seat or the soles so
a button under the legs stays usable, but the drawing reaches past it (19px
left, 26 right, 47 below, scratchpad/ui-sweeps/buddyhit1696.js): a pull that
began there was the page's, a text selection that autoscrolls. Measured on a
live page (24 pulls over a scroller): 11 of 17 pulls from the drawing outside
the handle scrolled it and selected text, none grabbed; with the block, 14 of
14 grabbed, no scroller moved, no selection was made, and a click on a button
under the legs still reached it (8 of 8).

The block runs here against a fake page, the same text the browser loads.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@pytest.fixture(scope="module")
def run() -> dict:
    done = subprocess.run(["node", str(ROOT / "tests" / "_pull_grab_harness.js")], capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_every_pressed_point_of_the_drawing_that_becomes_a_pull_is_a_grab(run):
    r = run["regions"]
    assert r["points"] > 40
    assert r["grabs"] == r["points"]
    assert r["blocked"] == r["points"]


def test_the_press_is_handed_to_the_face_at_the_pressed_point(run):
    assert run["handed"] == [660, 530, 1]
    assert run["clearedSelection"] == 1


def test_a_plain_click_goes_through_to_what_is_under_it(run):
    assert run["click"] == {"grabbed": 0, "selectionBlocked": False, "clickSwallowed": False}


def test_under_four_pixels_is_not_a_pull(run):
    assert run["wobble"] == 0


def test_a_press_off_the_drawing_on_the_companion_or_another_button_is_not_taken(run):
    assert run["outside"] is False
    assert run["onBuddy"] is False
    assert run["rightButton"] is False
    assert run["otherPointer"] == 0
