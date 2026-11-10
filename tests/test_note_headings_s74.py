"""S74: a note with three or more headings has a Headings row in its card's menu.

The row opens a sheet of jump links (the Contents recipe, `mdTocElement`); a link
opens the card out and scrolls the heading's `.note-heading` span (drawn by
`renderNoteText`) to the top. Measured in the running app: Section 4 at top 1524.5
px before, 365.5 px after, in a 900 px window.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
MENU = (JS / "entry-menu.js").read_text(encoding="utf-8")
LIST = (JS / "notes-list.js").read_text(encoding="utf-8")


def _block(text: str, head: str) -> str:
    start = text.index(head)
    ends = [text.find(close, start) + len(close) for close in ("\n}\n", "\n};\n") if text.find(close, start) >= 0]
    return text[start : min(ends)]


def test_the_menu_row_is_offered_only_from_three_headings_and_opens_the_sheet():
    assert "fillEntryMenu.headingCount(entry) >= 3" in MENU
    assert 'label: "ph:list-dashes Headings"' in MENU and "fillEntryMenu.headings(entry)" in MENU
    sheet = _block(MENU, "fillEntryMenu.headings = async function")
    assert 'name: "note-headings"' in sheet and "mdTocElement()" in sheet and "fillEntryMenu.jump(" in sheet
    assert "innerHTML" not in sheet


def test_a_heading_line_on_the_card_is_a_span_the_jump_can_find():
    assert 'className: "note-heading"' in LIST


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(
    ("entry", "want"),
    [
        ({"content": "# T\n\n## a\n\n## b\n\n## c", "title": "T"}, 3),
        ({"content": "# T\n\n## a\n\n## b", "title": "T"}, 2),
        ({"content": "## a\n## b\n## c\n```\n# x\n```"}, 3),
        ({"content": "start", "content_truncated": True, "heading_count": 4, "title": "T"}, 3),
        ({"content": "start", "content_truncated": True}, 0),
    ],
)
def test_the_count_leaves_out_the_title_line_and_code_fences(entry, want):
    script = (
        "const MD_CODE_FENCE = /^\\s*(```|~~~)/;\n"
        + _block((JS / "markdown.js").read_text(encoding="utf-8"), "function mdTocEntries(")
        + "const fillEntryMenu = {};\nconst stripFrontmatter = (t) => t;\n"
        + "const bodyWithoutTitleLine = (t) => t.split('\\n').slice(1).join('\\n');\n"
        + _block(MENU, "fillEntryMenu.headingCount = function")
        + "process.stdout.write(String(fillEntryMenu.headingCount(JSON.parse(process.argv[1]))));"
    )
    out = subprocess.run(["node", "-e", script, json.dumps(entry)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    assert int(out.stdout) == want
