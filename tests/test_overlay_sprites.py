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
    # Intent moved (INBOX 1670, "very framey"): 12 walk and 24 idle frames, in-betweens of the old 6 and 12.
    # Intent moved (INBOX 1696 x): six wave frames (wave0..wave5), 50 to 56.
    # Intent moved (W31 E1, E2): five pictures of acts the desk lacked (`sprites.EXTRA_FRAMES`), 56 to 61.
    # Intent moved (L-ui-modernisation-10): the sleeping hang and the flip by the feet, 61 to 63.
    assert len(sprites.FRAME_NAMES) == 63 and len(sprites.WALK_FRAMES) == 12 and len(sprites.IDLE_FRAMES) == 24


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
    # an older, shorter set (6 walk, 12 idle) still runs, so those extras are not required
    # Intent moved (INBOX 1696 x): the six wave frames are optional too (`missing()` leaves them out).
    older = (sprites.WALK_COUNT - sprites.OLD_WALK_COUNT) + (sprites.IDLE_COUNT - sprites.OLD_IDLE_COUNT) + sprites.WAVE_COUNT
    # Intent moved (W31 E1, E2): the five extra pictures are optional as well.
    older += len(sprites.EXTRA_FRAMES)
    assert len(sprites.SpriteSet("masculine", DIR / "nowhere").missing()) == len(sprites.FRAME_NAMES) - older


def test_a_shorter_shipped_set_runs_with_its_own_counts(tmp_path) -> None:
    import shutil

    spr = sprites.SpriteSet("masculine", DIR)
    assert spr.walk_count() == 12 and spr.idle_count() == 24
    keep = tmp_path / "masculine"
    keep.mkdir()
    for n in spr.available():
        if n not in (*sprites.WALK_FRAMES[6:], *sprites.IDLE_FRAMES[12:]):
            shutil.copy(DIR / "masculine" / f"{n}.png", keep / f"{n}.png")
    old = sprites.SpriteSet("masculine", tmp_path)
    assert old.missing() == [] and old.walk_count() == 6 and old.idle_count() == 12


def test_the_shipped_frames_are_loadable_with_the_default_directory() -> None:
    assert sprites.frames_dir().resolve() == DIR.resolve()


def test_spin_frames_are_rotated_copies_on_a_canvas_that_fits_any_angle_cached_once() -> None:
    import math

    spr = sprites.SpriteSet("masculine", DIR)
    assert spr.gait == "float"
    w, h = spr.size(96)
    side = math.ceil(math.hypot(w, h))
    a, b = spr.frame("spin0", 96), spr.frame("spin3", 96)
    assert (a.width, a.height) == (side, side) == (b.width, b.height)
    assert (a.pad_x, a.pad_y) == ((side - w) // 2, (side - h) // 2)
    assert a.bgra != b.bgra and len(a.bgra) == side * side * 4
    assert spr.frame("spin3", 96) is b  # built once, not per frame
    assert spr.frame("spin3", 96, flip=True) is not b
    # the halo guard still holds on a rotated frame
    alphas = set(a.bgra[3::4])
    assert not any(0 < v < sprites.ALPHA_FLOOR for v in alphas)
    assert spr.missing() == []  # spin frames are made, not shipped files


def test_clipping_clears_the_hidden_rows_and_columns_and_leaves_the_rest() -> None:
    f = sprites.Frame(4, 4, bytes([255] * 64))
    rows = sprites.clipped(f, (0, 0, 4, 2))
    assert rows.bgra[: 2 * 16] == bytes([255] * 32) and set(rows.bgra[32:]) == {0}
    cols = sprites.clipped(f, (1, 0, 3, 4))
    assert all(cols.bgra[(r * 4 + c) * 4] == (255 if 1 <= c < 3 else 0) for r in range(4) for c in range(4))
    assert set(sprites.clipped(f, (0, 0, 4, 0)).bgra) == {0}
    assert sprites.clipped(f, None) is f and sprites.clipped(f, (0, 0, 4, 4)) is f


def test_the_nebula_stream_is_in_every_frame_soft_but_visible() -> None:
    """INBOX 1660 ("the desktop companion is also missing the nebular stream"): the stream is the
    translucent part of a frame (alpha above the click guard's floor and below solid). It is
    there in every frame, and its pixels are at least 35 percent opaque on average."""
    for look in sprites.LOOKS:
        for name in sprites.FRAME_NAMES:
            alpha = Image.open(DIR / look / f"{name}.png").convert("RGBA").getchannel("A")
            soft = [a for a in alpha.getdata() if sprites.ALPHA_FLOOR <= a < 250]
            assert len(soft) >= 1500, (look, name, len(soft))
            assert sum(soft) / len(soft) >= 0.35 * 255, (look, name, sum(soft) / len(soft))


def test_no_shipped_frame_is_cut_by_its_own_edge() -> None:
    """INBOX 1663: the feminine hang, hop, land, tumble and idle frames were captured through a
    clip narrower than the figure and shipped with a straight edge (half an Atlas)."""
    for look in sprites.LOOKS:
        for name in sprites.FRAME_NAMES:
            im = Image.open(DIR / look / f"{name}.png").convert("RGBA")
            box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
            assert box is not None
            assert box[0] > 0 and box[2] < im.width and box[3] < im.height, (look, name, box, im.size)


def test_every_frame_and_spin_frame_draws_inside_its_bitmap_at_every_dpi() -> None:
    for look in sprites.LOOKS:
        spr = sprites.SpriteSet(look)
        for dpi in (96, 120, 144, 192):
            for flip in (False, True):
                for name in (*sprites.FRAME_NAMES, *sprites.SPIN_FRAMES):
                    f = spr.frame(name, dpi, flip)
                    left, top, right, bottom = f.box
                    assert 0 < left and 0 < top and right < f.width and bottom < f.height, (look, dpi, flip, name, f.box, (f.width, f.height))
                    # The recorded box is the real one: the first and last drawn rows are inside it.
                    a = Image.frombytes("RGBA", (f.width, f.height), f.bgra, "raw", "BGRA").getchannel("A")
                    assert a.point(lambda v: 255 if v else 0).getbbox() == f.box, (look, dpi, flip, name)
