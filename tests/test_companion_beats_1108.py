"""The in-app companion shifts the pose of a long act by the catalogue's beats (atlascat-1108 A4). The desk side is
`tests/test_overlay_catalogue_1108.py`. Fixed seed, no wall time."""

from __future__ import annotations

import json

from tests._cat_node import AVATARS, CATALOGUE, run

SHIFT_SIM = """
nmb.cat.load(); await new Promise((r) => setTimeout(r, 20)); const gaps = {};
let s = 7; const rand = () => { s = (s * 16807) %% 2147483647; return s / 2147483647; };
for (const act of Object.keys(NAME_MARK_BUDDY_ACTS)) {
  const plan = nmb.cat.plan(act, 420000, rand); let last = 0, worst = 0;
  for (const t of [...plan, 420000]) { worst = Math.max(worst, t - last); last = t; }
  gaps[act] = worst;
}
console.log(JSON.stringify(gaps));
"""


def test_a_long_app_act_shifts_its_pose_inside_the_budget() -> None:
    """Over seven minutes of every act with a shift beat, no gap between shifts is over 90 s."""
    doc = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    acts = {}
    for e in doc["entries"]:
        if e["kind"] == "idle_act" and e["app"]["s"] == "built" and any(b.get("shifts") for b in e.get("beats", [])):
            for n in e["app"]["names"]:
                if n.startswith("acts:"):
                    acts[n[5:]] = {"ms": 1, "w": 1, "cool": 0, "poses": ["stand"]}
    assert set(acts) == {"nap", "read", "tea", "fish", "journal", "stars", "blanket", "plant", "knit"}, acts  # 1696 v: the Batch D acts with a shift beat are built here; E5 added knit
    out = run(SHIFT_SIM % {}, acts)
    assert max(out.values()) <= 90000, out


def test_an_act_without_a_shift_beat_plans_none() -> None:
    out = run("nmb.cat.load(); await new Promise((r) => setTimeout(r, 20)); console.log(JSON.stringify(nmb.cat.plan('blink', 420000)));", {"blink": {"ms": 1, "w": 1, "cool": 0, "poses": ["stand"]}})
    assert out == []


def test_the_runner_arms_the_beats_after_each_act_starts() -> None:
    assert "nmb.cat.arm(act, ms || spec?.ms || 1200);" in AVATARS.read_text(encoding="utf-8")
