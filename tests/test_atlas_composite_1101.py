"""One animation off the compositor costs the whole figure (audit 1031, row 17).

Measured in this repo's Chromium (153): once any running animation cannot be
composited, the page restyles EVERY animated element every frame, 60 a second,
whatever else is fine. A companion with one such animation ran 258 ms of main
thread a second at rest (65 style recalcs a second); with none, 69 (14). The two
causes found, neither visible in the code:

- `composite: "add"` is never composited, on the element or a child;
- two animations on one property of one element (a CSS loop's `rotate` and a
  Web Animation's `rotate`) are neither composited.

Atlas's micro behaviours (atlas-micro.js) played two to three seconds of both
over the body's sway loop every few seconds. They now replace a property the
loops leave alone. These lints keep the class from coming back.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MICRO = (JS / "atlas-micro.js").read_text(encoding="utf-8")
LAZY = (ROOT / "frontend" / "css" / "atlas-lazy.css").read_text(encoding="utf-8")

#: `composite: "add"` call sites today, outside comments: the companion's short gestures (a
#: glide, a beat, a manner, a menu nudge). The micro behaviours have none (the ear flick went
#: with audit 1101).
#: A new one is a seconds-long loop on the main thread unless it is as short as these;
#: lower this when one goes, never raise it for a loop.
ADD_SITES = 7


def _code_lines(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.lstrip().startswith("//")]


def test_composite_add_sites_do_not_grow() -> None:
    found = sum(ln.count('composite: "add"') for p in JS.glob("*.js") for ln in _code_lines(p))
    assert found <= ADD_SITES, f"{found} sites add to a running property; each takes the whole figure off the compositor"


def test_a_micro_shift_and_tilt_replace_what_the_loops_leave_alone() -> None:
    shift = re.search(r'if \(kind === "shift"\) \{.*?\n  \}', MICRO, re.S)
    tilt = re.search(r'if \(kind === "tilt"\) \{.*?\n  \}', MICRO, re.S)
    assert shift and tilt
    # The body's loop owns `rotate`: the shift moves `translate` only, and does not add.
    body = [ln for ln in shift.group(0).splitlines() if not ln.lstrip().startswith("//")]
    assert not any("rotate" in ln for ln in body), "the body's sway loop owns rotate"
    assert any('querySelector(".atl-lw-body")' in ln for ln in body)
    # The head's `rotate` is the rig's: the tilt animates `transform`, replacing.
    assert "transform:" in tilt.group(0)


def test_an_away_companion_pauses_its_roots_too() -> None:
    # The layer roots (`svg.nm-atlas`) carry the nebula's, the skirt's and the shimmer's loops:
    # `.nm-atlas *` did not match them, so they ran under `visibility: hidden` (67 animations
    # live off-tab, 5 now).
    assert re.search(r"#nm-buddy\.nmb-away :is\(\.nm-atlas, \.nm-atlas \*, ", LAZY)


def test_the_micro_behaviours_never_add_and_the_ear_flick_replaces_transform() -> None:
    code = "\n".join(_code_lines(JS / "atlas-micro.js"))
    assert "composite" not in code, "a micro behaviour replaces; add is the main thread's"
    ear = re.search(r'if \(kind === "ear"\) \{.*?\n  \}', MICRO, re.S)
    assert ear
    body = "\n".join(ln for ln in ear.group(0).splitlines() if not ln.lstrip().startswith("//"))
    # An svg part's individual `rotate` is the main thread's: the flick turns `transform`, from the crest's turn.
    assert "rotate:" not in body and "transform:" in body and "--atl-crest" in body


def test_the_lower_pose_boxes_hint_translate_and_the_stream_has_one_translate_loop() -> None:
    # Measured in Chromium 153 (compositeFailed per animation, traced from the start): a Web
    # Animation of `translate` on a box that says `will-change: transform` is refused (bit 19);
    # two `translate` animations on one box (the stream's CSS drift and its flow path) are refused
    # (bit 6). Each refusal puts the whole figure's animations back on the main thread.
    core = (ROOT / "frontend" / "css" / "characters-lazy.css").read_text(encoding="utf-8")
    rule = re.search(r"\.atl-lw > \.atl-lw-pose \{[^}]*\}", core)
    assert rule and "will-change: translate" in rule.group(0)
    for box in ("atl-lw-pose-neb", "atl-lw-pose-neb-front"):
        full = re.search(r"& \." + box + r" \{ animation: ([^;]*);", LAZY)
        assert full and "atl-lw-drift" not in full.group(1), "the flow path carries the stream's wobble"
