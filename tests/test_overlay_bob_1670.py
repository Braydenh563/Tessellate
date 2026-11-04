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


def test_the_engine_bob_is_slow_and_small() -> None:
    e = Engine((100, 120), ONE, rng=random.Random(1), gait="float", home=(800, 920))
    e.y = 700.0
    e.bob_gain = 1.0
    ys = []
    for i in range(0, 60 * 40):  # 40 s at 60 fps
        e.now = i / 60.0
        ys.append(e._display("stand")[1])
    ys = np.array(ys) - np.mean(ys)
    assert ys.max() - ys.min() <= 5.0, ys.max() - ys.min()
    freq = np.abs(np.fft.rfft(ys))
    hz = np.fft.rfftfreq(len(ys), 1 / 60.0)[int(np.argmax(freq[1:])) + 1]
    assert hz < 0.3, hz
    assert eng.BOB_HZ < 0.3 and eng.BOB <= 5.0


def centroid_y(path: Path) -> float:
    alpha = np.array(Image.open(path).convert("RGBA"))[..., 3].astype(float)
    return float((alpha * np.arange(alpha.shape[0])[:, None]).sum() / alpha.sum()) / 2.0  # css px


@pytest.mark.parametrize("look", LOOKS)
def test_no_frame_set_bobs_the_figure_by_itself(look: str) -> None:
    """The drift frames (`walk0` to `walk5`, 8 a second) once carried 9.7 px of up and down
    (1.33 Hz) and the idle ones 1.6 px (0.67 Hz): the bob's fast twin."""
    d = frames_dir() / look
    walk = [centroid_y(d / f"walk{i}.png") for i in range(6)]
    idle = [centroid_y(d / f"idle{i}.png") for i in range(IDLE_COUNT)]
    assert max(walk) - min(walk) <= 3.0, (look, max(walk) - min(walk))
    assert max(idle) - min(idle) <= 1.2, (look, max(idle) - min(idle))


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
