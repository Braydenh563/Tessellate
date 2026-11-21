"""A map topic in an exported picture (L-world-class-413, exportcolours.js).

Two faults, both seen in the PNG: the label was wrapped at a fixed 7.5px a letter, so a 22px
root title ("Export colours light", box 200 wide) ran on one line past its box and came out
cut at "Export colours lig"; and every topic drew a 4px left bar, so the root (no spine on
the board, data-spine "none") wore a stray stripe across its rounded end. Measured on the
board: root border-left 1px (the rim), a child 4px; label 22px and 17px.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-export.js").read_text(encoding="utf-8")


def _wrap_source():
    m = re.search(r"\n  function wbSvgWrapLines\(.*?\n  \}\n", SRC, re.S)
    assert m, "wbSvgWrapLines moved"
    return m.group(0)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_22px_root_title_wraps_inside_its_box():
    level = 22
    script = _wrap_source() + f"console.log(JSON.stringify(wbSvgWrapLines('Export colours light', 200 - 28, 4, {level} * 0.55)));"
    lines = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert lines == ["Export colours", "light"]
    # Each line fits the box at the label's own size (0.55em a letter).
    assert all(len(line) * level * 0.55 <= 172 for line in lines)


def test_the_topic_label_wraps_at_its_own_size():
    assert "wbMapLabel(obj), size.w - 28 - (textLeft - 14), 4, level * 0.55)" in SRC
    assert "wbMapLabel(obj), size.w - 28 - (textLeft - 14), 4, 7.5)" not in SRC


def test_the_spine_is_read_off_the_drawn_topic():
    assert '`<rect width="4" height="${size.h}" rx="2"' not in SRC, "a fixed bar on every topic is back"
    assert re.search(r"spine: el \?.*getComputedStyle\(el\)\) : \{ side: \"left\", width: 4", SRC, re.S)
    assert "if (Math.abs(left - top) < 1) return null;" in SRC
