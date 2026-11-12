"""INBOX 1694 (a), the owner 2026-11-07: a two-finger pinch in the lightbox was "very slow or minimal". A pinch is a Ctrl
wheel of small pixel deltas; it moved 0.002 per pixel, a fifth of the diagram view's rate (`diagramModel.view.math.factor`,
0.01). The pinch now takes that rate; a mouse notch keeps its one step (x1.22)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "lightbox-view.js").read_text(encoding="utf-8")


def _factor(event: dict) -> float:
    start = SRC.index("function lightboxZoomFactor(")
    fn = SRC[start : SRC.index("\n}\n", start) + 2]
    out = subprocess.run(["node", "-e", f"{fn};process.stdout.write(String(lightboxZoomFactor({json.dumps(event)})))"],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_pinch_zooms_at_the_diagram_views_rate_and_a_notch_is_one_step():
    pinch = _factor({"ctrlKey": True, "deltaMode": 0, "deltaY": -10})
    assert 1.09 < pinch < 1.12  # the diagram view's own number for the same gesture
    assert _factor({"ctrlKey": True, "deltaMode": 0, "deltaY": 10}) == pytest.approx(1 / pinch)
    assert _factor({"ctrlKey": False, "deltaMode": 0, "deltaY": -100}) == pytest.approx(1.2214, abs=1e-3)
    assert _factor({"ctrlKey": False, "deltaMode": 1, "deltaY": -3}) == pytest.approx(1.2712, abs=1e-3)


def test_the_stage_wheel_zooms_by_that_factor():
    wheel = SRC[SRC.index('stage.addEventListener(\n    "wheel"') :][:2000]
    assert "lightboxZoomFactor(e)" in wheel
