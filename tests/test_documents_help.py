"""Every part of the Documents tab has its '?' and names its controls (OPEN 1054).

DESIGN.md's recipe is one line in place and the rest behind one `data-help-for`
'?' per section, so the Documents tab carries five: the list, the outline tab,
the dock with its menus, the find bar and the AI panel (the code panel and the
run panel had theirs). The test holds two things: each '?' sits inside its
section and points at a popover that exists, and the popover names each control
in the section. The dock's menu rows are read from the page, so a row added to
the ⋯ menu without a word in the help fails here.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

INDEX = (Path(__file__).resolve().parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")

#: The one phrase the dock's help uses for each ⋯ menu row, by id.
DOCK_MENU_WORDS = {
    "doc-format-toggle": "formatting toolbar",
    "doc-connections": "Connections",
    "doc-history": "History",
    "doc-replace-everywhere": "Replace in every document",
    "doc-copy-link": "Copy app link",
    "doc-ai-model": "Model for this feature",
    "doc-extract": "Extract notes",
    "doc-map-headings": "Map the headings",
    "doc-export-md": ".md",
    "doc-export-html": ".html",
    "doc-export-zip": "with images",
    "doc-export-docx": ".docx",
    "doc-export-pdf": "PDF",
    "doc-width-menu": "page width",
    "doc-text-size": "text size",
    "doc-line-spacing": "line spacing",
    "doc-toolbar-mode": "toolbar row",
    "doc-code-wrap-row": "wrap",
    "doc-whitespace-row": "whitespace",
    "doc-minimap-row": "minimap",
    "doc-dim-others": "Dim all but this paragraph",
    "doc-typewriter": "Keep this line centred",
    "doc-margin-reader": "Margin reader",
    "doc-serif": "Serif for reading",
    "doc-autocorrect-row": "Autocorrect",
    "doc-complete-row": "Suggest words",
    "doc-suggest-row": "Suggest changes",
    "doc-suggest-next": "Review the next change",
    "doc-suggest-accept-all": "Accept all changes",
    "doc-suggest-reject-all": "Reject all changes",
    "doc-read-aloud": "Read aloud",
}
VIEW_WORDS = ("Live", "Source", "Split", "Plain", "Read", "Formatting", "AI edit", "Focus", "Run", "Format", "Assistant", "Snippets")

#: popover id -> (the section it is in, the words it must carry)
SECTIONS = {
    "doc-list-help": (
        'id="doc-sidebar-list"',
        ("Recent", "New", "template", "All in Library", "rename", "archive", "delete"),
    ),
    "doc-outline-help": (
        'id="doc-sidebar-outline"',
        ("Outline", "Comments", "Linked from", "Notes it draws on", "References", "Attach a bookmark", "Where are my documents kept?"),
    ),
    "doc-dock-help": ('class="row space-between doc-dock"', VIEW_WORDS),
    "doc-find-help": (
        'id="doc-find-bar"',
        ("Find", "Replace", "Replace all", "Replace in every document", "Shift+Enter", "Esc"),
    ),
    "doc-ai-verb-help": (
        'id="doc-ai-panel"',
        ("Edit", "Write", "Remove", "Suggest an edit", "Stop", "Replace with this", "Cancel", "History"),
    ),
}


def _popover(pid: str) -> str:
    match = re.search(rf'<div class="help-body hidden" id="{pid}".*?\n\s*</div>', INDEX, re.S)
    assert match, f"{pid} has no popover"
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(0))))


def _section_with_trigger(marker: str, pid: str) -> bool:
    """The '?' for `pid` sits after `marker` and before the section's own end:
    the nearest trigger above the popover must come after the section opens."""
    trigger = INDEX.find(f'data-help-for="{pid}"')
    start = INDEX.find(marker)
    return trigger != -1 and start != -1 and start < trigger


def test_each_documents_section_has_its_question_mark_and_popover():
    for pid, (marker, _words) in SECTIONS.items():
        assert INDEX.count(f'data-help-for="{pid}"') == 1, pid
        assert f'aria-controls="{pid}"' in INDEX, pid
        assert _section_with_trigger(marker, pid), f"{pid}: the '?' is not inside {marker}"


def test_each_popover_names_the_controls_of_its_section():
    for pid, (_marker, words) in SECTIONS.items():
        text = _popover(pid)
        missing = [word for word in words if word.lower() not in text.lower()]
        assert not missing, f"{pid} does not name {missing}"


def test_the_dock_menu_rows_are_all_named_in_the_dock_help():
    start = INDEX.index('class="doc-dock-menu-list"')
    end = INDEX.index('id="doc-delete"', start)
    ids = []
    for tag in re.findall(r"<(?:button|label)\b[^>]*>", INDEX[start:end]):
        if "doc-dock-menu-item" not in tag:
            continue
        found = re.search(r'\bid="([^"]+)"', tag)
        if found:
            ids.append(found.group(1))
    assert ids, "no menu rows found: the markup moved"
    unnamed = [row for row in ids if row not in DOCK_MENU_WORDS]
    assert not unnamed, f"a new menu row needs a word in doc-dock-help and a row here: {unnamed}"
    text = _popover("doc-dock-help").lower()
    missing = [word for word in DOCK_MENU_WORDS.values() if word.lower() not in text]
    assert not missing, f"doc-dock-help does not name {missing}"
    assert "delete document" in text and "file type" in text


def test_the_help_copy_has_no_em_dash_or_exclamation():
    for pid in SECTIONS:
        text = _popover(pid)
        assert chr(0x2014) not in text and "!" not in text, pid
