"""The companion is stacked by what it is perched on.

INBOX 431 (5), the owner: "if it is perched on like a chat message bubble or
a library card, when it scrolls with them it should probably go behind the
top bar like the thing it is perched on not in front of it. If say it is
sitting on or perched on an element like the top bar, then it would be in
front".

Riding a panel's scroll, it is drawn in a band clipped to the area its perch
is seen in. The band was widened, at placement, to take in a head that
reached over the top bar (or a bar that sticks in the area) so a perch at
the very top of a panel was not cut where it stands; and it stayed widened
while the panel scrolled, so the figure was carried up over the bar its
perch had gone under (measured, `scratchpad/ui-sweeps/companionstack.js`:
62px of it past its perch's clip line on a chat message, a library card and
a note card, 41px over the top bar itself at the Large size). Now a shutter
inside the band, moved by the same scroll as the rider, brings the clip line
back down to the bar's edge pixel for pixel as the panel scrolls away from
where it was perched, and up from the bottom bar the same way; at rest it is
drawn whole. On the top bar itself it rides nothing and stays in front.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest
from tests._js_scope import unwrapped
from tests._css_paths import sheets

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
CSS08 = sheets("05-sidebars-themes.css", "characters-lazy.css")


def _fn(name: str, src: str = AV) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def _frames(s0: float, up: float, down: float, up_span: str = "undefined", down_span: str = "undefined") -> dict:
    # Runs the keyframes as written and reads them back at a set of scroll
    # offsets, interpolating linearly between keyframes as the browser does.
    script = (
        "const NMB_RIDE_PX = 1e6;\n"
        + _fn("nameMarkBuddyRideFrames")
        + """
const f = nameMarkBuddyRideFrames(%s, %s, %s, %s, %s);
const ty = (k) => Number(/translateY\\((-?[\\d.e+-]+)px\\)/.exec(k.transform)[1]);
const at = (frames, u) => {
  const p = u / NMB_RIDE_PX;
  for (let i = 1; i < frames.length; i += 1) {
    const a = frames[i - 1], b = frames[i];
    if (p <= b.offset) {
      const w = b.offset === a.offset ? 1 : (p - a.offset) / (b.offset - a.offset);
      return ty(a) + (ty(b) - ty(a)) * w;
    }
  }
  return ty(frames[frames.length - 1]);
};
const us = [0, 100, 200, 250, 280, 290, 300, 310, 320, 340, 400, 2000];
const offsets = [f.rider, f.shutter].map((fr) => fr.map((k) => k.offset));
console.log(JSON.stringify({
  offsets,
  rows: us.map((u) => ({ u, shutter: Math.round(at(f.shutter, u) * 1000) / 1000, net: Math.round((at(f.shutter, u) + at(f.rider, u)) * 1000) / 1000 })),
}));
"""
        % (s0, up, down, up_span, down_span)
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_shutter_closes_to_the_bar_as_the_panel_scrolls_away() -> None:
    # Perched at scroll 300 with its head 40px over the top bar's edge and
    # its feet 20px over the bottom bar's.
    got = _frames(300, 40, 20)
    for offs in got["offsets"]:
        assert offs[0] == 0 and offs[-1] == 1 and offs == sorted(offs)
    rows = {r["u"]: r for r in got["rows"]}
    # The rider still goes exactly where its panel goes: one px of travel
    # per px scrolled, whatever the shutter does (the shutter's own move is
    # taken back out of the rider's).
    for u, r in rows.items():
        assert r["net"] == pytest.approx(-u, abs=0.01)
    # Where it was perched: drawn whole, nothing shut.
    assert rows[300]["shutter"] == pytest.approx(0, abs=0.01)
    # Scrolled up: the top edge comes down pixel for pixel, and stops at
    # the bar's edge (40px down) once the head has gone under it.
    assert rows[310]["shutter"] == pytest.approx(10, abs=0.01)
    assert rows[340]["shutter"] == pytest.approx(40, abs=0.01)
    assert rows[2000]["shutter"] == pytest.approx(40, abs=0.01)
    # Scrolled down: the bottom edge comes up the same way, to the bottom
    # bar's edge (20px up), and no further.
    assert rows[290]["shutter"] == pytest.approx(-10, abs=0.01)
    assert rows[280]["shutter"] == pytest.approx(-20, abs=0.01)
    assert rows[0]["shutter"] == pytest.approx(-20, abs=0.01)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_shutter_is_shut_by_the_time_its_perch_goes_under() -> None:
    # Sitting on a card whose top edge is 20px under the bar, its head 40px
    # over it: the card is under the bar after 20px of scroll, so the
    # shutter closes over those 20px (two px a px), not over 40.
    got = _frames(300, 40, 20, "20", "10")
    rows = {r["u"]: r for r in got["rows"]}
    assert rows[310]["shutter"] == pytest.approx(20, abs=0.01)
    assert rows[320]["shutter"] == pytest.approx(40, abs=0.01)
    assert rows[290]["shutter"] == pytest.approx(-20, abs=0.01)
    for u, r in rows.items():
        assert r["net"] == pytest.approx(-u, abs=0.01)
    # Never slower than the panel itself: a span longer than the gap is
    # the gap.
    slow = {r["u"]: r for r in _frames(300, 10, 0, "80", "0")["rows"]}
    assert slow[310]["shutter"] == pytest.approx(10, abs=0.01)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_nothing_over_a_bar_means_nothing_moves() -> None:
    got = _frames(0, 0, 0)
    for r in got["rows"]:
        assert r["shutter"] == pytest.approx(0, abs=0.01)
        assert r["net"] == pytest.approx(-r["u"], abs=0.01)


def test_the_shutter_is_wired_into_the_band() -> None:
    ride = _fn("nameMarkBuddyRide")
    # One scroll timeline, two animations on it: the shutter and the rider
    # inside it, both transforms, so the compositor moves both with the
    # scroll in the same frame.
    assert "new ScrollTimeline({ source: want" in ride
    assert "nmb.shutterAnim = shutter.animate(" in ride
    assert "nmb.rideAnim = rider.animate(" in ride
    box = _fn("nameMarkBuddyRideBox")
    # The gaps are measured at placement against the bar's own edge, never
    # above it, and the keyframes set again from them.
    assert "nameMarkBuddyRideClip(r)" in box
    clip = _fn("nameMarkBuddyRideClip")
    assert "setKeyframes" in clip and "nameMarkBuddyRideFrames(" in clip
    build = _fn("nameMarkBuddyBuild")
    assert 'shutter.className = "nm-buddy-shutter";' in build
    assert "#nm-buddy-band.nmb-riding .nm-buddy-shutter {" in CSS08
    shutter_css = CSS08[CSS08.index("#nm-buddy-band.nmb-riding .nm-buddy-shutter {") :]
    shutter_css = shutter_css[: shutter_css.index("}")]
    assert "overflow: clip;" in shutter_css
    # On the top bar itself it rides nothing, in a band over the bar (40).
    band_css = CSS08[CSS08.index("#nm-buddy-band {") :]
    assert "z-index: 44;" in band_css[: band_css.index("}")]
