"""What a carried or thrown companion costs per frame (owner, 2026-10-17:
"when throwing companions around the physics and movement was insanely
framey and laggy and not clean"; BACKLOG 2026-10-12: "about 4 frames a
second").

Measured, not guessed (`/tmp` sweep, Chromium, 1440x900): the loop was
already one rAF on transforms with a capped dt, and the frames were lost to
style recalculation, not script. Two things made each frame's restyle of
`#nm-buddy` expensive:

- `body:has(dialog[open]:modal, .modal-overlay:not(.hidden), ...) #nm-buddy`
  is matched against the whole document every time the companion's own style
  changes, which is every frame it moves (4.7 ms of a 16.7 ms frame; 0.2 ms
  without it). JS now sets `data-cover` on the companion when a dialog,
  modal overlay or the lock screen is up, and the CSS reads that.
- `--nmb-sway` was an inherited custom property written on `#nm-buddy` every
  frame, which restyles every descendant of the figure (53 to 140 elements,
  7 to 15 ms). The lean is now written on the figure and the legs, the only
  elements that wear it (the perf agent's 27ec556, found independently).

These are static checks because the number only shows in a browser; the
sweep that measures it is described in
`docs/roadmap/agent-remaining/companion-physics-1017.md`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AV = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")
CSS_DIR = ROOT / "frontend" / "css"


def _css() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(CSS_DIR.glob("*.css")))


def _fn(name: str) -> str:
    start = AV.index(f"function {name}(")
    return AV[start : AV.index("\n}\n", start) + 2]


def test_no_document_wide_has_rule_is_matched_against_the_companion() -> None:
    bad = re.findall(r"(?:^|[\n,])\s*(?:body|html|:root):has\([^{}]*\)\s+#nm-buddy", _css())
    assert not bad, "an ancestor :has() is re-matched over the whole DOM on every restyle of #nm-buddy"


def test_a_cover_over_the_page_is_a_flag_the_script_sets() -> None:
    css = _css()
    assert re.search(r'#nm-buddy\[data-cover="lock"\]\s*\{\s*display:\s*none', css)
    assert re.search(r"#nm-buddy\[data-cover\]:not\(\.nm-viewer-figure > \*\)\s*\{[^}]*opacity:\s*0", css)
    fn = _fn("nameMarkBuddyCoverCheck")
    assert "dataset.cover" in fn and ":modal" in fn and "lock-overlay" in fn
    assert "MutationObserver" in AV[AV.index("nmb.coverObserver") - 200 : AV.index("nmb.coverObserver") + 400]


def test_sway_is_written_on_the_parts_that_wear_it_not_on_the_companion() -> None:
    # 27ec556 (the perf agent) and this branch found the same cause: an inherited
    # custom property set on #nm-buddy every frame restyles the whole drawing.
    assert "--nmb-sway" not in AV and "--nmb-sway" not in _css()
    fn = _fn("nameMarkBuddySway")
    assert ".nm-figure" in fn and ".nmb-leg" in fn and "style.rotate" in fn


def test_the_carry_writes_the_turn_only_when_it_changes() -> None:
    src = AV[AV.index("const follow = () => {") :][:1800]
    assert "dataset.turn !==" in src, "a same-value attribute write still dirties the companion's style"


def test_the_flight_frame_is_time_based_capped_and_writes_no_layout_properties() -> None:
    src = AV[AV.index("function nameMarkBuddyThrow(") :][:4200]
    frame = src[src.index("const frame = (now) =>") : src.index("const next = () =>")]
    assert "Math.min(32, Math.max(0, now - then))" in frame
    assert re.search(r"nameMarkBuddyFlightStep\(s, Math\.min\(16, dt\)", frame)
    for forbidden in ("getBoundingClientRect", "offsetWidth", "offsetHeight", "style.left", "style.top", "setInterval", "setTimeout"):
        assert forbidden not in frame
    assert src.count("requestAnimationFrame(") == 1


needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


@needs_node
def test_the_flight_lands_in_the_same_place_at_60_and_144_hz() -> None:
    consts = re.search(r"^const NMB_THROW = .*;$", AV, re.M).group(0)
    src = _fn("nameMarkBuddyFlightStep")
    script = "\n".join(
        [
            consts,
            src,
            "const W = { left: 0, right: 1376, top: 48, floor: 780, ledges: [] };",
            "const k = { ...NMB_THROW, bounce: 0.4, ground: 0.006, air: 0.0011, spin: 0 };",
            # Frame at `hz`, the way the loop does: dt capped at 32, stepped in pieces of at most 16.
            "function fly(hz, vx, vy) { let s = { x: 200, y: 400, vx, vy, rot: 0, t: 0, on: null, rest: false };"
            + " const frame = 1000 / hz; let guard = 0;"
            + " while (!s.rest && guard++ < 5000) { let dt = Math.min(32, frame); while (dt > 0 && !s.rest) { s = nameMarkBuddyFlightStep(s, Math.min(16, dt), W, k); dt -= 16; } }"
            + " return { x: s.x, y: s.y, t: s.t }; }",
            "console.log(JSON.stringify([[1.2, -0.5], [2.5, -1.2], [-1.8, -0.2]].map(([vx, vy]) => [fly(60, vx, vy), fly(144, vx, vy), fly(30, vx, vy)])));",
        ]
    )
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for a, b, c in out:
        assert abs(a["x"] - b["x"]) < 120 and abs(a["x"] - c["x"]) < 120, (a, b, c)
        assert abs(a["y"] - b["y"]) < 12 and abs(a["y"] - c["y"]) < 12, (a, b, c)


def test_the_atlas_rig_reads_style_once_before_it_writes_any() -> None:
    # A thrown Atlas ran at 29 fps at 1x CPU and 5 fps at 4x: each arm read its
    # probe and then wrote its transform, so the next arm's read (and the
    # head's) forced another restyle, on top of the flight's own writes.
    motion = (ROOT / "frontend" / "js" / "atlas-motion.js").read_text(encoding="utf-8")
    start = motion.index("function atlasRigFrame(")
    body = motion[start : motion.index("\n}\n", start)]
    first_write = min(i for i in (body.find("setProperty("), body.find("setAttribute("), body.find(".style.rotate =")) if i >= 0)
    for read in ("atlasRigRead(", "getAnimations()", "getComputedStyle("):
        assert body.count(read) == 1, f"{read} is read once"
        assert body.index(read) < first_write, f"{read} comes after a write"
