"""A failed lazy load is not cached (notes audit 1031, N41).

Offline, `lazyScript` resolved false and the Map kept that answer, so the
capture bar stayed dead until a reload. The loader drops a failed file (and a
failed module), and the capture bar says why instead of throwing.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
NOTES = (ROOT / "frontend" / "js" / "notes-list.js").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")

HARNESS = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const grab = (start, end) => src.slice(src.indexOf(start), src.indexOf(end));
const code = grab('const lazyFileLoads', 'const LAZY_UNUSED_END');
let online = false, appended = [];
const document = { head: { appendChild(el) { appended.push(el); setTimeout(() => (online ? el.onload() : el.onerror()), 0); el._in = true; } },
  createElement: () => ({ remove() { this._in = false; } }) };
const lazyAssetStamp = () => '';
const LAZY_MODULES = { m: ['/js/a.js', '/js/b.js'] };
const lazyModuleLoads = new Map();
eval(code + ';globalThis.lazyScript = lazyScript; globalThis.ensureModule = ensureModule;');
(async () => {
  const first = await lazyScript('/js/a.js');
  online = true;
  const second = await lazyScript('/js/a.js');
  const mod1 = await (online = false, ensureModule('m'));
  online = true;
  const mod2 = await ensureModule('m');
  console.log(JSON.stringify({ first, second, mod1, mod2, leftover: appended.filter((e) => e._in).length, total: appended.length }));
})();
"""


@node
def test_a_failed_load_is_retried_and_leaves_no_dead_tag(tmp_path):
    marker = "const LAZY_UNUSED_END"
    text = APP.replace("function ensureModule(name) {", "function ensureModule(name) {", 1)
    end = text.index("//: **The note editor's door, kept at boot.**")
    patched = tmp_path / "app-slice.js"
    patched.write_text(text[:end] + "\n" + marker + "\n", encoding="utf-8")
    runner = tmp_path / "run.js"
    runner.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(runner), str(patched)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["first"] is False
    assert got["second"] is True, "a failed file must be fetched again"
    assert got["mod1"] is False
    assert got["mod2"] is True, "a failed module must be fetched again"
    assert got["leftover"] == 2, "failed tags are removed; only the two good ones stay"


def test_the_capture_bar_checks_the_load_and_says_why():
    block = NOTES[NOTES.index("The capture bar's card is the lazy capture-card.js") :][:900]
    assert "captureCardNeedsConnection" in block
    assert 'ensureModule("captureCard")' in block
