"""Writes to saved settings go through `prefs.set` (WORLD_CLASS_PLAN F1, "Left: the writes").

Reads are held by test_prefs_module.py. This is the write side as a ratchet:
each file may make no more direct `localStorage.setItem` calls than it makes
today, and a file not listed may make none. Move a write onto `prefs.set` and
lower its number; never raise one. `prefs.js` is the door and is not counted.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
SET = re.compile(r"localStorage\.setItem\(")

#: file -> direct setItem calls on 2026-10-11.
CAPS = {
    # A new file, not a raised count: the one-time origin carry copies the old
    # origin's raw storage bytes and its marker before prefs.js is loaded.
    "origin-bridge.js": 2,
}


def _code(text: str) -> str:
    return "\n".join(
        "" if line.lstrip().startswith(("//", "*", "/*")) else line for line in text.splitlines()
    )


def _found() -> dict[str, int]:
    out = {}
    for path in sorted(JS.glob("*.js")):
        if path.name == "prefs.js":
            continue
        n = len(SET.findall(_code(path.read_text(encoding="utf-8"))))
        if n:
            out[path.name] = n
    return out


def test_no_file_writes_storage_more_than_it_did():
    over = {name: n for name, n in _found().items() if n > CAPS.get(name, 0)}
    assert not over, f"write saved settings through prefs.set, not localStorage.setItem: {over}"


def test_the_caps_only_fall():
    stale = {name: cap for name, cap in CAPS.items() if _found().get(name, 0) < cap}
    assert not stale, f"lower these caps to the current count: {stale}"
