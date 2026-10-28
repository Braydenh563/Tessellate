"""Sweep 1028b W4, W5: a failed load says so, in words that read.

W5: `surfaceFailed(el, what, retry)` wrote "Could not load your ${what}", so
"this week's counts" read "your this week's counts" and "the library" read
"your the library". The template adds nothing now; every caller passes the
whole phrase, which starts with a determiner.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

CALL = re.compile(r"\b(?:surfaceFailed|loadSurface)\((?:[^,()]|\([^()]*\))+?,\s*\"([^\"]+)\"")
PHRASE = re.compile(r"^(?:your|the|this|what)\b")


def test_the_failure_title_adds_no_possessive():
    nav = (JS_DIR / "load-failed.js").read_text(encoding="utf-8")
    assert "`Could not load ${what}`" in nav
    assert "Could not load your" not in nav


def test_every_caller_names_a_whole_phrase():
    seen = 0
    for path in sorted(JS_DIR.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for match in CALL.finditer(text):
            seen += 1
            phrase = match.group(1)
            assert PHRASE.match(phrase), f"{path.name}: {phrase!r} reads badly in 'Could not load ...'"
            assert not re.search(r"\byour (?:the|this|what|your)\b", phrase), phrase
    assert seen >= 20
