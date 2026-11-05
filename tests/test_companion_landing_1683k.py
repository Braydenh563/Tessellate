"""How the in-app companion comes to rest after a throw (INBOX 1683 k, the same ask as the desk companion's): by outcome,
never a held tilt or a snap. The owner: "I want it to either land on its feet, land on its back or stomach and like skid
or smth or fall off ... can it flail?? ... if it is skidding down a surface can it scrabble for purchase??".

Seeded node runs of the pure flight (`companionThrowStep` over `nameMarkBuddyFlightStep`), 200 throws each, a fixed 16 ms
clock. Measured before this change: all 200 came to rest on the feet by an exponential turn, none on its back or belly,
none flailed."""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests.test_companion_throw_fates import AV, THROW, _fn

def landing_js(src: str) -> str:
    """The landing's functions and constants, for the older harnesses that run `nameMarkBuddyFlightStep` on its own."""
    consts = "\n".join(m.group(0) for m in re.finditer(r"^const COMPANION_THROW_(?:FEET|SINK|SLEW|FLAIL) = .*;$", src, re.M))
    return consts + "\n" + "\n".join(_fn(src, n) for n in ("companionThrowTurn", "companionThrowSlew", "companionThrowLie", "companionThrowLand"))


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const W = { left: 0, right: 1376, top: 48, floor: 780, ledges: [], w: 64, hang: 43, climb: 84 };
const wrap = (a) => (((a + 180) % 360) + 360) % 360 - 180;
function throwOne(seed) {
  const rand = companionThrowRng(seed * 7919 + 1);
  const vx = (rand() * 2 - 1) * 3.2, vy = (rand() * 2 - 1) * 3.2;
  const x = 100 + rand() * 1100, y = 150 + rand() * 500;
  const k = nameMarkBuddyThrowFeel([rand(), rand(), rand()], Math.hypot(vx, vy));
  k.ms = 2000;
  let s = { x, y, vx, vy, rot: 0, t: 0, on: null, rest: false, tried: {} };
  let rawSnaps = 0, shown = 0, steps = 0, tilt = 0, tiltMax = 0, snaps = 0, lie = "", flail = 0, scrabble = 0;
  while (!s.rest && steps < 400) {
    const was = s;
    s = companionThrowStep(s, 16, W, k, nameMarkBuddyFlightStep, rand);
    steps += 1;
    const d = Math.abs(wrap(s.rot - was.rot));
    if (d > 30 && !s.splat && !was.splat && !s.wrap && !was.wrap) rawSnaps += 1;
    const next = companionThrowSlew(shown, s.rot, 16);
    if (Math.abs(wrap(next - shown)) > 30) snaps += 1;
    shown = next;
    const pose = s.lying || s.splat || s.wrap || (s.fate && /hang|climb|grab|slip/.test(s.fate.kind));
    tilt = !pose && s.on && Math.abs(wrap(s.rot)) > 15 && d < 0.5 && !s.rest ? tilt + 16 : 0;
    tiltMax = Math.max(tiltMax, tilt);
    if (s.lie) lie = s.lie > 0 === (s.dir > 0) ? "belly" : "back";
    flail = Math.max(flail, Math.abs(s.flail || 0));
  }
  return { kind: lie || "feet", tilt: tiltMax, snaps, rawSnaps, flail: +flail.toFixed(1), fate: s.fate && s.fate.kind, rest: s.rest, steps };
}
function many(n) { const out = []; for (let i = 1; i <= n; i += 1) out.push(throwOne(i)); return out; }
"""


def run(body: str):
    consts = re.search(r"^const NMB_THROW = .*;$", AV, re.M).group(0)
    base = "\n".join(_fn(AV, n) for n in ("nameMarkBuddyFlightStep", "nameMarkBuddyThrowFeel"))
    pure = THROW[: THROW.index("//: The throw itself (moved here")]
    script = "\n".join([consts, base, pure, HARNESS, f"console.log(JSON.stringify({body}));"])
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def summary(rows: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    return {
        "kinds": kinds, "tilt_ms_max": max(r["tilt"] for r in rows), "snaps": sum(r["snaps"] for r in rows),
        "raw_snaps": sum(r["rawSnaps"] for r in rows),
        "flails": sum(1 for r in rows if r["flail"] > 5), "unrested": sum(1 for r in rows if not r["rest"]),
    }


@needs_node
def test_200_seeded_throws_land_by_outcome_with_no_snap_and_no_held_tilt() -> None:
    r = summary(run("many(200)"))
    # before: feet 200; 53 jumps over 30 degrees between two drawn frames (catches that set the lean to 0 in one step,
    # a head-down landing easing 18 percent a step)
    assert r["kinds"].get("back", 0) >= 15 and r["kinds"].get("belly", 0) >= 15 and r["kinds"].get("feet", 0) >= 60, r
    assert r["snaps"] == 0, r
    assert r["tilt_ms_max"] <= 100, r  # a tilt on the floor is turning every step, never held
    assert r["flails"] >= 3 and r["unrested"] == 0, r


@needs_node
def test_the_drawn_lean_never_turns_faster_than_a_tumble() -> None:
    out = run("[companionThrowSlew(0, 170, 16), companionThrowSlew(170, -170, 16), companionThrowSlew(10, 12, 16), companionThrowSlew(0, 90, 32)]")
    assert out[0] == pytest.approx(13.6) and out[1] == pytest.approx(170 + 13.6) and out[2] == 12 and out[3] == pytest.approx(27.2)


@needs_node
def test_a_landing_on_the_back_or_belly_rests_on_the_floor_and_gets_up() -> None:
    out = run(
        "(() => { const k = nameMarkBuddyThrowFeel([0.5, 0.5, 0.9], 1.0); k.ms = 2000;"
        " let s = { x: 600, y: 780, vx: 0, vy: 0, rot: 100, t: 0, on: 'floor', rest: false, tried: {} }; const seen = [];"
        " for (let i = 0; i < 200 && !s.rest; i += 1) { s = nameMarkBuddyFlightStep(s, 16, W, k); seen.push([s.rot, s.sink || 0, !!s.lying]); }"
        " return { seen, rest: s.rest, lie: s.lie }; })()"
    )
    assert out["lie"] == 90 and out["rest"]
    rots = [r for r, _sink, _l in out["seen"]]
    assert max(_sink for _r, _sink, _l in out["seen"]) == pytest.approx(14, abs=0.6)  # the body lies on the floor, not above it
    assert any(l for _r, _s, l in out["seen"])
    assert abs(rots[-1]) < 1.5  # and got up
    assert max(abs(b - a) for a, b in zip(rots, rots[1:])) < 30


def test_the_sink_is_half_the_height_less_half_the_width() -> None:
    w = int(re.search(r"^const NMB_W = (\d+);", AV, re.M).group(1))
    h = int(re.search(r"^const NMB_H = (\d+);", AV, re.M).group(1))
    assert (h - w) / 2 == float(re.search(r"^const COMPANION_THROW_SINK = ([\d.]+);", THROW, re.M).group(1))


if __name__ == "__main__":
    print(summary(run("many(200)")))
