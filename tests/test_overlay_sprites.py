"""The overlay's frames (BACKLOG 16, O2): the shipped PNGs and how they become
premultiplied BGRA for the layered window."""

from __future__ import annotations

from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from tessellate.core.overlay import sprites  # noqa: E402

DIR = Path(__file__).resolve().parent.parent / "frontend" / "img" / "desk"


def test_every_look_has_every_frame() -> None:
    for look in sprites.LOOKS:
        files = sorted(p.stem for p in (DIR / look).glob("*.png"))
        assert files == sorted(sprites.FRAME_NAMES), look
    assert len(sprites.FRAME_NAMES) == 16 and len(sprites.WALK_FRAMES) == 6


def test_frames_of_a_look_share_one_size_and_stay_small() -> None:
    total = 0
    for look in sprites.LOOKS:
        sizes = {Image.open(DIR / look / f"{n}.png").size for n in sprites.FRAME_NAMES}
        assert len(sizes) == 1, (look, sizes)
        total += sum((DIR / look / f"{n}.png").stat().st_size for n in sprites.FRAME_NAMES)
    assert total < 1_500_000, total


def test_frames_have_real_partial_alpha_and_a_figure() -> None:
    for look in sprites.LOOKS:
        for name in sprites.FRAME_NAMES:
            alpha = Image.open(DIR / look / f"{name}.png").convert("RGBA").getchannel("A")
            hist = alpha.histogram()
            assert sum(hist[sprites.ALPHA_FLOOR : 255]) > 200, (look, name, "soft edges missing: not true alpha")
            assert sum(hist[128:]) > 500, (look, name, "no figure")


def test_border_ring_is_clear_after_the_guard_at_every_dpi() -> None:
    for look in sprites.LOOKS:
        spr = sprites.SpriteSet(look, DIR)
        for dpi in (96, 144, 192):
            for flip in (False, True):
                for name in ("stand", "walk3", "wave", "sleep"):
                    f = spr.frame(name, dpi, flip)
                    im = Image.frombytes("RGBA", (f.width, f.height), f.bgra, "raw", "BGRa")
                    a = im.getchannel("A")
                    ring = [a.getpixel((x, y)) for x in range(f.width) for y in (0, f.height - 1)]
                    ring += [a.getpixel((x, y)) for y in range(f.height) for x in (0, f.width - 1)]
                    assert max(ring) == 0, (look, name, dpi, flip)


def test_no_pixel_between_zero_and_the_floor_survives() -> None:
    spr = sprites.SpriteSet("masculine", DIR)
    for dpi in (96, 120, 192):
        f = spr.frame("stand", dpi)
        alphas = f.bgra[3::4]
        assert not any(0 < a < sprites.ALPHA_FLOOR for a in alphas)


def test_premultiply_matches_hand_values() -> None:
    im = Image.new("RGBA", (4, 1))
    im.putdata([(200, 100, 50, 128), (255, 255, 255, 255), (10, 20, 30, 0), (255, 0, 0, 64)])
    out = sprites.premultiplied_bgra(im)
    # B, G, R premultiplied by alpha / 255, then A.
    assert list(out[0:4]) == [25, 50, 100, 128]
    assert list(out[4:8]) == [255, 255, 255, 255]
    assert list(out[8:12]) == [0, 0, 0, 0]
    assert list(out[12:16]) == [0, 0, 64, 64]


def test_clear_faint_alpha_zeroes_colour_with_it() -> None:
    im = Image.new("RGBA", (3, 1))
    im.putdata([(9, 9, 9, 3), (9, 9, 9, 8), (9, 9, 9, 200)])
    out = sprites.clear_faint_alpha(im)
    assert list(out.getdata()) == [(0, 0, 0, 0), (9, 9, 9, 8), (9, 9, 9, 200)]


def test_mirror_is_a_true_left_right_flip_and_size_scales_with_dpi() -> None:
    spr = sprites.SpriteSet("feminine", DIR)
    plain, flipped = spr.frame("stand", 192), spr.frame("stand", 192, True)
    with Image.open(DIR / "feminine" / "stand.png") as drawn:
        drawn_size = drawn.size
    assert (plain.width, plain.height) == spr.size(192) == drawn_size
    a = Image.frombytes("RGBA", (plain.width, plain.height), plain.bgra, "raw", "BGRa")
    b = Image.frombytes("RGBA", (flipped.width, flipped.height), flipped.bgra, "raw", "BGRa")
    from PIL import ImageOps

    assert list(ImageOps.mirror(a).getchannel("A").getdata()) == list(b.getchannel("A").getdata())
    assert spr.size(96)[0] * 2 - spr.size(192)[0] in (-1, 0, 1)
    assert len(plain.bgra) == plain.width * plain.height * 4


def test_frames_are_cached_per_name_dpi_and_flip() -> None:
    spr = sprites.SpriteSet("masculine", DIR)
    assert spr.frame("stand", 96) is spr.frame("stand", 96)
    assert spr.frame("stand", 96) is not spr.frame("stand", 96, True)
    assert spr.frame("stand", 96) is not spr.frame("stand", 144)
    with pytest.raises(KeyError):
        spr.frame("nope")


def test_look_names_and_missing_frames() -> None:
    assert sprites.look_for("Feminine") == "feminine"
    assert sprites.look_for("auto") == "masculine" and sprites.look_for(None) == "masculine"
    assert sprites.SpriteSet("masculine", DIR).missing() == []
    assert len(sprites.SpriteSet("masculine", DIR / "nowhere").missing()) == 16


def test_the_shipped_frames_are_loadable_with_the_default_directory() -> None:
    assert sprites.frames_dir().resolve() == DIR.resolve()
