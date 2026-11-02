"""INBOX 1436: the long pause that becomes a picture, and the Wander and
Drift styles. The pure parts (the noise, the edge turn-back, the pause
decision) run in node; the rest is read from the source, as the other
background-art tests do."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
BG_ART = FRONTEND / "js" / "bg-art.js"
SETTINGS = FRONTEND / "js" / "settings.js"

_SCRIPT = r"""
const fs = require("fs");
const vm = require("vm");
const luma = fs.readFileSync(process.argv[3], "utf8").match(/function bgLuma[\s\S]*?\n}\n/)[0];
const src = luma + fs.readFileSync(process.argv[2], "utf8");
const noop = () => {};
const box = {
  document: { addEventListener: noop }, window: { addEventListener: noop },
  navigator: {}, performance: { now: () => 0 }, console,
};
vm.createContext(box);
vm.runInContext(src + `
this.out = { bgHash2, bgLattice, bgFbmRow, bgTurnBack, bgArtShouldFreeze, BG_ART_FREEZE_MS };
`, box);
const o = box.out;
const lat = o.bgLattice(5), row = new Uint8Array(4000);
o.bgFbmRow(lat, row, 4000, 0, 0.01, 3.7);
let min = 255, max = 0, maxStep = 0;
for (let i = 0; i < 4000; i++) {
  min = Math.min(min, row[i]); max = Math.max(max, row[i]);
  if (i) maxStep = Math.max(maxStep, Math.abs(row[i] - row[i - 1]));
}
const one = new Uint8Array(1);
o.bgFbmRow(lat, one, 1, 3, 0, 4);
const again = new Uint8Array(4000);
o.bgFbmRow(lat, again, 4000, 0, 0.01, 3.7);
const other = new Uint8Array(4000);
o.bgFbmRow(o.bgLattice(6), other, 4000, 0, 0.01, 3.7);
console.log(JSON.stringify({
  hashA: o.bgHash2(3, 4, 1), hashB: o.bgHash2(3, 4, 1), hashC: o.bgHash2(3, 4, 2), hashD: o.bgHash2(4, 3, 1),
  lattice: [one[0], Math.floor((lat[4 * 256 + 3] + 0.5 * lat[8 * 256 + 6] + 0.25 * lat[16 * 256 + 12]) / 1.75 * 255)],
  repeat: Array.from(row).every((v, i) => v === again[i]),
  seeded: Array.from(row).some((v, i) => v !== other[i]),
  min, max, maxStep,
  turn: [o.bgTurnBack(-1, -2, 0, 10), o.bgTurnBack(11, 2, 0, 10), o.bgTurnBack(-1, 2, 0, 10), o.bgTurnBack(5, -2, 0, 10)],
  freezeMs: o.BG_ART_FREEZE_MS,
  freeze: [
    o.bgArtShouldFreeze(0, 99999, false),
    o.bgArtShouldFreeze(1000, 20999, false),
    o.bgArtShouldFreeze(1000, 21000, false),
    o.bgArtShouldFreeze(1000, 90000, true),
  ],
}));
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    script = tmp_path_factory.mktemp("bgart1436") / "run.js"
    script.write_text(_SCRIPT, encoding="utf-8")
    run = subprocess.run(
        [node, str(script), str(BG_ART), str(SETTINGS)], capture_output=True, text=True, timeout=60, check=False
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_the_hash_is_stable_seeded_and_not_symmetric(out):
    assert out["hashA"] == out["hashB"]
    assert out["hashA"] != out["hashC"]
    assert out["hashA"] != out["hashD"]
    assert 0 <= out["hashA"] < 1


def test_value_noise_is_the_lattice_at_whole_numbers_repeatable_and_seeded(out):
    assert abs(out["lattice"][0] - out["lattice"][1]) <= 1
    assert out["repeat"] and out["seeded"]


def test_three_octave_noise_stays_in_range_and_is_smooth(out):
    assert 0 <= out["min"] and out["max"] <= 255
    assert out["max"] - out["min"] > 70  # it is a field, not a constant
    assert out["maxStep"] <= 10  # a hundredth of a lattice cell moves it little


def test_a_stroke_turns_back_only_when_leaving(out):
    assert out["turn"] == [2, -2, 2, -2]


def test_a_pause_freezes_after_twenty_seconds_and_only_once(out):
    assert out["freezeMs"] == 20000
    assert out["freeze"] == [False, False, True, False]


def _chunk(name: str) -> str:
    text = BG_ART.read_text(encoding="utf-8")
    start = text.index(f"\n  {name}(p, ctx) {{")
    nxt = re.search(r"\n  [a-z]+\(p, ctx\) \{", text[start + 10 :])
    end = start + 10 + nxt.start() if nxt else text.index("\n};\n", start)
    return text[start:end]


def test_wander_and_drift_follow_the_files_rules():
    for name in ("wander", "drift"):
        chunk = _chunk(name)
        assert "background:" in chunk, name
        assert "new Float32Array" in chunk or "new Uint32Array" in chunk, name
        assert not re.search(r"pixelDensity: *[2-9]|pixelDensity: *1\.", chunk), name
    drift = _chunk("drift")
    assert "pixelDensity: 0.125" in drift
    assert "createImageData" in drift and "putImageData" in drift
    assert "drawImage" not in drift  # scaled by the compositor, never by drawImage
    assert "bgFbmRow" in drift and "bgFbm3" not in drift
    wander = _chunk("wander")
    assert "destination-out" in wander and "bgTurnBack" in wander


def test_the_new_styles_are_registered_everywhere_a_style_is():
    settings = SETTINGS.read_text(encoding="utf-8")
    text = BG_ART.read_text(encoding="utf-8")
    assert '"wander"' in settings and '"drift"' in settings
    assert re.search(r"\bwander: \[", settings) and re.search(r"\bdrift: \[", settings)
    assert re.search(r"\bwander: [0-9.]+", text.split("const BG_ART_COST")[1])
    assert re.search(r"\bdrift: [0-9.]+", text.split("const BG_ART_COST")[1])


def test_the_long_pause_reuses_the_still_capture():
    text = BG_ART.read_text(encoding="utf-8")
    assert "function bgArtMountStill(" in text
    assert text.count("toBlob(") == 1  # one capture path, shared
    pause = text[text.index("function bgArtApplyPause") : text.index("function bgArtCovered")]
    assert "BG_ART_FREEZE_MS" in text and "bgArtFreeze" in pause and "bgArtThaw" in pause
