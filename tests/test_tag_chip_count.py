"""A tag chip on a note card says how many notes carry the tag (L-world-class-47).

The count comes from the notes the client already holds (`allEntries`), so there is no new
route; it is the chip's hover title, not visible text, to keep cards quiet. `tagUseCount`
runs in node on a small list.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

CARDS = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "entry-card.js").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    begin = CARDS.index(start)
    return CARDS[begin : CARDS.index(end, begin) + len(end)]


def _run(tail: str):
    node = shutil.which("node")
    if not node:  # pragma: no cover
        pytest.skip("node is not available")
    script = "let allEntries = [];\nfunction tagAddChipKind() {}\n" + _block("tagAddChipKind.carrying = (tag) => {", "\n};\n") + tail
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_count_is_notes_carrying_the_tag_once_each():
    got = _run(
        'allEntries = [{tags:["a","b"]},{tags:["a","a"]},{tags:[]},{}];'
        'process.stdout.write(JSON.stringify([tagAddChipKind.carrying("a"), tagAddChipKind.carrying("b"), tagAddChipKind.carrying("zzz")]));'
    )
    assert got == [2, 1, 0]


def test_the_count_follows_a_replaced_or_longer_list():
    got = _run(
        'allEntries = [{tags:["a"]}]; const first = tagAddChipKind.carrying("a");'
        'allEntries = [{tags:["a"]},{tags:["a"]}]; const grown = tagAddChipKind.carrying("a");'
        'allEntries = [{tags:["b"]},{tags:["b"]}]; const swapped = tagAddChipKind.carrying("a");'
        "process.stdout.write(JSON.stringify([first, grown, swapped]));"
    )
    assert got == [1, 2, 0]


def test_the_chip_title_carries_it_and_the_help_says_so():
    assert "const carrying = tagAddChipKind.carrying(tag);" in CARDS
    assert "notes carry" in CARDS
    guide = (Path(__file__).resolve().parent.parent / "src" / "tessellate" / "ai" / "help_topics_more_mid.py").read_text(encoding="utf-8")
    assert "hover a tag chip on a note card to see how" in guide
