"""INBOX 1670 (owner, 12:17Z): "it keeps bobbing really fast". Measured, not reasoned: the drawn
figure's vertical motion is the engine's bob plus whatever the frames bake in. The target is the
slow, graceful rate the owner asked for: under 0.3 Hz and a few px, and no frame set that
moves the figure up and down by itself."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tessellate.core.overlay import engine as eng
from tessellate.core.overlay.engine import Engine, Monitor
from tessellate.core.overlay.sprites import IDLE_COUNT, LOOKS, frames_dir

ONE = [Monitor((0, 0, 1920, 1040), 96)]


def test_the_engine_has_no_bob_and_the_drawn_window_does_not_move_in_the_air() -> None:
    # Intent moved (INBOX 1670, 16:40Z: "it randomly jitters up and down"): the slow, small bob of the 12:17Z fix is
    # gone altogether; the window stays on its row (the breath is in the figure's pose).
    e = Engine((100, 120), ONE, rng=random.Random(1), gait="float", home=(800, 920))
    e.y = 700.0
    ys = []
    for i in range(0, 60 * 40):  # 40 s at 60 fps
        e.now = i / 60.0
        ys.append(e._display("stand")[1])
    assert max(ys) == min(ys)
    assert not hasattr(eng, "BOB") and not hasattr(e, "bob_gain")


def centroid_y(path: Path, upper: float = 1.0, left: int | None = None) -> float:
    alpha = np.array(Image.open(path).convert("RGBA"))[..., 3].astype(float)
    alpha = alpha[: int(alpha.shape[0] * upper), :left]
    return float((alpha * np.arange(alpha.shape[0])[:, None]).sum() / alpha.sum()) / 2.0  # css px


@pytest.mark.parametrize("look", LOOKS)
def test_no_frame_set_bobs_the_figure_by_itself(look: str) -> None:
    """The drift frames (`walk0` to `walk11`) once carried 9.7 px of up and down
    (1.33 Hz) and the idle ones 1.6 px (0.67 Hz): the bob's fast twin."""
    d = frames_dir() / look
    walk = [centroid_y(d / f"walk{i}.png") for i in range(12)]
    # Intent moved (INBOX 1696 hh, deskframes-1108): the idle frames now hold the tail at the loop's own 24 moments, so the
    # whole figure's centroid carries the tail's swing (masculine 1.75 px, its curl and glow rising and falling over the
    # loop; the live tail does the same). A bob is the body going up and down, so the idle bound reads the upper half.
    # Intent kept, how it is measured moved (L150, the new 269 px wide desk frames): the feminine tail's curl still reaches
    # into the upper half's right side (0.90 over the loop with it, 0.80 without), so the body is read left of column 150
    # (feminine 0.80, masculine 0.49); the bound stays 0.9.
    idle = [centroid_y(d / f"idle{i}.png", 0.5, 150) for i in range(IDLE_COUNT)]
    assert max(walk) - min(walk) <= 3.0, (look, max(walk) - min(walk))
    # Intent kept (no up and down of its own faster than a breath): 24 frames sample the tail's swing
    # at more points than 12 did, and two renders of the same frame differ by about half a pixel, so the
    # bound is 1.4 (measured 1.28 and 1.05). The bug it guards was 1.6 px at 0.67 Hz.
    # Review of deskframes-1108: the upper half measures 0.33 (masculine) and 0.71 (feminine), so 1.4 there left a
    # 1 px bob unseen; 0.9 keeps the half pixel two renders differ by. The lower half (tail, feet) is held below.
    assert max(idle) - min(idle) <= 0.9, (look, max(idle) - min(idle))
    # The figure never sinks or lifts through the loop: every idle frame's lowest drawn row (alpha 32 and up, past
    # the faint wash; the solid rows at 200 follow the tail's own swing, up to 5 px) is the stand's.
    def bottom(path: Path) -> int:
        alpha = np.array(Image.open(path).convert("RGBA"))[..., 3]
        return int(np.nonzero((alpha >= 32).any(axis=1))[0].max())

    feet = bottom(d / "stand.png")
    sunk = {i: bottom(d / f"idle{i}.png") - feet for i in range(IDLE_COUNT)}
    assert all(abs(v) <= 1 for v in sunk.values()), (look, sunk)


@pytest.mark.parametrize("look", LOOKS)
def test_the_idle_cycle_has_no_step_in_the_nebula_or_the_body_including_the_wrap(look: str) -> None:
    """INBOX 1670 "the nebular flow keeps blinking in and out": two or three frames of every idle
    cycle were captured with the page's own act in them (arms up, a half-hidden sit, hearts) or
    the stream at another moment, so the faint wash lost 30% of its mass and the body a third of
    its pixels for one frame at 8 a second, twice a cycle."""
    d = frames_dir() / look
    faint, solid = [], []
    for i in [*range(IDLE_COUNT), 0]:  # the last is the wrap back to idle0
        alpha = np.array(Image.open(d / f"idle{i}.png").convert("RGBA"))[..., 3].astype(float)
        wash = (alpha > 8) & (alpha < 90)
        faint.append(alpha[wash].sum() / 255.0)
        solid.append(float((alpha >= 200).sum()))
    for a, b in zip(faint, faint[1:]):
        assert abs(b - a) / max(a, b) <= 0.12, (look, faint)
    for a, b in zip(solid, solid[1:]):
        assert abs(b - a) / max(a, b) <= 0.03, (look, solid)
