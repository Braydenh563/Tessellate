"""Sh1 P22: the map's New note popup has the head's '?' (DESIGN.md, a dialog's head).

The popup (`#graph-new`) was the one graph popup with a title and a close but no
help: what happens to what is typed (saved as typed, filed in the background,
Private seals it) was nowhere on screen. The '?' sits right beside the title,
before the all-icon group, as in the Documents AI panel's head.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _popup() -> str:
    start = HTML.index('<div id="graph-new"')
    return HTML[start : HTML.index('<div id="graph-zoom"', start)]


def test_the_new_note_head_carries_a_help_button_between_the_title_and_the_actions():
    block = _popup()
    head = block[: block.index('id="graph-new-hint"')]
    assert head.index('id="graph-new-title"') < head.index("data-help-for=") < head.index('class="dialog-head-actions"')
    button = re.search(r"<button[^>]*data-help-for=\"graph-new-help\"[^>]*>", head, re.S)
    assert button, "the '?' names its help body"
    tag = button.group(0)
    assert 'aria-controls="graph-new-help"' in tag and 'aria-expanded="false"' in tag
    assert "aria-label=" in tag and "title=" in tag
    assert "dialog-head-btn" in tag and "icon-only" in tag


def test_the_help_body_exists_once_hidden_and_says_what_happens_to_the_note():
    block = _popup()
    assert block.count('id="graph-new-help"') == 1
    body = re.search(r'<div class="help-body hidden" id="graph-new-help"[^>]*>(.*?)</div>', block, re.S)
    assert body, "a hidden .help-body"
    text = body.group(1)
    assert "Private" in text and "files it in the background" in text
    assert "!" not in text and chr(0x2014) not in text


def test_the_guide_points_at_it():
    source = (ROOT / "src" / "tessellate" / "ai" / "help_topics_core_tail.py").read_text(encoding="utf-8")
    assert "? says more" in source
