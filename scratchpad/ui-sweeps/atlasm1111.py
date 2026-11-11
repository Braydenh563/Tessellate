"""W31 E4 (INBOX 1607): the numbers from scratchpad/ui-sweeps/atlasm1111.js's OUT.

    python scratchpad/ui-sweeps/atlasm1111.py OUT            # prints the table as JSON
    python scratchpad/ui-sweeps/atlasm1111.py OUT sheet.png  # and a sheet of every cell

Head: the skin's width over its height, and the head as drawn (skin and hair cap) the same way.
Eyes: one white's width over the head's, the eyes' centre below the head's top over its height, the
inner gap over one eye, and in the juggle the iris's top below the white's upper edge (px at 1x).
Shoulder join, at each forced arm angle: within 5 units of each arm's root, (gap) ground pixels that a
1.5 unit closing of the paint would fill, i.e. notches and slits between arm and body, in 1x px; and
(seam) arm outline points inside the torso whose two sides differ by 12 or more in luminance.
Faces: the bust's face, every mood against every other, mean absolute grey difference; the least pair.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(sys.argv[1])
M = json.loads((OUT / "measure.json").read_text())
S = M["scale"]
C = M["clip"]


def _inside(poly, x, y):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def _disk(r):
    r = int(math.ceil(r))
    return [(dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if dx * dx + dy * dy <= r * r]


def _shift_any(mask, offs, op):
    out = mask.copy()
    h, w = mask.shape
    for dx, dy in offs:
        sh = np.zeros_like(mask) if op == "or" else np.ones_like(mask)
        ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
        xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
        sh[ys, xs] = mask[yd, xd]
        out = (out | sh) if op == "or" else (out & sh)
    return out


def head(rec):
    x, y, w, h = rec["head"]
    cx, cy, cw, ch = rec["cap"] or rec["head"]
    x0, y0, x1, y1 = min(x, cx), min(y, cy), max(x + w, cx + cw), max(y + h, cy + ch)
    return {"skin_wh": round(w / h, 3), "drawn_wh": round((x1 - x0) / (y1 - y0), 3)}


def eyes(rec):
    x, y, w, h = rec["head"]
    (a, b) = rec["eyes"][:2]
    sa, sb = a["sclera"], b["sclera"]
    left, right = sorted((sa, sb))
    ew = (sa[2] + sb[2]) / 2
    cy = (sa[1] + sa[3] / 2 + sb[1] + sb[3] / 2) / 2
    clear = min(e["irisTop"] - e["scleraTopAtIris"] for e in (a, b)) if a["scleraTopAtIris"] else None
    lid = min(e["irisTop"] - e["lidBottom"] for e in (a, b)) if a["lidBottom"] else None
    return {
        "eye_over_head": round(ew / w, 3),
        "eye_y": round((cy - y) / h, 3),
        "gap_over_eye": round((right[0] - left[0] - left[2]) / ew, 3),
        "iris_clear_px": clear and round(clear, 2),
        "iris_below_lid_px": lid and round(lid, 2),
    }


def alpha(look, name):
    k = np.asarray(Image.open(OUT / look / f"{name}.png").convert("RGB"), dtype=np.float32)
    w = np.asarray(Image.open(OUT / look / f"{name}-w.png").convert("RGB"), dtype=np.float32)
    a = 1 - (w - k).mean(axis=2) / 255
    return a, k.mean(axis=2)


def join(look, angle):
    rec = M[look]["angles"][str(angle)]
    a, lum = alpha(look, f"angle-{angle}")
    paint = a >= 0.5
    unit = rec["unit"] * S
    closed = _shift_any(_shift_any(paint, _disk(1.5 * unit), "or"), _disk(1.5 * unit), "and")
    yy, xx = np.mgrid[0 : a.shape[0], 0 : a.shape[1]]
    gaps, seams = [], []
    torso = rec["torsoOutline"]
    for (rx, ry), arm in zip(rec["roots"], rec["armOutlines"]):
        px, py = (rx - C["x"]) * S, (ry - C["y"]) * S
        near = (xx - px) ** 2 + (yy - py) ** 2 <= (5 * unit) ** 2
        gaps.append(round(float((closed & ~paint & near).sum()) / S / S, 2))
        line = 0
        for i in range(1, len(arm) - 1):
            x, y = arm[i]
            if not _inside(torso, x, y) or min(math.hypot(x - p, y - q) for p, q in torso) < 1.2 or math.hypot(x - rx, y - ry) > 6 * rec["unit"]:
                continue
            tx, ty = arm[i + 1][0] - arm[i - 1][0], arm[i + 1][1] - arm[i - 1][1]
            n = math.hypot(tx, ty) or 1
            h = 1.2 / S

            def at(u, v):
                return lum[min(lum.shape[0] - 1, max(0, round((v - C["y"]) * S))), min(lum.shape[1] - 1, max(0, round((u - C["x"]) * S)))]

            if abs(at(x - ty / n * h, y + tx / n * h) - at(x + ty / n * h, y - tx / n * h)) >= 12:
                line += 1
        seams.append(line)
    return {"gap_px": gaps, "seam_pts": seams}


def faces(look, px):
    rec = M[look]["faces"][str(px)]
    im = np.asarray(Image.open(OUT / look / f"faces-{px}.png").convert("L"), dtype=np.float32)
    crops = {}
    for mood, box in zip(rec["moods"], rec["boxes"]):
        x, y, w, h = box["head"]
        crops[mood] = im[round(y * 1 + h * 0.25) : round(y + h), round(x) : round(x + w)]
    hh = min(c.shape[0] for c in crops.values())
    ww = min(c.shape[1] for c in crops.values())
    crops = {k: v[:hh, :ww] for k, v in crops.items()}
    moods = list(crops)
    pairs = sorted((float(np.abs(crops[p] - crops[q]).mean()), p, q) for i, p in enumerate(moods) for q in moods[i + 1 :])
    calm = {m: round(float(np.abs(crops[m] - crops["calm"]).mean()), 1) for m in moods if m != "calm"}
    return {"least_pair": [round(pairs[0][0], 2), pairs[0][1], pairs[0][2]], "pairs_under_3": sum(p[0] < 3 for p in pairs), "from_calm_min": min(calm.items(), key=lambda kv: kv[1]), "from_calm_mean": round(sum(calm.values()) / len(calm), 2)}


def main():
    res = {}
    for look in ("masculine", "feminine"):
        L = M.get(look)
        if not L:
            continue
        r = res[look] = {}
        if L["poses"]:
            r["poses"] = {n: {**head(p), **eyes(p)} for n, p in L["poses"].items()}
        if L["angles"]:
            r["joins"] = {a: join(look, a) for a in L["angles"]}
        if L["faces"]:
            r["faces"] = {px: faces(look, px) for px in L["faces"]}
    print(json.dumps(res, indent=1))
    if len(sys.argv) > 2:
        rows = []
        for look in ("masculine", "feminine"):
            names = [f"pose-{n}" for n in M[look]["poses"]] + [f"angle-{a}" for a in M[look]["angles"]]
            cells = []
            for n in names:
                im = Image.open(OUT / look / f"{n}.png").convert("RGB")
                cells.append(im.resize((im.width * 160 // im.height, 160)))
            rows.append(cells)
        W = max(sum(c.width for c in row) for row in rows)
        sheet = Image.new("RGB", (W, 160 * len(rows)))
        for j, row in enumerate(rows):
            x = 0
            for c in row:
                sheet.paste(c, (x, j * 160))
                x += c.width
        sheet.save(sys.argv[2])


main()
