"""INBOX 1719 b, the in-app side: the companion reads the catalogue's `vitals` (the desk's table,
`tests/test_companion_vitals_1719.py`). Its breath was a fixed 4.6 s (him) or 4.0 s (her) whatever it did; now a walk,
a carry or a lively act quickens it (the animations' playback rate) and it eases back, sleepy slower, startled
quicker. Its blink gap was 3.4 to 7.6 s in every mood; now the mood's scale applies. Node, a fixed clock."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const [motion, life, cat, which] = process.argv.slice(1);
const doc = JSON.parse(fs.readFileSync(cat, "utf8"));
const ctx = { console, Math, Map, Set, Object, Array, JSON, Number, Infinity, nmb: { cat: { state: { doc: which === "none" ? null : doc } } } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(motion, "utf8"), ctx);
const src = fs.readFileSync(life, "utf8");
const grab = (re) => { const m = src.match(re); if (!m) throw new Error(String(re)); return m[0]; };
vm.runInContext("function atlasBreathFrame() {}\n" + grab(/^atlasBreathFrame\.hot = .*$/m) + "\n" + grab(/^atlasBreathFrame\.rate = [\s\S]*?\n};$/m), ctx);
const cls = (...on) => ({ classList: { contains: (c) => on.includes(c) } });
const anim = () => ({ rates: [], updatePlaybackRate(r) { this.rates.push(r); } });
const out = {};
const breath = { anims: [anim(), anim()], rise: anim(), rate: 1 };
const series = [];
// walking 10 s, then standing calm for 60 s, sampled every 0.4 s like the resting beat
for (let t = 0; t <= 70000; t += 400) series.push([t, ctx.atlasBreathFrame.rate(breath, t < 10000 ? cls("nmb-walking") : cls(), "calm", t)]);
out.series = series;
out.writes = breath.anims[0].rates.length;
out.synced = JSON.stringify(breath.anims[0].rates) === JSON.stringify(breath.rise.rates);
out.sleepy = ctx.atlasBreathFrame.rate({ anims: [], rate: 1 }, cls("nmb-drowsy"), "calm", 0);
out.startled = ctx.atlasBreathFrame.rate({ anims: [], rate: 1 }, cls(), "surprised", 0);
out.calm = ctx.atlasBreathFrame.rate({ anims: [], rate: 1 }, cls(), "calm", 0);
out.blink = Object.fromEntries(["calm", "sleepy", "curious", "surprised"].map((m) => [m, ctx.atlasBlink.vitals(m)]));
console.log(JSON.stringify(out));
"""


def run(which: str = "doc") -> dict:
    got = subprocess.run(
        ["node", "-e", HARNESS, str(JS / "atlas-motion.js"), str(JS / "atlas-life.js"), str(ROOT / "frontend" / "companion-catalogue.json"), which],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return json.loads(got.stdout)


@needs_node
def test_a_walk_leaves_it_out_of_breath_and_it_eases_back():
    r = run()
    rates = dict(r["series"])
    assert rates[9600] >= 1.3, rates[9600]  # walking: was 1.0
    assert rates[10400] >= 1.3 > rates[30000] > rates[50000]  # easing back after it stops
    assert rates[60000] < 1.05 and rates[70000] <= 1.0  # back to its calm breath within 50 s
    assert r["synced"] and r["writes"] <= 12, r["writes"]  # a write per 0.05 step, never per beat, chest and rise together


@needs_node
def test_moods_set_the_breath_and_the_blink():
    r = run()
    assert r["sleepy"] <= 0.85 < r["calm"] < r["startled"], r
    b = r["blink"]
    assert b["sleepy"]["gap"] < b["calm"]["gap"] < b["curious"]["gap"] <= b["surprised"]["gap"], b
    assert b["sleepy"]["len"] > 1.5, b


@needs_node
def test_before_the_catalogue_arrives_nothing_changes():
    r = run("none")
    assert {v for _t, v in r["series"]} == {1} and r["writes"] == 0
    assert all(v == {"gap": 1, "len": 1, "breath": 1} for v in r["blink"].values())


def test_the_beat_sets_the_rate_and_the_blink_clock_reads_the_gap():
    life = (JS / "atlas-life.js").read_text(encoding="utf-8")
    motion = (JS / "atlas-motion.js").read_text(encoding="utf-8")
    assert re.search(r"atlasBreathFrame\(box, live\);\n\s*atlasBreathFrame\.rate\(box\.atlasBreath,", life)
    assert "* gap);" in motion and "atlasBlink.vitals(" in motion
