"""The app speaks in one voice (CHAT_PLAN decision 55, section 2's toasts
row): system copy moves onto the realiser's voice table surface by surface.
First the three surfaces with the most toasts (library.js 119, whiteboard.js
104, whiteboard-map.js 72): every failure is `voiceLine("failed", ...)`,
"Couldn't ..." in one register. The copy lint: no toast says "!" or "Oops"
anywhere in the app."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import realise

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
MOVED = ("library.js", "whiteboard.js", "whiteboard-map.js")


def _js_voice() -> dict:
    src = (JS / "status.js").read_text(encoding="utf-8")
    body = src[src.index("const VOICE = {"):src.index("};", src.index("const VOICE = {"))]
    return dict(re.findall(r'^\s*(\w+): "((?:[^"\\]|\\.)*)",', body, re.M))


def test_the_browsers_voice_is_the_realisers():
    assert _js_voice() == realise.VOICE


def test_the_realiser_says_a_failure_in_one_register():
    assert realise.say("failed", what="open that document") == "Couldn't open that document."
    assert realise.say("failed", what="save", why="the disk is full") == "Couldn't save: the disk is full"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_says_it_the_same():
    src = (JS / "status.js").read_text(encoding="utf-8")
    table = src[src.index("const VOICE = {"):src.index("};", src.index("const VOICE = {")) + 2]
    start = src.index("function voiceLine(")
    fn = src[start:src.index("\n}\n", start) + 2]
    script = table + "\n" + fn + '\nconsole.log(JSON.stringify([voiceLine("failed", "open that document"), voiceLine("failed", "save", "the disk is full")]));'
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, check=True)
    assert json.loads(out.stdout) == ["Couldn't open that document.", "Couldn't save: the disk is full"]


def test_the_moved_surfaces_fail_in_the_voice():
    calls = 0
    for name in MOVED:
        src = (JS / name).read_text(encoding="utf-8")
        calls += src.count('voiceLine("failed", ')
        for line in src.split("\n"):
            if "toast(" in line:
                assert not re.search(r'["`]Could not ', line), f"{name}: {line.strip()}"
                assert not re.search(r'"Couldn\'t [^"$`]*"', line), f"{name}: a failure not through the voice: {line.strip()}"
    assert calls >= 66  # 67 until whiteboard-map.js lost "put it back" to the shared undo


def test_no_toast_in_the_app_says_oops_or_shouts():
    found = []
    for path in sorted(JS.glob("*.js")):
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            for said in re.findall(r'toast(?:Action)?\(\s*["\'`]([^"\'`]*)', line):
                if "Oops" in said or re.search(r"!(?=\s|$)", said):
                    found.append(f"{path.name}:{number}: {said}")
    assert not found, found


def test_every_lazy_failure_toast_goes_through_the_voice():
    """L-chat-205 and 211 (decision 55): no toast or toast action in a lazily
    loaded script spells out "Couldn't ..." or "Could not ..." itself; each says
    it through `voiceLine("failed", what, why)` (about 150 literal failures moved
    on 2026-11-14). The 29 boot scripts keep their literals: the table call
    cost about 100 bytes gzipped there, over the boot cap
    (`test_static_compression`), which is never raised."""
    from tests._app_js import app_js_files

    boot = {path.name for path in app_js_files()}
    loose = []
    calls = 0
    for path in sorted(JS.glob("*.js")):
        if path.name in boot:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if line.lstrip().startswith("//"):
                continue
            calls += line.count('voiceLine("failed"')
            if re.search(r"toast(?:Action)?\(", line) and re.search(r"[\"`']Could(?:n't| not) ", line):
                loose.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not loose, loose
    assert calls >= 200
