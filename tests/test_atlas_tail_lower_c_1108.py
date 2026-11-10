"""In-app Atlas: the nine tail poses of atlascat-1108 C2 and C3 and the eight lower-body states of C5, each with a trigger
(`atlasRigLower.spell`, `ATLAS_TAIL_BY_STATE`, `atlasTailPick.byMood`). Run in node's vm over the real file with a fixed clock."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
LIFE = (ROOT / "frontend" / "js" / "atlas-life.js").read_text(encoding="utf-8")
TAILS = ("hook", "coil_hold", "thump", "shiver", "tuck", "loop8", "tip_twitch", "balance", "pillow")
LOWERS = ("billow", "coil", "ripple_calm", "flutter", "pool", "hem_kick", "spiral", "heavy")

SCRIPT = r"""
const fs = require("fs"), vm = require("vm");
const src = fs.readFileSync("frontend/js/atlas-life.js", "utf8");
let clock = 0;
const ctx = { atlasFix: (v) => v, console, Math, Map, Set, Object, Array, Number, document: {}, window: {}, setTimeout, clearTimeout,
  performance: { now: () => clock },
  atlasLowerState: (buddy, box) => box.base };
vm.createContext(ctx);
vm.runInContext(src + "\n;this.__x = { spell: atlasRigLower.spell, acts: ATLAS_TAIL_ACTS, byState: ATLAS_TAIL_BY_STATE, byMood: atlasTailPick.byMood, bend: atlasTailBend, lower: ATLAS_LOWER_STATES, calm: atlasTailCalm.states, rests: atlasRigLower.rests };", ctx);
const x = ctx.__x;
const mk = (base, mood = "calm", spin = false) => ({ base, dataset: { atlasMood: mood }, classList: { contains: (c) => (c === "atl-play-spin" ? spin : false) } });
const buddy = (...cls) => ({ classList: { contains: (c) => cls.includes(c) } });
const at = (box, ms, b = buddy()) => { clock = ms; return x.spell(b, box); };
const out = {};
let box = mk("glide"); out.glideStart = at(box, 0); out.glideLater = at(box, 2000);
box = mk("sit"); out.sitStart = at(box, 0); out.sitLong = at(box, 41000); out.coil = at(mk("sit"), 0, buddy("nmb-act-meditate"));
box = mk("idle"); out.idle0 = at(box, 0); out.idle25 = at(box, 25000); out.idle33 = at(box, 33000);
out.idleAngry = at(mk("idle", "curious"), 25000);
out.flutter = at(mk("happy", "laughing"), 0);
box = mk("happy", "happy"); out.kick = at(box, 0); out.kickOver = at(box, 3000);
box = mk("sad", "sleepy"); out.heavy = at(box, 0); out.drowsy = at(mk("sad", "sad"), 0, buddy("nmb-drowsy")); out.sad = at(mk("sad", "sad"), 0);
box = mk("idle", "calm", true); out.spin = at(box, 100000); box.classList.contains = () => false; out.spinAfter = at(box, 101000); out.spinDone = at(box, 103000);
// the tail: the hook turns the tip back up, a tip twitch moves only the tip
const rest = { curl: 0.25, amp: 0, period: 1, k: 1, tip: 0, env: 6 };
const twitch = { ...x.acts.tip_twitch, amp: 0.2 };
out.twitchNear = Math.abs(x.bend(0.3, twitch, 1.3, 0.5, 0) - x.bend(0.3, rest, 1.3, 0.5, 0));
out.twitchTip = Math.abs(x.bend(1, twitch, 1.3, 0.5, 0) - x.bend(1, rest, 1.3, 0.5, 0));
out.hookTip = x.bend(1, x.acts.hook, 0, 0, 0) - x.bend(1, { ...x.acts.hook, tip: 0 }, 0, 0, 0);
out.hookRoot = x.bend(0, x.acts.hook, 0, 0, 0);
out.tailRows = Object.keys(x.acts);
out.lowerRows = Object.keys(x.lower);
out.byStateKeys = Object.keys(x.byState);
out.byMood = Object.keys(x.byMood);
out.calm = [...x.calm];
out.rests = [...x.rests];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def got() -> dict:
    out = subprocess.run(["node", "-e", SCRIPT], capture_output=True, text=True, timeout=30, check=True, cwd=ROOT)
    return json.loads(out.stdout)


@needs_node
def test_the_rows_are_in_the_tables(got: dict) -> None:
    assert set(TAILS) <= set(got["tailRows"]) and set(LOWERS) <= set(got["lowerRows"])
    assert set(LOWERS) <= set(got["byStateKeys"]), "each lower state picks the tail that goes with it"
    assert got["hookRoot"] == 0, "the root never moves"


@needs_node
def test_a_fast_glide_billows_for_its_first_moments_only(got: dict) -> None:
    assert (got["glideStart"], got["glideLater"]) == ("billow", "glide")


@needs_node
def test_a_long_sit_pools_and_meditating_coils(got: dict) -> None:
    assert (got["sitStart"], got["sitLong"], got["coil"]) == ("sit", "pool", "coil")


@needs_node
def test_a_calm_idle_ripples_for_eight_seconds_of_forty(got: dict) -> None:
    assert (got["idle0"], got["idle25"], got["idle33"]) == ("idle", "ripple_calm", "idle")
    assert got["idleAngry"] == "idle", "only a calm mood ripples"


@needs_node
def test_glad_flutters_or_kicks_and_tired_is_heavy(got: dict) -> None:
    assert got["flutter"] == "flutter" and (got["kick"], got["kickOver"]) == ("hem_kick", "happy")
    assert got["heavy"] == "heavy" and got["drowsy"] == "heavy" and got["sad"] == "sad"


@needs_node
def test_a_twirl_leaves_a_spiral_that_unwinds(got: dict) -> None:
    assert (got["spin"], got["spinAfter"], got["spinDone"]) == ("spiral", "spiral", "idle")


@needs_node
def test_the_tip_twitch_moves_only_the_tip_and_the_hook_bends_the_tip_back(got: dict) -> None:
    assert got["twitchTip"] > 10 * got["twitchNear"], (got["twitchNear"], got["twitchTip"])
    assert got["hookTip"] > 1.0


@needs_node
def test_the_resting_states_re_read_on_their_timer_and_the_calm_ones_rest_on_the_compositor(got: dict) -> None:
    assert set(LOWERS) <= set(got["rests"]), "else a spell never ends: the rig re-reads the state only on this timer"
    assert {"coil", "ripple_calm", "pool", "heavy"} <= set(got["calm"])
    assert not {"billow", "flutter", "hem_kick", "spiral"} & set(got["calm"]), "the lively ones keep the frame loop"


def test_the_moods_pick_the_tails() -> None:
    row = LIFE.split("atlasTailPick.byMood = ")[1].split("\n")[0]
    for mood, pose in (("curious", "hook"), ("shy", "tuck"), ("worried", "shiver"), ("sleepy", "pillow")):
        assert f'{mood}: [[' in row and f'"{pose}"' in row.split(f"{mood}: ")[1].split("]]")[0], mood


def test_a_shiver_springs_fast_and_every_goal_carries_the_tip_and_envelope() -> None:
    assert '["flick", "stiff", "shiver"].includes(tail.act) ? 7 : 2.6' in LIFE
    assert "tip: base.tip || 0, env: base.env || 1.5" in LIFE
