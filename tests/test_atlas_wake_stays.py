"""Atlas stays awake once woken (the owner, 2026-11-04, about 2:40 am local).

"atlas always just instantly falls back asleep even when I wake it": in the small hours its resting mood was sleepy
whatever you did, so a woken Atlas dozed again 45 s later while you worked. Run under node with a fixed clock.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ATLAS = (ROOT / "frontend" / "js" / "atlas.js").read_text(encoding="utf-8")
AVATARS = (ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8")


def _fn(src: str, head: str) -> str:
    body = src[src.index(head) :]
    return body[: body.index("\n}\n") + 3]


def _run(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


SETUP = """
let clock = 0; let hourNow = 2;
const RealDate = Date;
globalThis.Date = class extends RealDate { static now() { return clock; } getHours() { return hourNow; } };
let atlasLastInput = 0, atlasAwakeUntil = 0, atlasMoodNow = "sleepy";
const ATLAS_WAKE_MS = 2400, ATLAS_AWAKE_HOLD_MS = 45000;
const setAtlasMood = (m) => { atlasMoodNow = m; };
"""


def test_in_the_small_hours_an_atlas_in_use_is_not_sleepy():
    script = SETUP + _fn(ATLAS, "function atlasRestingMood()") + """
    const at = (min, idle) => { clock = min * 60000; atlasLastInput = clock - idle * 60000; return atlasRestingMood(); };
    console.log(JSON.stringify({ busy: at(100, 0.5), quiet2: at(100, 2), quiet4: at(100, 4), dayQuiet4: (hourNow = 14, at(100, 4)), dayQuiet11: at(100, 11) }));
    """
    r = _run(script)
    assert r == {"busy": "calm", "quiet2": "calm", "quiet4": "sleepy", "dayQuiet4": "calm", "dayQuiet11": "sleepy"}


def test_woken_often_it_stays_up_longer_each_time():
    script = SETUP + _fn(ATLAS, "function atlasWake(") + """
    const holds = [];
    for (let i = 0; i < 6; i++) { clock = 1e9 + i * 60000; atlasMoodNow = "sleepy"; atlasWake(0); holds.push((atlasAwakeUntil - clock) / 1000); }
    clock += 16 * 60000; atlasWake(0); holds.push((atlasAwakeUntil - clock) / 1000);
    console.log(JSON.stringify({ holds, mood: atlasMoodNow }));
    """
    r = _run(script)
    assert r["holds"] == [45, 90, 180, 360, 600, 600, 45]
    assert r["mood"] == "calm"


def test_a_night_nap_waits_for_a_quiet_half_minute_and_not_just_after_a_wake():
    assert 'if (act === "nap") w = idle > 90 * 1000 ? 3 : night && idle > 30 * 1000 && now >= (nmb.awakeUntil || 0) ? 1 : 0;' in AVATARS
