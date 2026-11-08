"""INBOX 1607 b, c, d: the masculine Atlas against the feminine, measured from what renders.

Reads the cells and JSON that `atlasm1108.js` wrote (run it at SCALE=1 into D1 and SCALE=2 into D2) and the
shipped desk frames, prints the metrics the spec in docs/roadmap/agent-remaining/atlasm-1108.md targets, and
writes one pose sheet (both looks, every mood, sit and walk, in-app 1x and 2x, desk 1x and 2x) as WebP.

    python scratchpad/ui-sweeps/atlasm1108.py D1 D2 OUT.webp

Metrics, per look:
- head : head skin height over the drawn figure's height; head width over the torso's width at body y 40
  (the shoulders), both in the rig's own units after the head's 0.76 (`--atl-head-k`) and the look's scale.
- eyes : one sclera's width over the head's width, the inner gap over one eye's width, sclera area over
  head area, brow opacity and stroke.
- framing : the share of the head's outline below the brows that borders background, not hair (sampled in
  the page, 1.2 units outside the outline).
- seam : where an arm's outline lies inside the torso (1.2 css px or more from its edge), the luminance step
  across it (mean, device px 1.2 either side) and the count of points that read as a line (step 12 or more,
  or a ridge of 8 or more over both sides).
- moods : mean |luminance change| from calm inside the face (brows to chin, aligned on the head), per mood.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image

LOOKS = ("masculine", "feminine")
CELLS = (
    "stand-calm", "stand-happy", "stand-delighted", "stand-laughing", "stand-thinking", "stand-curious",
    "stand-surprised", "stand-confused", "stand-sleepy", "stand-sad", "stand-proud", "stand-shy",
    "stand-determined", "stand-love", "stand-worried", "sit-calm", "walk-calm",
)
DESK = ("stand", "look", "blink", "walk0", "walk6", "sit", "sleep", "wave", "hang")
CLIP = (180, 100)  # the sweep's screenshot clip origin, css px


def _inside(poly, x, y):
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i - 1], poly[i]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def seam(m, im, scale):
    def px(x, y):
        return im.getpixel((min(im.width - 1, max(0, round((x - CLIP[0]) * scale))), min(im.height - 1, max(0, round((y - CLIP[1]) * scale)))))

    torso, out = m["torsoOutline"], []
    for arm in m["armOutlines"]:
        steps = []
        for i in range(1, len(arm) - 1):
            x, y = arm[i]
            if not _inside(torso, x, y) or min(math.hypot(x - a, y - b) for a, b in torso) < 1.2:
                continue
            tx, ty = arm[i + 1][0] - arm[i - 1][0], arm[i + 1][1] - arm[i - 1][1]
            n = math.hypot(tx, ty) or 1
            h = 1.2 / scale
            a, b, c = px(x - ty / n * h, y + tx / n * h), px(x + ty / n * h, y - tx / n * h), px(x, y)
            steps.append((abs(a - b), c - (a + b) / 2))
        line = [s for s in steps if s[0] >= 12 or abs(s[1]) >= 8]
        out.append((round(sum(s[0] for s in steps) / max(1, len(steps)), 1), len(line), len(steps)))
    return out


def face_box(rect, scale):
    x, y, w, h = rect
    return tuple(round(v) for v in ((x - CLIP[0]) * scale, (y - CLIP[1] + h * 0.3) * scale, (x - CLIP[0] + w) * scale, (y - CLIP[1] + h) * scale))


def moods(d, cells, scale, look):
    v = d[look]
    rect = lambda n: v[n]["head"] if isinstance(v[n], dict) else v[n]  # noqa: E731
    base = Image.open(cells / look / "stand-calm.png").convert("L").crop(face_box(rect("stand-calm"), scale))
    res = {}
    for n in CELLS[1:15]:
        im = Image.open(cells / look / f"{n}.png").convert("L").crop(face_box(rect(n), scale)).resize(base.size)
        a, b = base.tobytes(), im.tobytes()
        res[n[6:]] = sum(abs(p - q) for p, q in zip(a, b)) / len(a)
    return res


def report(d, cells, scale):
    print(f"--- in-app {scale}x")
    md = {look: moods(d, cells, scale, look) for look in LOOKS}
    for look in LOOKS:
        m = d[look]["stand-calm"]
        hx, hy, hw, hh = m["head"]
        rows = dict(m["torsoRows"])
        shoulder = rows.get(40.0)
        body_px = m["torso"][2] / max(rows.values())  # css px per body unit
        (sx, _, sw, sh), (sx2, *_ ) = m["scl"][0], m["scl"][1]
        st = m["styles"]
        print(f"{look}: head h/fig h {hh / m['fig'][3]:.3f}; head w/shoulders {hw / (shoulder * body_px):.2f} (shoulders {shoulder} units)")
        print(f"  eye w/head w {sw / hw:.3f}; inner gap/eye w {(sx2 - sx - sw) / sw:.3f}; sclera area/head {2 * sw * sh / (hw * hh):.3f}; eye {sw:.2f}x{sh:.2f} css px")
        print(f"  brow op {st['brow']['op']} sw {st['brow']['sw']}; lash sw {st['lash']['sw']}; lashes {'yes' if st['lashes'] else 'no'}; hairline y {m['hairline']}")
        print(f"  framing: bare outline below brows {m['framing']['bareBelowBrow']:.3f} (all {m['framing']['bareAll']:.3f})")
        for cell in ("stand-calm", "sit-calm"):
            im = Image.open(cells / look / f"{cell}.png").convert("L")
            print(f"  seam {cell}: " + "; ".join(f"arm{i} step {a} line {b}/{c}" for i, (a, b, c) in enumerate(seam(d[look][cell], im, scale))))
        r = md[look]
        print(f"  moods mean {sum(r.values()) / len(r):.1f}; weakest " + ", ".join(f"{n} {x:.1f}" for n, x in sorted(r.items(), key=lambda t: t[1])[:4]))


def desk(root):
    print("--- desk (shipped 2x frames)")
    for look in LOOKS:
        im = Image.open(root / look / "stand.png").convert("RGBA")
        solid = im.split()[3].point(lambda a: 255 if a > 128 else 0).getbbox()
        print(f"{look}: stand solid box {solid} ({solid[2] - solid[0]}x{solid[3] - solid[1]})")


def sheet(d1, d2, root, out):
    rows = []
    for cells, scale in ((d1, 1), (d2, 2)):
        for look in LOOKS:
            crop = (0, 25 * scale, 112 * scale, 150 * scale)
            rows.append([Image.open(cells / look / f"{n}.png").convert("RGB").crop(crop) for n in CELLS])
    for scale in (1, 2):
        for look in LOOKS:
            ims = [Image.open(root / look / f"{n}.png").convert("RGBA") for n in DESK]
            if scale == 1:
                ims = [i.resize((i.width // 2, i.height // 2), Image.LANCZOS) for i in ims]
            tiles = []
            for i in ims:
                bg = Image.new("RGB", i.size, (27, 29, 42))
                bg.paste(i, mask=i.split()[3])
                tiles.append(bg)
            rows.append(tiles)
    width = max(sum(t.width for t in r) for r in rows)
    sheet = Image.new("RGB", (width, sum(max(t.height for t in r) for r in rows)), (27, 29, 42))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width
        y += max(t.height for t in r)
    sheet.save(out, "WEBP", quality=62, method=6)
    print(f"sheet {out} {sheet.size} {Path(out).stat().st_size} bytes")


def main():
    d1, d2, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    for cells, scale in ((d1, 1), (d2, 2)):
        report(json.loads((cells / f"measure-{scale}x.json").read_text()), cells, scale)
    root = Path(__file__).resolve().parents[2] / "frontend" / "img" / "desk"
    desk(root)
    sheet(d1, d2, root, out)


if __name__ == "__main__":
    main()
