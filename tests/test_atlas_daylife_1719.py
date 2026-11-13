"""INBOX 1719 b and 1696 j, the in-app side of `tests/test_overlay_daylife_1719.py`: the companion answers dusk (a
stretch), the morning's first key or press (a sleepy wave, once a day), a full-screen view left (a look back) and a long
run of typing come to rest (a nod), the desk's four rows under the same names. Node on fixed dates."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
MENU = unwrapped((ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8"))
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const [block] = process.argv.slice(1);
const nmb = {};
eval(block);
const s = nmb.dayLife;
const at = (h, m = 0, sec = 0, d = 9) => new Date(2026, 10, d, h, m, sec);
const out = {};
out.dawn = s.input(at(5, 50), true);
out.first = s.input(at(7, 30), true);
s.hello = at(7, 30).toDateString();
out.again = s.input(at(8, 0), true);
out.nextDay = s.input(at(7, 0, 0, 10), false);
out.afternoon = s.input(at(14, 0, 0, 11), false);
s.run = null;
let t = at(9).getTime();
const said = [];
for (let i = 0; i < 40; i++) { s.input(new Date(t), true); t += 900; }   // 35 s of keys
said.push(...s.rested(t + 1000));                                       // resting 1.9 s: not yet
said.push(...s.rested(t + 3200));                                       // 4.1 s: a burst
out.burst = said;
s.run = null;
let u = at(10).getTime();
for (let i = 0; i < 10; i++) { s.input(new Date(u), true); u += 900; }   // 8 s
out.short = s.rested(u + 5000);
out.toDusk = [s.toDusk(at(16, 0)), s.toDusk(at(18, 0))];
console.log(JSON.stringify(out));
"""


def _block() -> str:
    m = re.search(r"^nmb\.dayLife = \{.*?\n\};$", MENU, re.S | re.M)
    assert m
    return m.group(0)


@needs_node
def test_the_morning_hello_and_the_typing_burst():
    got = subprocess.run(["node", "-e", HARNESS, _block()], capture_output=True, text=True, timeout=60, check=True)
    r = json.loads(got.stdout)
    assert r["dawn"] == [] and r["first"] == ["morning_hello"] and r["again"] == []
    assert r["nextDay"] == ["morning_hello"] and r["afternoon"] == []
    assert r["burst"] == ["typing_burst"] and r["short"] == []
    assert r["toDusk"][0] == 3600 * 1000 + 1000 and 22 * 3600 * 1000 < r["toDusk"][1] <= 23 * 3600 * 1000 + 1000


def test_the_rows_and_the_listeners():
    rows = re.search(r"^Object\.assign\(NMB_REACTIONS, \{(.*?)\n\}\);", MENU, re.S | re.M)
    assert rows
    names = set(re.findall(r"^  ([a-z_]+):", rows.group(1), re.M))
    #: `writing_stretch` joined the rows for L-chat-7 (a minute's writing run ends in a stretch, tests/test_writing_stretch_l7.py).
    assert names == {"night_falls", "morning_hello", "fullscreen_app", "typing_burst", "writing_stretch"}
    assert all("world: true" in line for line in rows.group(1).strip().splitlines())  # Little habits off and reduced motion stop them
    assert 'document.addEventListener("keydown", seen, { capture: true, passive: true });' in MENU
    assert 'window.addEventListener("fullscreenchange", () => document.fullscreenElement || nameMarkBuddyReact("fullscreen_app"), true);' in MENU
