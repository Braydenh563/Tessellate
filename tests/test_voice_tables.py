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


STANDALONE = re.compile(r"^(capture|clip|standalone-undo|theme-boot|prefs|desk-.*|companion-.*)\.js$")


def test_every_failure_toast_goes_through_the_voice():
    """L-chat-205, 211 and 255 (decision 55): no toast or toast action in any script of the app
    spells out "Couldn't ..." or "Could not ..." itself; each says it through
    `voiceLine("failed", what, why)` (about 150 literal failures in the lazy scripts moved on
    2026-11-14, the 29 boot ones the same day, with `focusFirstIn` moved to its one caller,
    notifications.js, to win the gzip bytes back: `test_static_compression`'s cap is never raised)."""
    loose = []
    calls = 0
    for path in sorted(JS.glob("*.js")):
        if STANDALONE.match(path.name):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if line.lstrip().startswith("//"):
                continue
            calls += line.count('voiceLine("failed"')
            if re.search(r"toast(?:Action)?\(", line) and re.search(r"[\"`']Could(?:n't| not) ", line):
                loose.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not loose, loose
    assert calls >= 220


def test_a_plain_success_toast_goes_through_the_voice():
    """L-chat-255: `toast("Saved.")` and its kin (a verb-first past tense, one argument, a full stop)
    say it through `voiceLine("done", what)`, so the full stop and the sentence shape are the table's."""
    plain = re.compile(r'\btoast\(\s*(["`])([A-Z][a-z]+ed\b[^"`\n]*?)\.\1\s*\)')
    loose, calls = [], 0
    for path in sorted(JS.glob("*.js")):
        if STANDALONE.match(path.name):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if line.lstrip().startswith("//"):
                continue
            calls += line.count('voiceLine("done"')
            if plain.search(line):
                loose.append(f"{path.name}:{number}: {line.strip()[:90]}")
    assert not loose, loose
    assert calls >= 66
    assert realise.say("done", what="Saved") == "Saved."
