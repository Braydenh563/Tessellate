"""Render the desktop companion's overlay frames (BACKLOG 16, O2).

    PYTHONPATH=src BASE=http://127.0.0.1:8828 .venv/bin/python scripts/render_desk_frames.py

`DESK_ADD=1` captures only the optional extra frames (`DESK_ADD=a,b`: only those named) and adds them to the shipped set, registered to its canvas.

Boots nothing itself: `BASE` is a running app (`bash scratchpad/ui-sweeps/serve.sh
8828 <dir>`). `scripts/render_desk_frames.js` captures every frame of Atlas, both
looks, with a transparent background at device scale 2; this script zeroes the
faint alpha (the halo guard `sprites.py` also applies) and stretches the rest so the figure is solid (`solidify`), crops every frame of a
look to the same box (so they stay registered), and writes
`frontend/img/desk/<look>/<frame>.png`. Needs Pillow (the `desktop` extra).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from tessellate.core.overlay import sprites  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import render_card_frames  # noqa: E402

PAD = 4
#: Fewer colours with their alpha kept: a quarter of the bytes for frames that are soft gradients.
COLOURS = 256
#: The figure's glass, glow and wisp fades come out of the capture as soft
#: translucent washes that read as a pale ghost over a wallpaper. Alpha is
#: stretched so what is at least `SOLID_HI` is fully opaque and what is under
#: `SOLID_LO` is clear, with a short ramp between: a solid body with a soft edge.
SOLID_LO = 24
SOLID_HI = 120


def solidify(a: int) -> int:
    if a <= SOLID_LO:
        return 0
    return min(255, (a - SOLID_LO) * 255 // (SOLID_HI - SOLID_LO))


#: The nebula stream (INBOX 1660): `render_desk_frames.js` captures each frame twice, without
#: (`<name>.png`) and with (`<name>.neb.png`) the app's nebula washes. What the second adds
#: to the first is the stream; it is kept as its own soft layer under the solid body, at
#: `STREAM_SOFT` of its alpha (a pale veil, not a second body), and anything fainter than
#: `STREAM_LO` is dropped (the click guard would clear it anyway).
STREAM_LO = 10
STREAM_SOFT = 0.85


def stream_of(body: Image.Image, neb: Image.Image) -> Image.Image:
    """The alpha the `neb` capture adds to `body`: the nebula stream, soft, with the faint dropped."""
    extra = ImageChops.subtract(neb.getchannel("A"), body.getchannel("A"))
    return extra.point(lambda a: 0 if a < STREAM_LO else min(255, round(a * STREAM_SOFT)))


def with_stream(body: Image.Image, neb: Image.Image, stream: tuple[Image.Image, Image.Image] | None = None) -> Image.Image:
    """`body` (the capture without the nebula) solidified, with the stream the `neb`
    capture adds under it. Both are RGBA captures of the same frame. `stream` is a shared
    (colours, alpha) pair to use instead of this frame's own: the idle and drift frames all
    take one, so the stream cannot step from frame to frame (INBOX 1670: "the nebular flow
    keeps blinking in and out", the stream's mass varied up to 3x between captures)."""
    veil, extra = (neb.copy(), stream_of(body, neb)) if stream is None else (stream[0].copy(), stream[1])
    veil.putalpha(extra)
    solid = body.copy()
    solid.putalpha(body.getchannel("A").point(solidify))
    return Image.alpha_composite(veil, solid)


def shared_stream(captured: dict[str, Image.Image], nebs: dict[str, Image.Image], names: list[str]) -> tuple[Image.Image, Image.Image]:
    """The stream of the stand: the one every frame of the set then shows. (It was the median-mass one of the
    set, a different capture each run, so the figure's right edge and the ring's lowest row moved 8 to 17 px
    between renders and the tests that bound the cycle's edges passed or failed by the run.)"""
    pick = "stand" if "stand" in names else names[0]
    return nebs[pick], stream_of(captured[pick], nebs[pick])


#: Frames that stand or drift in place, each showing the same stream.
STREAM_SHARED = tuple(sprites.IDLE_FRAMES) + tuple(sprites.WALK_FRAMES) + tuple(sprites.WAVE_FRAMES) + ("stand", "blink", "look", "wave", "held")


def touches_edge(im: Image.Image) -> bool:
    """True when a drawn pixel (alpha at the floor or more) is on the image's left, right or bottom edge."""
    box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
    if not box:
        return False
    return box[0] <= 0 or box[2] >= im.width or box[3] >= im.height


def crop_box(images: list[Image.Image], stand: Image.Image | None = None) -> tuple[int, int, int, int]:
    """The union of every frame's drawn pixels plus PAD, widened on its narrower side so the stand sits in the
    middle of the canvas: a mirrored figure then lands where it stood (the engine's `_flip_dx` is 0) and never
    hangs a few px off a screen edge (INBOX 1696 hh, the 1107 handle flip: the stand was 8 to 17 px off centre)."""
    left = top = 10**9
    right = bottom = 0
    for im in images:
        box = im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()
        if box:
            left, top = min(left, box[0]), min(top, box[1])
            right, bottom = max(right, box[2]), max(bottom, box[3])
    width, height = images[0].size
    left, right = left - PAD, right + PAD
    sb = stand.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox() if stand is not None else None
    if sb:
        mid = (sb[0] + sb[2]) / 2
        half = max(mid - left, right - mid) + 1  # one px more on the right: the shift is never positive
        left, right = int(mid - half), int(mid + half + 1)
    return max(0, left), max(0, top - PAD), min(width, right), min(height, bottom + PAD)


def clip_idle_tails(folder: Path) -> None:
    """Clip the stand, its blink and look and every idle picture to the same lowest row: that of the highest of them (the tail tip's
    last two or three near-transparent rows). The engine registers the cycle to one rest line and its tests
    bound a step of the drawn feet line; a tip that dipped 1 to 3 rows lower in some phases was a bob of the
    window's feet at every wrap (INBOX 1670, 16:40Z: the feminine idle bottom stepped 258 to 261 and the figure
    seemed to jitter), and pinning the tail left masculine's idle 2 rows above its stand. A person cannot see it."""
    def bottom(im: Image.Image) -> int:
        return im.getchannel("A").point(lambda v: 255 if v >= sprites.ALPHA_FLOOR else 0).getbbox()[3]

    paths = [folder / f"{n}.png" for n in ("stand", "blink", "look")] + sorted(folder.glob("idle*.png"))
    limit = min(bottom(Image.open(p).convert("RGBA")) for p in paths)
    for path in paths:
        im = Image.open(path).convert("RGBA")
        if bottom(im) <= limit:
            continue
        im.paste((0, 0, 0, 0), (0, limit, im.width, im.height))
        im.quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(path, optimize=True)


def drawn(im: Image.Image) -> tuple[int, int, int, int]:
    return im.getchannel("A").point(lambda a: 255 if a >= sprites.ALPHA_FLOOR else 0).getbbox()


def solid_box(im: Image.Image) -> tuple[int, int, int, int]:
    """The box of the fully opaque pixels: the body, not the nebula stream (which is at most 85 percent and differs by run)."""
    return im.getchannel("A").point(lambda a: 255 if a >= 230 else 0).getbbox()


def best_offset(captured: Image.Image, shipped: Image.Image, ox: int, oy: int, reach: int = 5) -> tuple[int, int]:
    """The crop offset near (`ox`, `oy`) that lays the capture's opaque body over the shipped stand's with the fewest pixels
    differing: the two renders' boxes agree to a few px only (the stream's mass and the tail's tip vary), the body does not."""
    def mask(im: Image.Image) -> Image.Image:
        return im.getchannel("A").point(lambda a: 255 if a >= 230 else 0)

    want, have = mask(shipped), mask(captured)
    best = (10**9, ox, oy)
    for dy in range(oy - reach, oy + reach + 1):
        for dx in range(ox - reach, ox + reach + 1):
            cut = have.crop((dx, dy, dx + want.width, dy + want.height))
            miss = sum(ImageChops.difference(cut, want).point(lambda a: 1 if a else 0).histogram()[1:])
            best = min(best, (miss, dx, dy))
    print(f"registration: offset ({best[1]}, {best[2]}), {best[0]} px differ; start ({ox}, {oy})")
    return best[1], best[2]


#: The hang frames drawn from a capture, not patched into the shipped hang: which of the hang's hands each one holds the edge with.
HANG_HELD = {"hang_sloth": "left", "hang_feet": "both"}


def grip_x(im: Image.Image, side: str) -> float:
    """The mean column of the opaque pixels in the topmost rows of a hang frame (the hands at the edge): `left` takes the left half only."""
    solid = im.getchannel("A").point(lambda a: 255 if a >= 230 else 0)
    top = solid.getbbox()[1]
    rows = solid.crop((0, top, solid.width, top + 8))
    cols = [x for x in range(rows.width) for y in range(rows.height) if rows.getpixel((x, y))]
    if side == "left":
        cols = [x for x in cols if x <= min(cols) + (max(cols) - min(cols)) // 2]
    return sum(cols) / len(cols)


def hung_from_the_edge(im: Image.Image, hang: Image.Image, side: str) -> Image.Image:
    """`im` moved so its grip is where the shipped hang's is: the same top row (the engine places a hang by it) and the same column
    (a hang is drawn about the grip, so a swap between two hang pictures does not jump)."""
    dy = drawn(hang)[1] - drawn(im)[1]
    dx = round(grip_x(hang, "left" if side == "left" else "both") - grip_x(im, side))
    moved = Image.new("RGBA", im.size)
    moved.paste(im, (dx, dy))
    return moved


def added_names() -> tuple[str, ...]:
    """The extra frames `DESK_ADD` names (`1`: all of `sprites.EXTRA_FRAMES`), so a new frame leaves the shipped ones' bytes alone."""
    want = os.environ.get("DESK_ADD", "")
    return tuple(n for n in sprites.EXTRA_FRAMES if want == "1" or n in want.split(","))


def add_extras(raw: str) -> int:
    """`DESK_ADD=1`: capture only `sprites.EXTRA_FRAMES` (and the stand and the hang, to register them) and write them beside
    the shipped frames, cropped to the SAME canvas as the shipped `stand` (found by matching the stand's opaque body), so
    no shipped picture changes. A frame whose drawn pixels reach that canvas's edge is refused: it would be cut.
    `hang_one` is the shipped `hang` with only what differs from a fresh capture of the hang (the let-go arm) patched in:
    the rig draws the hem a few px longer than it did when `hang` was shipped, and a hang that changed its hem as one hand
    let go would pop."""
    out = ROOT / "frontend" / "img" / "desk"
    for look in sprites.LOOKS:
        names = ["stand", "hang", *added_names()]
        captured = {n: Image.open(Path(raw) / look / f"{n}.png").convert("RGBA") for n in names}
        nebs = {n: Image.open(Path(raw) / look / f"{n}.neb.png").convert("RGBA") for n in names}
        shipped = Image.open(out / look / "stand.png").convert("RGBA")
        sb, hb = solid_box(with_stream(captured["stand"], nebs["stand"])), solid_box(shipped)
        ox, oy = best_offset(with_stream(captured["stand"], nebs["stand"]), shipped, sb[0] - hb[0], sb[1] - hb[1])
        box = (ox, oy, ox + shipped.width, oy + shipped.height)
        for n in added_names():
            if touches_edge(captured[n]):
                raise SystemExit(f"{look}/{n}: the capture touches the clip edge; widen BOX in render_desk_frames.js")
            im = with_stream(captured[n], nebs[n]).crop(box)
            if n == "hang_one":
                im = patched_hang(look, captured, nebs, out)
            if n in HANG_HELD:
                im = hung_from_the_edge(im, Image.open(out / look / "hang.png").convert("RGBA"), HANG_HELD[n])
            d = drawn(im)
            if d[0] <= 0 or d[1] <= 0 or d[2] >= im.width or d[3] >= im.height:
                raise SystemExit(f"{look}/{n}: drawn pixels {d} reach the shipped canvas {im.size}; the frame would be cut")
            im.quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(out / look / f"{n}.png", optimize=True)
            print(f"{look}/{n}: drawn {d} in {im.size}, {(out / look / f'{n}.png').stat().st_size} bytes")
    return 0


def patched_hang(look: str, captured: dict[str, Image.Image], nebs: dict[str, Image.Image], out: Path) -> Image.Image:
    """The shipped hang with the let-go arm of a fresh capture pasted over the box where the fresh hang and hang_one differ."""
    shipped = Image.open(out / look / "hang.png").convert("RGBA")
    fresh, one = with_stream(captured["hang"], nebs["hang"]), with_stream(captured["hang_one"], nebs["hang_one"])
    sb, hb = solid_box(fresh), solid_box(shipped)
    ox, oy = best_offset(fresh, shipped, sb[0] - hb[0], sb[1] - hb[1], reach=10)
    #: Only the upper part of the figure: the arms. The hem below differs a little between two captures (it sways).
    arms = (0, 0, fresh.width, sb[1] + int(0.55 * (sb[3] - sb[1])))
    changed = ImageChops.difference(fresh, one).convert("L").point(lambda v: 255 if v > 24 else 0).crop(arms).getbbox()
    if changed is None:
        raise SystemExit(f"{look}: hang_one is the same picture as hang")
    print(f"{look}: hang_one differs from the hang in {changed}")
    left, top, right, bottom = max(0, changed[0] - 6), max(0, changed[1] - 6), changed[2] + 6, changed[3] + 6
    result = shipped.copy()
    result.paste(one.crop((left, top, right, bottom)), (left - ox, top - oy))
    return result


def main() -> int:
    out = ROOT / "frontend" / "img" / "desk"
    with tempfile.TemporaryDirectory() as raw:
        env = {**os.environ, "BASE": os.environ.get("BASE", "http://127.0.0.1:8828"), "SCRATCH": raw}
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        if os.environ.get("DESK_ADD"):
            env["ONLY"] = ",".join(["stand", "hang", *added_names()])
        if not os.environ.get("DESK_RAW"):  # DESK_RAW: reuse the captures of an earlier run (a folder of <look>/<frame>.png and .neb.png)
            subprocess.run(["node", str(ROOT / "scripts" / "render_desk_frames.js"), raw], check=True, env=env, cwd=ROOT)
        raw = os.environ.get("DESK_RAW") or raw
        if os.environ.get("DESK_ADD"):
            return add_extras(raw)
        total = 0
        for look in sprites.LOOKS:
            captured = {name: Image.open(Path(raw) / look / f"{name}.png").convert("RGBA") for name in sprites.FRAME_NAMES if name not in sprites.CARD_FRAMES}
            nebs = {name: Image.open(Path(raw) / look / f"{name}.neb.png").convert("RGBA") for name in captured}
            shared = shared_stream(captured, nebs, [n for n in STREAM_SHARED if n in captured])
            images = {name: with_stream(im, nebs[name], shared if name in STREAM_SHARED else None) for name, im in captured.items()}
            #: A capture can come out blank (seen once on a cold page: eight idle frames
            #: of one look): refuse to ship it rather than a figure that vanishes.
            blank = [n for n, im in captured.items() if sum(im.getchannel("A").histogram()[128:]) < 1000]
            if blank:
                raise SystemExit(f"{look}: blank captures {blank}; run it again")
            #: A capture whose drawn pixels reach the clip's edge was cut by the clip (INBOX
            #: 1663: half an Atlas shipped): widen `BOX` in the script, never crop around it.
            cut = [n for n, im in captured.items() if touches_edge(im)]
            if cut:
                raise SystemExit(f"{look}: captures {cut} touch the clip edge; widen BOX in render_desk_frames.js")
            box = crop_box(list(images.values()), images.get("stand"))
            target = out / look
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            for name, im in images.items():
                im = im.crop(box)
                small = im.quantize(colors=COLOURS, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
                small.save(target / f"{name}.png", optimize=True)
                total += (target / f"{name}.png").stat().st_size
            clip_idle_tails(target)
            render_card_frames.render_look(look)
            print(f"{look}: {len(images)} frames, {box[2] - box[0]}x{box[3] - box[1]} px")
        print(f"total {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
