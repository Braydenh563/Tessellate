"""A falling companion does not stutter (INBOX 1696 a, owner: "when the desktop companion is falling, it stops and
glitches at like 8 frames per second or smth as it is falling in the downward arc"). Measured on FakeWin32 with the
owner's screen (one 2560x1504 monitor at dpi 192, frames 263x299 px): before, every tick of a spinning fall built a
new picture at a quarter degree, 6.4 ms median and 10.9 max of Pillow (4.7 ms the rotate alone, about ten GIL
hand-backs), 22 to 60 builds a second. Now the quarter turn is rotated once per size on a worker (`warm_spins`) and
every angle is that picture transposed into place: no rotate on the fall path, 0.3 ms median. Fixed clock."""

from __future__ import annotations

import math
import time

import pytest

pytest.importorskip("PIL")

from tessellate.core.overlay import sprites  # noqa: E402
from tests._overlay_fake import FakeWin32  # noqa: E402
from tests.test_overlay_runner import FRAMES, make, wait_for  # noqa: E402

STEP = 1.0 / 60.0


def reference(s: sprites.SpriteSet, deg: int, dpi: int, flip: bool) -> bytes:
    """The picture as it was built before: the (mirrored) tumble pasted on the spin canvas and rotated."""
    from PIL import Image

    base = s.frame("spin0", dpi, flip)
    canvas = Image.new("RGBA", (base.width, base.height), (0, 0, 0, 0))
    canvas.paste(s._pose_image(sprites.SPIN_BASE, dpi, flip), (base.pad_x, base.pad_y))
    turned = sprites.clear_faint_alpha(canvas.rotate(-deg, resample=Image.Resampling.BILINEAR))
    return sprites.premultiplied_bgra(turned)


@pytest.mark.parametrize("look", ["masculine", "feminine"])
@pytest.mark.parametrize("flip", [False, True])
def test_every_quarter_and_the_mirror_are_the_one_quarter_transposed(look: str, flip: bool) -> None:
    s = sprites.SpriteSet(look, FRAMES)
    for deg in (0, 17, 89, 90, 133, 200, 271, 359):
        got = s.spun_at(math.radians(deg), 96, flip)
        want = reference(s, deg, 96, flip)
        assert len(got.bgra) == len(want)
        # the same picture to within a pixel's resampling (an odd side mirrors half a pixel off): mean byte error
        # measured 0.06 to 1.1 of 255 on the mirror, 0 on the unmirrored quarter
        assert sum(abs(a - b) for a, b in zip(got.bgra, want)) / len(want) < 1.5, deg
    assert s.rotations <= sprites.SPIN_QUARTER  # only the quarter is ever rotated


def test_keep_only_drops_the_quarter_of_another_size_and_a_stale_warm_stops() -> None:
    s = sprites.SpriteSet("masculine", FRAMES)
    s.keep_only(96)
    assert s.warm_spins(96) == sprites.SPIN_QUARTER and s.spins_ready(96)
    assert s.warm_spins(96) == 0  # built once
    s.keep_only(120)
    assert not s._spin_bases.get(96)
    assert s.warm_spins(96) == 0  # a warm for a size no longer in use builds nothing


def _owner_runner():
    fake = FakeWin32()
    fake.monitor_list = [((0, 0, 2560, 1504), 192)]
    r, fake, clock, *_ = make(fake, reduced=False, look="feminine", home=(1200, 1400))
    assert r.start()
    r.show()
    assert wait_for(lambda: r.host.visible)
    r.paused = True  # the test drives the engine itself
    return r, clock


def _throw(r, clock, speed: float, angle: float) -> list[float]:
    """Pick the figure up, move the pointer at `speed` toward `angle` for six ticks, let go, and draw every tick of
    the flight through the runner. Returns the ms each new spin picture took."""
    e = r.engine
    e.big_ready = e.trip_ready = e.climb_ready = float("inf")
    w, h = e.size
    took: list[float] = []
    orig = r._new_picture

    def timed(out, key):
        t0 = time.perf_counter()
        more = orig(out, key)
        if out.angle is not None:
            took.append((time.perf_counter() - t0) * 1000.0)
        return more

    r._new_picture = timed

    def tick(cursor=None, event=None):
        out = e.update(clock.t, cursor, event) if cursor is not None else e.update(clock.t, event=event)
        r._apply(out)

    e.x, e.y = 1200.0, 300.0
    tick()
    sx, sy = int(e.x + w / 2), int(e.y + h / 2)
    tick((sx, sy), ("down", sx, sy))
    x, y = float(sx), float(sy)
    for _ in range(6):
        clock.t += STEP
        x, y = x + math.cos(angle) * speed * STEP, y + math.sin(angle) * speed * STEP
        tick(event=("move", round(x), round(y)))
    clock.t += STEP
    tick(event=("up", round(x), round(y)))
    for _ in range(60 * 6):
        clock.t += STEP
        tick()
        if e.state != "fly":
            break
    r._new_picture = orig
    return took


@pytest.mark.parametrize("speed,angle", [(1500.0, -0.6), (2500.0, -1.2)])
def test_a_spinning_fall_at_the_owners_size_rotates_nothing_on_the_overlay_thread(speed: float, angle: float) -> None:
    r, clock = _owner_runner()
    assert r.sprites.size(r._fdpi()) == (263, 299)
    assert r.sprites.spins_ready(192)  # warmed when the size settled (the test's hand-off runs at once)
    before = r.sprites.rotations
    took = _throw(r, clock, speed, angle)
    r.stop()
    assert len(took) > 60  # a new angle most ticks of the flight
    assert r.sprites.rotations == before  # every picture of the fall from the built quarter
    # measured here: 0.3 ms median, before 6.4 (a timing bound loose enough for a busy CI box)
    assert sorted(took)[len(took) // 2] < 3.0


def test_without_the_warm_each_step_is_built_once_and_hit_after() -> None:
    s = sprites.SpriteSet("feminine", FRAMES)
    s.keep_only(192)
    for i in range(400):  # four degrees a tick, past a full turn
        s.spun_at(math.radians(i * 4.0), 192, i % 2 == 0)
    first = s.rotations
    assert first <= sprites.SPIN_QUARTER
    for i in range(400):
        s.spun_at(math.radians(i * 4.0 + 1.0), 192, False)
    assert s.rotations <= sprites.SPIN_QUARTER  # cache hits after the first
