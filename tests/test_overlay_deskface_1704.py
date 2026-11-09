"""INBOX 1704 (the owner, 2026-11-09, four close-ups of the desk companion): eye expressions that look off, the astral flow
cut apart, two eyebrows, brows that never move, blinks and mouths that pop. Pixel checks on the real sprite code at 192 dpi
(nothing here ran on a Windows desktop):

- one brow per eye (a dark stroke above the eye box), none on a happy-arc eye, which is its own line;
- the brow moves with the look: up for surprise, down for sleepy, inner end up for sad, inner end down for miffed;
- a blink eases (half lid, shut, half lid), both eyes alike, and the lids rest open between blinks;
- a half lid covers a third of the iris at most (sleepy aside); the mouth keeps its corners and width across looks;
- the flow: no flat cut at the tail's lowest row (the render pinned it, `sprites.tapered`), the tail layer never leaves the
  canvas bottom, and a stretch never touches the canvas top.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from tessellate.core.overlay import behaviour as bh
from tessellate.core.overlay import faces
from tessellate.core.overlay import sprites as sp

LOOKS = ("feminine", "masculine")
DPI = 192
NOISE = 8  # px: fewer marks than this above an eye is a stray pixel of the art, not a stroke
#: Looks that draw no separate brow: the eye is a happy arc (the arc is the line).
ARCS = {k for k, v in faces.EXPRESSIONS.items() if v.arc} | {"blink"}  # (a blink is lids alone: no brow either)


@pytest.fixture(scope="module", params=LOOKS)
def spr(request: pytest.FixtureRequest) -> sp.SpriteSet:
    return sp.SpriteSet(request.param)


def _rgba(f: sp.Frame) -> np.ndarray:
    return np.frombuffer(f.bgra, dtype=np.uint8).reshape(f.height, f.width, 4).astype(int)


def _marks(spr: sp.SpriteSet, kind: str, level: int = 3, name: str = "stand") -> tuple[np.ndarray, tuple[float, float, float]]:
    """Dark pixels the face drew over the bare frame (True where ink was added), and the eye line `(x, y, px per shipped px)`."""
    base = spr.frame(name, DPI, False)
    cx, cy, k = faces.head_point(spr, name, base, False, None)
    drawn = faces.draw(spr, name, base, False, None, (kind, level), base)
    a, b = _rgba(base), _rgba(drawn)
    lum = b[..., :3].sum(-1) / 3.0
    return ((np.abs(a[..., :3] - b[..., :3]).sum(-1) > 60) & (lum < 165)), (cx, cy, k)


def _brow(spr: sp.SpriteSet, kind: str, side: int, level: int = 3) -> np.ndarray:
    """The ink above one eye's box, as (row, col) pixels."""
    m, (cx, cy, k) = _marks(spr, kind, level)
    ex = cx + side * faces.EYE_GAP * k
    top = int(cy - faces.EYE_RY * k - 1.5 * k)
    ys, xs = np.nonzero(m[max(0, int(cy - 30 * k)):top, int(ex - 9 * k):int(ex + 9 * k)])
    return np.stack([ys + max(0, int(cy - 30 * k)), xs + int(ex - 9 * k)], 1)


def _runs(col: np.ndarray) -> int:
    return int(((col[1:] & ~col[:-1]).sum()) + (1 if col[0] else 0))


@pytest.mark.parametrize("kind", sorted(faces.EXPRESSIONS))
def test_one_brow_per_eye_and_none_over_a_happy_arc(spr: sp.SpriteSet, kind: str) -> None:
    for side in (-1, 1):
        pts = _brow(spr, kind, side)
        if kind in ARCS:
            assert len(pts) < NOISE, (kind, side, "a brow over a happy arc reads as a second brow")
            continue
        assert len(pts) >= NOISE, (kind, side, "no brow drawn")
        m, (cx, cy, k) = _marks(spr, kind)
        ex = cx + side * faces.EYE_GAP * k
        top = int(cy - faces.EYE_RY * k - 1.5 * k)
        band = m[max(0, int(cy - 30 * k)):top, int(ex - 3 * k):int(ex + 3 * k) + 1]
        assert max(_runs(band[:, i]) for i in range(band.shape[1])) == 1, (kind, side)


def _centre(spr: sp.SpriteSet, kind: str, side: int = -1) -> float:
    return float(_brow(spr, kind, side)[:, 0].mean())


def test_the_brow_moves_with_the_look(spr: sp.SpriteSet) -> None:
    up = [_centre(spr, k) for k in ("surprised", "smile", "focus", "sleepy")]
    assert up == sorted(up), ("raised for surprise, lower through smile and focus, lowest asleep", up)
    assert up[-1] - up[0] >= 3.0, up  # px at 192 dpi: a visible travel, not a rounding


@pytest.mark.parametrize(("kind", "inner_higher"), [("sad", True), ("worried", True), ("miffed", False), ("focus", False)])
def test_brow_ends_tilt_with_the_feeling(spr: sp.SpriteSet, kind: str, inner_higher: bool) -> None:
    pts = _brow(spr, kind, -1)  # the figure's left eye
    mid = np.median(pts[:, 1])  # the left eye's inner end is toward the middle of the face: the greater column
    inner = pts[pts[:, 1] > mid][:, 0].mean()
    outer = pts[pts[:, 1] <= mid][:, 0].mean()
    assert (inner < outer) == inner_higher, (kind, inner, outer)


def test_curious_and_confused_raise_one_brow_more(spr: sp.SpriteSet) -> None:
    for kind in ("curious", "confused", "smirk"):
        assert abs(_centre(spr, kind, -1) - _centre(spr, kind, 1)) >= 2.0, kind


def _lid_row(spr: sp.SpriteSet, kind: str, level: int, side: int) -> float:
    """The row (px below the eye's top) of the lid line drawn on one eye: the mean row of the ink inside its box."""
    m, (cx, cy, k) = _marks(spr, kind, level)
    ex = cx + side * faces.EYE_GAP * k
    y0 = int(cy - faces.EYE_RY * k)
    box = m[y0:int(cy + faces.EYE_RY * k) + 1, int(ex - faces.EYE_RX * k):int(ex + faces.EYE_RX * k) + 1]
    ys, _xs = np.nonzero(box)
    assert len(ys) >= 3, (kind, level, side, "no lid drawn")
    return float(ys.mean())


def test_a_blink_eases_and_both_eyes_close_together(spr: sp.SpriteSet) -> None:
    rows = [[_lid_row(spr, "blink", lv, side) for side in (-1, 1)] for lv in (1, 2)]
    assert rows[0][0] < rows[1][0] and rows[0][1] < rows[1][1], rows  # the lid is further down at step 2
    for left, right in rows:
        assert abs(left - right) <= 1.5, rows  # the two lids sit on the same row (the art under each eye differs a little)
    assert faces.EXPRESSIONS["blink"].brows == 0  # a blink moves no brow


def test_half_lids_are_light_except_asleep() -> None:
    for kind, look in faces.EXPRESSIONS.items():
        cover = look.lid * 2 * faces.EYE_RY - (faces.EYE_RY - faces.IRIS_TOP)  # px of the iris the lid hides at full strength
        if kind in ("sleepy", "blink"):
            continue
        assert cover <= faces.IRIS_H / 3 + 1e-6, (kind, cover)


def test_the_mouth_keeps_its_corners_and_width(spr: sp.SpriteSet) -> None:
    spans = {}
    for kind in ("smile", "worried", "sad", "focus", "proud", "smirk", "confused"):
        m, (cx, cy, k) = _marks(spr, kind)
        y0, y1 = int(cy + (faces.MOUTH_DOWN - 5) * k), int(cy + (faces.MOUTH_DOWN + 8) * k)
        ys, xs = np.nonzero(m[y0:y1, int(cx - 8 * k):int(cx + 8 * k)])
        spans[kind] = (xs.max() - xs.min() + 1) / k, ((xs.max() + xs.min()) / 2 + int(cx - 8 * k) - cx) / k
    widths = [w for w, _c in spans.values()]
    assert max(widths) - min(widths) <= 3.0, spans  # shipped px
    assert all(abs(c) <= 1.5 for _w, c in spans.values()), spans


def _engine():
    from tests.test_overlay_engine import make

    e, _s = make(roam=False)
    return e


def test_the_engine_blinks_through_half_lids_and_never_pops() -> None:
    e = _engine()
    e.update(0.0)
    e.next_ambient = 1.0
    seen: list[tuple[str, tuple | None]] = []
    t = 0.0
    while t < 2.0:
        t += 0.004
        o = e.update(t)
        if e.flash and e.flash[0] == "blink":
            seen.append((o.frame, o.face))
    seq = [s for i, s in enumerate(seen) if i == 0 or s != seen[i - 1]]
    names = [(f, None if fc is None else fc[1]) for f, fc in seq]
    assert names[0][1] == 2 and names[-1][1] == 2, names  # in and out through a half lid
    assert ("blink", None) in names, names
    for a, b in zip(names, names[1:]):  # never open straight to shut, or shut straight to open
        assert not (a[0] != "blink" and a[1] is None and b[0] == "blink"), names
    e.next_ambient = math.inf
    assert e.update(t + 3.0).face is None  # the lids rest open between blinks


# --- the flow --------------------------------------------------------------------------------------------------


def _last_row_solid(f: sp.Frame) -> int:
    a = _rgba(f)[..., 3]
    rows = np.nonzero((a >= sp.ALPHA_FLOOR).any(1))[0]
    return int((a[rows.max()] >= 200).sum())


@pytest.mark.parametrize("dpi", [96, 192])
def test_no_frame_ends_in_a_flat_cut(spr: sp.SpriteSet, dpi: int) -> None:
    for name in spr.available():
        for flip in (False, True):
            assert _last_row_solid(spr.frame(name, dpi, flip)) < sp.CUT_WIDTH * dpi / 96, (name, dpi, flip)


def _extreme_tails() -> list[tuple[int, ...]]:
    big = round(bh.TAIL_LEN * bh.TAIL_REACH * bh.TAIL_Q)
    return [(big, big) * bh.TAIL_STEPS, (-big, big) * bh.TAIL_STEPS, (big, -big) * bh.TAIL_STEPS, (0, big) * bh.TAIL_STEPS]


@pytest.mark.parametrize("flip", [False, True])
def test_the_tail_layer_never_leaves_the_canvas_bottom_or_cuts_the_flow(spr: sp.SpriteSet, flip: bool) -> None:
    big = round(bh.FLOW_MAX * sp.FLOW_Q)
    for name in ("stand", "idle5", "sit"):
        for flow in (None, (big, big, big, 0, 0) * bh.FLOW_BANDS, (-big, -big, -big, 0, 0) * bh.FLOW_BANDS):
            body = spr.posed(name, DPI, flip, (1.0, 1.0, 0.0, 0.0), flow)
            for tail in _extreme_tails():
                f = spr.tailed(body, name, DPI, flip, tail)
                a = _rgba(f)[..., 3]
                assert a[-1].max() < sp.ALPHA_FLOOR, (name, flow is None, tail[:2])
                assert _last_row_solid(f) < sp.CUT_WIDTH * 2, (name, flip, tail[:2], "a flat edge ends the tail")


def test_the_flow_centre_line_has_no_gap(spr: sp.SpriteSet) -> None:
    """Down the middle of the lower body (the stream under the torso) every row of the drawn height keeps solid pixels,
    in the plain frame and under the flow and the tail layer: a cut would leave a row with none."""
    for name in ("stand", "idle3", "idle9"):
        plain = _rgba(spr.frame(name, DPI, False))[..., 3]
        w = plain.shape[1]
        cols = slice(int(w * 0.40), int(w * 0.62))
        rows = np.nonzero((plain[:, cols] >= 200).any(1))[0]
        lo, hi = rows.min() + int(0.55 * (rows.max() - rows.min())), rows.max() - 14
        fl, tl = bh.Flow(3), bh.TailLayer(3)
        t = 1.0
        for _ in range(12):
            t += 0.8
            tl.choose("stand", "happy", t)
            f = spr.tailed(spr.posed(name, DPI, False, (1.0, 1.0, 0.0, 0.0), fl.view(t, False, name, "stand", 1.0)), name, DPI, False, tl.view(t))
            a = _rgba(f)[..., 3][:, cols]
            gaps = [y for y in range(lo, hi) if not (a[y] >= 200).any()]
            assert not gaps, (name, t, gaps[:5])


@pytest.mark.parametrize("dpi", [96, 192])
def test_a_stretch_never_touches_the_canvas_top(spr: sp.SpriteSet, dpi: int) -> None:
    for name in spr.available():
        for flip in (False, True):
            for sy in (1.1, 1.16, 1.2):
                f = spr.posed(name, dpi, flip, (1.0, sy, 0.0, 0.0))
                assert _rgba(f)[0, :, 3].max() < sp.ALPHA_FLOOR, (name, dpi, flip, sy)
