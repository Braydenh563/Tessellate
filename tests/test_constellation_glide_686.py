"""INBOX 686: the Dashboard's Notebook constellation glides on Regenerate.

The owner: "can you add a smooth animation for regenerating the notebook
constelation??" Regenerate used to tear the p5 sketch down and mount a new
one, so the sky changed in a single frame. Now the live sketch retargets:
stars ease to the new arrangement, unpaired ones fade in or out, the lines
fade out and back, and with interface animations off or reduced motion it is
a quick cross-fade instead. The pure parts run under node here; the frames
themselves are measured by `scratchpad/ui-sweeps/constellation686.js`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

DASH = Path(__file__).resolve().parents[1] / "frontend" / "js" / "dashboard.js"
SOURCE = DASH.read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _fn(name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", SOURCE, re.S | re.M)
    assert match, f"{name} is gone from dashboard.js"
    return match.group(0)


def _const(name: str) -> int:
    match = re.search(rf"^const {name} = (\d+);", SOURCE, re.M)
    assert match, f"{name} is gone from dashboard.js"
    return int(match.group(1))


def _node(body: str):
    script = "\n".join(_fn(n) for n in ("artEaseOut", "artLineFade", "artRetarget")) + "\n" + body
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_the_glide_lasts_600_to_900_ms_and_the_fade_is_quick():
    assert 600 <= _const("ART_GLIDE_MS") <= 900
    assert _const("ART_FADE_MS") <= 250


@needs_node
def test_no_frame_moves_a_star_more_than_an_eighth_of_its_journey():
    """At the glide's own frame rate, the largest step of the ease is under
    1/8 of the whole: the owner's bound, before a browser adds any jitter."""
    ms, fps = _const("ART_GLIDE_MS"), _const("ART_GLIDE_FPS")
    steps = _node(
        f"const n = Math.ceil({ms} / (1000 / {fps})); const out = [];"
        "for (let i = 0; i < n; i++) out.push(artEaseOut((i + 1) / n) - artEaseOut(i / n));"
        "process.stdout.write(JSON.stringify(out));"
    )
    assert max(steps) <= 1 / 8, max(steps)
    assert all(s >= 0 for s in steps), "the ease runs backwards somewhere"
    assert abs(sum(steps) - 1) < 1e-9


@needs_node
def test_a_late_frame_stalls_the_glide_rather_than_jumping_it():
    """The glide's clock advances at most ART_GLIDE_STEP_MS a frame, so even
    the ease's fastest frame, its first, stays under the bound however late
    the browser draws it."""
    ms, cap = _const("ART_GLIDE_MS"), _const("ART_GLIDE_STEP_MS")
    first = _node(f"process.stdout.write(JSON.stringify(artEaseOut({cap} / {ms})));")
    assert first <= 1 / 8, first
    assert "Math.min(now - glide.last, ART_GLIDE_STEP_MS)" in SOURCE
    assert "glide.last = now" in SOURCE and "last: null" in SOURCE, "the clock starts at the first drawn frame"


def test_the_glide_raises_the_frame_rate_and_drops_it_back():
    assert "p.frameRate(ART_GLIDE_FPS)" in SOURCE
    assert SOURCE.count("p.frameRate(ART_FRAME_RATE)") >= 2, "the sketch never returns to its resting rate"


@needs_node
def test_the_lines_fade_out_and_back_continuously():
    out = _node(
        "const us = [0, 0.15, 0.3, 0.4, 0.5, 0.75, 1];"
        "process.stdout.write(JSON.stringify([us.map((u) => artLineFade(1, u)), us.map((u) => artLineFade(0.4, u))]));"
    )
    full, half = out
    assert full[0] == 1 and full[2] == 0 and full[3] == 0 and full[-1] == 1
    assert 0 < full[1] < 1 and 0 < full[5] < 1
    # An interrupted glide starts its lines from where they were, not from 1.
    assert half[0] == pytest.approx(0.4)


@needs_node
def test_stars_pair_by_category_and_index():
    out = _node(
        """
const shown = [
  { cat: "Work", idx: 0, x: 10, y: 20, vis: 1, drawSize: 3 },
  { cat: "Work", idx: 1, x: 30, y: 40, vis: 0.5, drawSize: 2 },
  { cat: "Home", idx: 0, x: 50, y: 60, vis: 1, drawSize: 4 },
];
const next = [
  { cat: "Work", idx: 0, size: 5 },
  { cat: "Work", idx: 1, size: 5 },
  { cat: "Work", idx: 2, size: 5 },
];
const leaving = artRetarget(shown, [{ cat: "Old", idx: 0, x: 1, y: 2, vis: 0.6, drawSize: 1 }, { cat: "Gone", idx: 0, x: 0, y: 0, vis: 0 }], next);
process.stdout.write(JSON.stringify({ next, leaving }));
"""
    )
    first, second, fresh = out["next"]
    assert first["from"] == {"x": 10, "y": 20, "vis": 1, "size": 3}
    # A star caught mid-fade starts from its drawn strength, not from full.
    assert second["from"] == {"x": 30, "y": 40, "vis": 0.5, "size": 2}
    assert fresh["from"] == {"x": None, "y": None, "vis": 0, "size": 0}, "a new star grows in where it lands"
    cats = sorted(s["cat"] for s in out["leaving"])
    assert cats == ["Home", "Old"], "unpaired stars leave; a fully faded one is dropped"
    assert next(s for s in out["leaving"] if s["cat"] == "Old")["from"]["vis"] == pytest.approx(0.6)


def test_regenerate_retargets_the_live_sketch_rather_than_rebuilding_it():
    body = SOURCE[SOURCE.index("async function renderArtWidget(body)") :]
    body = body[: body.index("\nasync function startArt")]
    regen = body[body.index('"ph:dice-five Regenerate"') :]
    regen = regen[: regen.index("})\n  );")]
    assert "artInstance.regenerate()" in regen
    save = body[body.index('"ph:floppy-disk Save PNG"') :]
    save = save[: save.index("})\n  );")]
    assert "saveSettled()" in save, "Save PNG must save the settled layout, never a frame mid-glide"
    assert "saveCanvas" not in save


def test_interface_animations_off_and_reduced_motion_cross_fade():
    sketch = SOURCE[SOURCE.index("p.regenerate = ") :]
    sketch = sketch[: sketch.index("\n    };") ]
    assert "dataset.uiMotion" in sketch
    assert "reducedMotionWanted()" in sketch
    assert "fade = { snap" in sketch, "the still path is a cross-fade of the old picture"
    assert "(now - fade.start) / ART_FADE_MS" in SOURCE


# The constellation has a light well, fades between themes and keeps its shape and height across a theme change (INBOX 803, 838).

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"


def _front_css(name: str) -> str:
    return (CSS / name).read_text(encoding="utf-8")


def test_the_constellation_has_a_light_well_and_fades_between_themes():
    js = (ROOT / "frontend" / "js" / "dashboard.js").read_text(encoding="utf-8")
    # HSL lightness 250 clamps to white, the card's own colour: no well.
    assert "250 - (y / height) * 10" not in js
    # One gradient from lightness 95 down to 91 (it was 55 strips of 95 - (y / height) * 4).
    assert "${dark ? 14 : 95}%" in js and "${dark ? 24 : 91}%" in js
    body = js[js.index("function refreshArtForTheme("):].split("\nfunction buildArtParticles", 1)[0]
    assert 'className = "art-veil"' in body
    # No veil, so an instant change, with reduced motion or animations off.
    assert "reducedMotionWanted()" in body and 'uiMotion === "off"' in body
    css = _front_css("02-chat-graph.css")
    veil = css[css.index(".art-holder > .art-veil {"):].split("}", 1)[0]
    assert "transition: opacity calc(var(--ui-slow)" in veil


# A theme change keeps the constellation's shape and height (INBOX 838).


def test_the_constellation_keeps_its_shape_and_its_height_across_a_theme_change():
    """"swapping between light and dark mode collapses the notebook
    constellation and joltingly redraws it without it staying the same shape"
    (INBOX 838). Measured over a theme switch: the holder fell 220px to 0 for a
    frame (the veil is absolute, so the canvas alone gave it height), and every
    star's drift restarted from phase 0 (up to 6px)."""
    css = (CSS / "02-chat-graph.css").read_text(encoding="utf-8")
    holder = css[css.index(".art-holder {") :].split("}", 1)[0]
    assert "min-height: 13.75rem;" in holder
    js = (JS / "dashboard.js").read_text(encoding="utf-8")
    # The drift is read off a page-lifetime clock, never a sketch's own.
    assert "const artEpoch = performance.now();" in js
    assert "p.millis() * 0.0003" not in js
    assert js.count("artDriftMs() * 0.0003") == 2
