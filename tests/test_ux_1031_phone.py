"""Audit 1031 class 47 (HR14, SH19, AI16): the phone's long panes, the strip past the edge.

HR14: Settings has a jump list on a phone (`#settings-jump`, group options
under each long pane) and the Tools pane's 72 switches have one switch a group.
SH19: the "unnamed button at r=474" was the Notes sub-tab "Questions" inside a
strip that scrolls; measured at 390 on every tab and every Settings section,
each strip wider than its box is an `.edge-fade` with a mask. A strip added
later says the same or is measured to fit and listed here.
AI16: the off-canvas phone sidebar is `inert`."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Static strips with two to five short tabs (13 to 29 letters in all), measured
# to fit a 390 px phone with room to spare. A wider one fades and scrolls.
FITS_AT_390 = {
    "activity-tabs",
    "wb-template-kind",
    "note-picker-sources",
    "doc-code-side-tabs",
    "wb-format-tabs",
    "skills-tabs",
    "tasks-tabs",
}


def _text(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_a_strip_in_the_page_fades_or_is_measured_to_fit():
    html = _text("frontend", "index.html")
    loose = set()
    for tag in re.findall(r"<[a-z]+\b[^>]*\bclass=\"[^\"]*\btabs-line\b[^\"]*\"[^>]*>", html, re.S):
        name = re.search(r'\bid="([^"]+)"', tag)
        if "edge-fade" not in tag:
            loose.add(name.group(1) if name else tag[:60])
    assert loose <= FITS_AT_390, f"a strip that may scroll has no fade: {sorted(loose - FITS_AT_390)}"


def test_the_off_canvas_sidebar_is_inert_until_it_opens():
    text = _text("frontend", "js", "sheets-selects.js")
    assert 'aside.inert = phone && !aside.classList.contains("sidebar-sheet-open")' in text


def test_settings_has_a_jump_list_with_the_groups_of_a_long_pane():
    find = _text("frontend", "js", "settings-find.js")
    assert "function settingsIndexJump(name, heads)" in find
    assert "row.value = `${name}#${i}`" in find
    # A pane of three groups or more has one, whatever the window's height.
    assert "if (heads.length < 3 || !scroller)" in find


def test_a_tool_group_turns_all_off_or_all_on_in_one_save():
    js = _text("frontend", "js", "settings-controls.js")
    assert 'all.className = "linklike tool-group-all"' in js
    save = js.split("async function saveToolGroup(", 1)[1].split("\n}\n", 1)[0]
    # One request for the group, the boxes follow the answer, a failure puts them back.
    assert save.count('apiJson("/preferences"') == 1
    assert "disabled_tools" in save and "check.checked" in save and "catch" in save
    # Only the rows on screen, so a filter is never overstepped.
    assert 'classList.contains("hidden")' in js.split("function toolGroupBoxes(", 1)[1].split("\n}\n", 1)[0]
    assert "toolGroupBoxes(head.dataset.group)" in save
    # Named for its group, and the words flip with the state.
    assert "Turn all off" in js and "Turn all on" in js
    assert "aria-label" in js.split("function toolGroupAllPaint(", 1)[1].split("\n}\n", 1)[0]


def test_the_guide_says_a_group_has_its_own_switch():
    more = _text("src", "tessellate", "ai", "help_topics_more.py") + _text("src", "tessellate", "ai", "help_topics_more_mid.py")
    body = more.split('"id": "tools-setting"', 1)[1].split('"badge"', 1)[0]
    assert "Turn all off" in body
    text = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', body.split('"body": (', 1)[1]))
    assert len(text) <= 1900, len(text)
