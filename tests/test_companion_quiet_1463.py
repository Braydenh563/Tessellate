"""The companion comes in quietly on a new page (INBOX 1463).

The owner, 2026-10-31: "when atlas or the companion comes tumbling afrom side
screen acorss the screen or falls from the ceiling across my screen when I am
on a new page it is really distracting ... I want ... for it to be a non
intrusive companion".

Measured before (companion-1031.md): every tab arrival picked among glide,
walk on, tumble, fall (Atlas 1,500ms from above the window) and materialise,
and a sub-view change could carry it across the page. Now the way in is a
fade under 200ms where it rests, or a few steps inside its own corner; the
showy ways wait behind Settings > Companion > Showy entrances, off by default;
a far move a sub-view asked for is a crossfade. The frames are counted by the
sweep named in the CHANGELOG line; these pin the wiring.
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
MENU = (ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _fn(name: str, src: str = AV) -> str:
    start = src.index(f"function {name}(")
    return src[start : src.index("\n}\n", start) + 2]


def test_the_showy_ways_are_off_unless_chosen() -> None:
    showy = _fn("nameMarkBuddyShowy")
    assert 'prefs.get("avatar-buddy-entrances", null) === "showy"' in showy
    assert "return false;" in showy
    enter = _fn("nameMarkBuddyEnter")
    quiet = enter.index("if (!nameMarkBuddyShowy() && !(unlockFirst && hangs)) return nameMarkBuddyQuietEnter(")
    # Before any of the showy ways is drawn or played.
    assert quiet < enter.index("let ways;") < enter.index('if (how === "glide") {')


def test_the_quiet_way_in_is_a_short_fade_or_a_few_steps() -> None:
    assert re.search(r"^const NMB_QUIET_FADE_MS = (\d+);$", AV, re.M)
    ms = int(re.search(r"^const NMB_QUIET_FADE_MS = (\d+);$", AV, re.M).group(1))
    step = int(re.search(r"^const NMB_QUIET_STEP_PX = (\d+);$", AV, re.M).group(1))
    assert ms < 200 and step <= 40
    quiet = _fn("nameMarkBuddyQuietEnter")
    assert "[{ opacity: 0 }, { opacity: 1 }], { duration: NMB_QUIET_FADE_MS" in quiet
    # The steps are faded up within the same 180ms: offset 0.3 of 600.
    assert "nameMarkBuddyWalkIn(buddy, fromLeft ? -NMB_QUIET_STEP_PX : NMB_QUIET_STEP_PX, NMB_QUIET_FADE_MS / 0.3, 0.3);" in quiet
    assert "{ opacity: 1, offset: shown }" in _fn("nameMarkBuddyWalkIn")
    for showy in ("rotate", "innerWidth", "innerHeight", "nameMarkBuddyBurst"):
        assert showy not in quiet, showy


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_the_quiet_way_is_steps_only_standing_near_a_side_and_never_twice() -> None:
    src = _fn("nameMarkBuddyQuietWay")
    cases = "[['stand',40,'',0.1],['stand',40,'',0.9],['stand',40,'step',0.1],['stand',400,'',0.1],['hang',10,'',0.1],['float',10,'',0.1],['sit',10,'fade',0.1]]"
    script = src + f"\nconsole.log(JSON.stringify({cases}.map((a) => nameMarkBuddyQuietWay(...a))));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["step", "fade", "fade", "fade", "fade", "fade", "fade"]


def test_a_new_view_never_carries_it_across_the_page() -> None:
    beat = _fn("nameMarkBuddyBeat")
    assert "nmb.quiet = fresh;" in beat and "nmb.quiet = false;" in beat
    assert beat.index("nmb.quiet = fresh;") < beat.index("placeNameMarkBuddy(buddy, false, fresh ? null : [nmb.x, nmb.y]);") < beat.index("nmb.quiet = false;")
    go = _fn("nameMarkBuddyGo")
    assert "if (nameMarkBuddyNoTravel() || (nmb.quiet && distance > size * NMB_FAR_SIZES)) {" in go
    # Before the far ways are chosen or played.
    assert go.index("nmb.quiet && distance") < go.index("nmb.travelPlay?.(")


def test_the_switch_is_in_settings_off_and_saved_with_a_companion() -> None:
    row = HTML[HTML.index('id="avatar-buddy-showy-row"') :][:600]
    assert '<input type="checkbox" id="avatar-buddy-showy">' in row and "checked" not in row.split("</label>")[0].replace('id="avatar-buddy-showy"', "")
    assert "Showy entrances" in row
    mount = _fn("mountBuddyShowy")
    assert 'prefs.set("avatar-buddy-entrances", box.checked ? "showy" : "quiet");' in mount
    assert "mountBuddyShowy();" in _fn("mountBuddyActivities")
    assert '"avatar-buddy-entrances"]' in MENU
