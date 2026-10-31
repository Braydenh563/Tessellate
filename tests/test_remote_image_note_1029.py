"""Audit 1029 row 45 (N7): a picture at another address in a note.

It read "deleted" and logged four CSP errors per render, because the page's
`img-src 'self' data: blob:` refuses it. It is never requested now: the card says
so and links to it. The address test runs in node; the rest is source checks, since
the drawing needs a browser (numbers in the commit, from scratchpad/ui-sweeps).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _decl(path: str, name: str) -> str:
    text = (JS / path).read_text(encoding="utf-8")
    start = re.search(rf"^function {name}\(", text, re.M).start()
    return text[start : text.index("\n}\n", start) + 2]


@node
def test_only_an_address_that_is_not_this_app_is_remote() -> None:
    script = (
        "const location = { origin: 'http://127.0.0.1:8781' };\n"
        + _decl("notes-list.js", "isRemoteImage")
        + "\nconst urls = ['https://example.invalid/p.png?id=1', 'http://127.0.0.1:8781/media/a.png', '/media/a.png',"
        " 'staged:abc', 'data:image/png;base64,AA', 'HTTP://Example.com/x.png', 'http://127.0.0.1:8781.evil.test/x.png'];"
        + "\nconsole.log(JSON.stringify(urls.map(isRemoteImage)));"
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(done.stdout) == [True, False, False, False, False, True, True]


def test_a_remote_picture_gets_no_img_and_says_why() -> None:
    run = _decl("notes-list.js", "appendInlineRun")
    gate = run.index("isRemoteImage(imageUrl)")
    # Decided before either branch that builds an <img>, so the browser never asks for it.
    assert gate < run.index('createElement("img")')
    note = _decl("notes-list.js", "remoteImageNote")
    assert "Remote image not loaded" in note
    assert "Open link" in note
    assert 'createElement("img")' not in note
    assert "noopener noreferrer" in note
    # A picture that is gone keeps its own word; the blocked one never says "deleted".
    assert "deleted" not in note
    assert "tracker" not in note


def test_the_image_notes_share_one_class() -> None:
    css = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "css").glob("*.css"))
    assert ".entry-image-note {" in css
    assert "entry-inline-image-deleted" not in css
    assert "entry-inline-image-deleted" not in (JS / "notes-list.js").read_text(encoding="utf-8")


def test_no_other_thumbnail_asks_the_web_either() -> None:
    """The dashboard's rows (and the chat sources and history rows that share
    `noteRowImage`) and the Library's cards made the same four CSP errors for
    a note's first remote picture; they now skip it and fall through to an
    attachment or no thumbnail."""
    row = _decl("dashboard.js", "noteRowImage")
    assert "!isRemoteImage(embedded.url)" in row
    card = (JS / "library.js").read_text(encoding="utf-8")
    assert "!isRemoteImage(item.thumb_url)" in card


def test_the_picker_preview_and_the_board_card_skip_a_remote_picture_too() -> None:
    """Review of the round: `notePickThumb` (the picker's pane) took any https
    address, and a board's note card took the Library's `thumb_url`, which the
    route returns as written. Both ask the web, and the page refuses, so each
    logged a CSP error; both now fall through (an attachment, or no picture)."""
    pick = _decl("note-pick-preview.js", "notePickThumb")
    assert "isRenderableUrl(inline[1]) && !isRemoteImage(inline[1])" in pick
    board = (JS / "whiteboard.js").read_text(encoding="utf-8")
    assert "entry.thumb_url && !isRemoteImage(entry.thumb_url)" in board
