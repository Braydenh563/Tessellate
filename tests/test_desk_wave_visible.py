"""INBOX 1688 (b): the desk's Wave shows a raised hand in both Atlas looks.

The old wave frame raised the arm on the hair's side, where hand and hair are the same
tint, so no hand showed (measured: 0 solid pixels beside the head above the shoulder in
either look). The shipped frame now waves the other arm, out in the clear, and the render
script says so (`nmb-desk-wave`)."""
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
Image = pytest.importorskip("PIL.Image")

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "frontend" / "img" / "desk"
SOLID = 128
#: Rows from the top of the head to the shoulder in the shipped frames (source px). Re-registered 2026-11-14 (L150): the
#: new feminine frame's shoulder starts on row 149 (4 solid px at x 93 to 96), so the window ends one row above it.
ARM_ROWS = (85, 149)


def _solid(look: str, name: str):
    return np.asarray(Image.open(FRAMES / look / f"{name}.png").convert("RGBA").getchannel("A")) >= SOLID


@pytest.mark.parametrize("look", ["masculine", "feminine"])
def test_the_wave_frame_has_a_raised_hand_clear_of_the_head(look):
    stand = _solid(look, "stand")
    head_left = int(np.nonzero(stand[90:130].any(axis=0))[0].min())
    top, bottom = ARM_ROWS
    beside = lambda m: m[top:bottom, : head_left - 2]  # noqa: E731 - solid pixels left of the head, above the shoulder
    assert beside(stand).sum() == 0
    arm = beside(_solid(look, "wave"))
    ys, xs = np.nonzero(arm)
    assert arm.sum() >= 30, f"{look}: {int(arm.sum())} arm pixels beside the head"
    # The hand is up at the face, well above the shoulder, not hanging.
    assert ys.min() + top <= 125
    assert xs.max() - xs.min() >= 5 and ys.max() - ys.min() >= 6


def test_the_render_script_waves_the_arm_that_is_not_against_the_hair():
    js = (ROOT / "scripts" / "render_desk_frames.js").read_text(encoding="utf-8")
    assert '{ name: "wave", pose: "stand", classes: ["nmb-desk-wave"]' in js
    css = (ROOT / "frontend" / "css" / "08-consistency.css").read_text(encoding="utf-8")
    assert "#nm-buddy.nmb-desk-wave .atl-figure .nmb-arm-l { transform: rotate(" in css
