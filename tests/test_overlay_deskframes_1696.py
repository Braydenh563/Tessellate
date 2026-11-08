"""INBOX 1696 x, w, z, hh: the desk frames re-rendered (the wave swing, a tail pinned to one moment, eyes
open in `stand`), the eye boxes measured on them, no flat patch round the mouth, arms no thicker than the app's."""

from __future__ import annotations

import pytest
from PIL import Image

from tessellate.core.overlay import faces, sprites
from tessellate.core.overlay.sprites import SpriteSet

LOOKS = ("masculine", "feminine")
DIR = sprites.frames_dir()


def _dark(im: Image.Image, box: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    out = []
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            r, g, b, a = im.getpixel((x, y))
            if a > 200 and r < 90 and g < 90 and b < 190:
                out.append((x, y))
    return out


@pytest.mark.parametrize("look", LOOKS)
def test_stand_has_its_eyes_open_and_the_eye_box_is_on_them(look: str) -> None:
    im = Image.open(DIR / look / "stand.png").convert("RGBA")
    x0, y0, x1, y1 = sprites.LID_EYES[look]
    pts = _dark(im, (x0 - 8, y0 - 8, x1 + 8, y1 + 8))
    # a shut-eye stand (a blink caught by the render) has about a third of these
    assert len(pts) >= 70, (look, len(pts))
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    # the box's centre is the eyes' centre to 4 px (the lashes and brows pull the dark mass up and out)
    assert abs(cx - (x0 + x1) / 2) <= 4 and abs(cy - (y0 + y1) / 2) <= 5, (look, cx, cy)


@pytest.mark.parametrize("look", LOOKS)
@pytest.mark.parametrize("kind", ("content", "smile"))
def test_a_drawn_mouth_leaves_no_flat_patch_round_it(look: str, kind: str) -> None:
    """INBOX 1696 hh ("white paste around its mouth"): where the art's calm mouth was painted out, the skin must
    be the face's own tone: within 16 levels a channel of the frame there (a flat disc was 35 to 63 off)."""
    spr = SpriteSet(look)
    base = spr.frame("stand", 192, False)
    cx, cy, k = faces.head_point(spr, "stand", base, False, None)
    drawn = faces.draw(spr, "stand", base, False, None, (kind, 3), base)
    raw = Image.frombytes("RGBA", (base.width, base.height), base.bgra, "raw", "BGRa")
    now = Image.frombytes("RGBA", (drawn.width, drawn.height), drawn.bgra, "raw", "BGRa")
    my = cy + faces.MOUTH_DOWN * k
    worst = 0
    for dy in (-2.5, -1.5, 2.0, 3.0):
        for dx in (-6.5, -6.0, 6.0, 6.5):  # inside the painted-out ellipse, clear of the mouth's own ink
            p = (int(cx + dx * k), int(my + dy * k))
            a, b = now.getpixel(p), raw.getpixel(p)
            worst = max(worst, max(abs(a[i] - b[i]) for i in range(3)))
    assert worst <= 16, (look, kind, worst)


def test_solidify_grows_an_arm_by_less_than_a_pixel_at_128() -> None:
    """INBOX 1696 z: a 6 px arm (at the 2x capture) with a soft edge each side: the ramp may add at most 1 px
    of coverage at the 2x capture, which is under 0.5 px once the figure is drawn 128 px tall."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("rdf", Path(__file__).resolve().parent.parent / "scripts" / "render_desk_frames.py")
    rdf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rdf)
    for edge in (30, 60, 90, 110):
        profile = [edge, 255, 255, 255, 255, 255, 255, edge]
        before = sum(profile) / 255
        after = sum(rdf.solidify(a) for a in profile) / 255
        assert after - before <= 1.0 + 1e-9, (edge, before, after)
        assert (after - before) * 128 / 306 <= 0.5, (edge, after - before)
