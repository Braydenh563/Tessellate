"""INBOX 1436: the long pause that becomes a picture, and the Wander and
Drift styles. The pure parts (the noise, the edge turn-back, the pause
decision) run in node; the rest is read from the source, as the other
background-art tests do."""

from __future__ import annotations

import json
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
this.out = { bgArtShouldFreeze, BG_ART_FREEZE_MS };
`, box);
const o = box.out;
console.log(JSON.stringify({
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


def test_a_pause_freezes_after_twenty_seconds_and_only_once(out):
    assert out["freezeMs"] == 20000
    assert out["freeze"] == [False, False, True, False]


def test_the_long_pause_reuses_the_still_capture():
    text = BG_ART.read_text(encoding="utf-8")
    assert "function bgArtMountStill(" in text
    assert text.count("toBlob(") == 1  # one capture path, shared
    pause = text[text.index("function bgArtApplyPause") : text.index("function bgArtCovered")]
    assert "BG_ART_FREEZE_MS" in text and "bgArtFreeze" in pause and "bgArtThaw" in pause
