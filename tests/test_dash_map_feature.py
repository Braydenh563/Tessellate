"""The dashboard's map widget follows the map's shape (INBOX 553(d), the
owner's decision: "dynamic depending on map size and scale").

`dashMapFeatureHeight` is pure and runs here in node; the real widget is
measured by `scratchpad/ui-sweeps/mmdoc1005-dashmap.js`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "frontend" / "js" / "dash-boards.js").read_text(encoding="utf-8")
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")


def _height(width, aspect, items):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = SRC.index("const DASH_MAP_FEATURE")
    end = SRC.index("//: The large picture")
    script = SRC[start:end] + f"\nprocess.stdout.write(JSON.stringify(dashMapFeatureHeight({width}, {aspect}, {items})));"
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_a_small_map_is_drawn_at_a_readable_size_not_blown_up():
    # Three topics, nearly square, in a wide card: capped at the small height.
    assert _height(600, 1.2, 3) == 168


def test_a_tall_map_gets_a_taller_card_up_to_the_limit_then_fits_whole():
    assert _height(306, 1.5, 40) == 204  # its natural height
    assert _height(306, 0.6, 40) == 320  # taller than the cap: the cap
    assert _height(306, 0.2, 40) == 320  # and no taller, fitted inside


def test_a_long_thin_map_keeps_a_floor():
    assert _height(306, 8, 40) == 96


def test_the_widget_loads_lazily():
    assert 'dashBoards: ["/js/pick-row.js", "/js/dash-boards.js"]' in APP
