"""L152 A4: the app's presence spells hold the desk's (`overlay/presence.py` SPELLS): the same hours, lengths and moods."""

from __future__ import annotations

import re

import pytest

from tessellate.core.overlay import presence as pr
from pathlib import Path

from tests._js_scope import unwrapped

JS = unwrapped((Path(__file__).resolve().parents[1] / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
BLOCK = JS[JS.index("const NMB_SPELLS = {") : JS.index("function nameMarkBuddySpellFactor")]
ROWS = {
    m.group(1): (m.group(2), (int(m.group(3)), int(m.group(4))), (int(m.group(5)), int(m.group(6))), re.findall(r'"(\w+)"', m.group(7)))
    for m in re.finditer(
        r'^\s*(\w+): \{ spell: "(\w+)", hours: \[(\d+), (\d+)\], sec: \[(\d+), (\d+)\], moods: \[([^\]]*)\] \}', BLOCK, re.M
    )
}


def test_every_app_spell_is_the_desks_by_hours_length_and_mood() -> None:
    assert ROWS, "the table was not read"
    for act, (name, (frm, to), (lo, hi), moods) in ROWS.items():
        sp = pr.SPELLS[name]
        assert pr._span(frm, to) == sp.hours, act
        assert (float(lo), float(hi)) == sp.seconds, act
        assert tuple(moods) == sp.moods, act


def test_only_the_reading_spell_has_no_app_counterpart() -> None:
    assert {v[0] for v in ROWS.values()} == set(pr.SPELLS) - {"read"}


def test_each_app_spell_is_a_built_desk_act_of_atlas() -> None:
    for act in ROWS:
        assert re.search(rf"^\s*{act}: \{{ ms: \d+, w: [\d.]+, cool: \d+, poses: \[[^\]]*\], atlas: true, desk: true \}}", JS, re.M), act


def test_the_pick_and_the_length_follow_the_hours_and_moods(tmp_path) -> None:
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("needs node")
    end = JS.index("//: **More ways to be somewhere**")
    code = JS[JS.index("const NMB_SPELLS = {") : end] + """
const out = {
  tea8: nameMarkBuddySpellFactor("tea", 8, "sleepy"), tea8plain: nameMarkBuddySpellFactor("tea", 8, "bored"), tea13: nameMarkBuddySpellFactor("tea", 13, "sleepy"),
  stars23: nameMarkBuddySpellFactor("stars", 23, "x"), stars2: nameMarkBuddySpellFactor("stars", 2, "x"), stars4: nameMarkBuddySpellFactor("stars", 4, "x"),
  plant3: nameMarkBuddySpellFactor("plant", 3, "x"), other: nameMarkBuddySpellFactor("hop", 3, "x"),
  lo: nameMarkBuddySpellMs("tea", 0), hi: nameMarkBuddySpellMs("tea", 1),
};
console.log(JSON.stringify(out));
"""
    import json

    script = tmp_path / "spells.js"
    script.write_text(code, encoding="utf-8")
    got = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    assert got == {"tea8": 1.6, "tea8plain": 1, "tea13": 0, "stars23": 1, "stars2": 1, "stars4": 0, "plant3": 1, "other": 1, "lo": 120000, "hi": 270000}
