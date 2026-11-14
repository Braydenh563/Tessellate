"""Capture's formatting strip is the shape it ends up in from its first paint.

At 390 the strip drew expanded (two rows, 104px) and then, when the Library
bundle landed and `applyDocToolbarCollapsed` ran, folded to the one-row
collapsed bar (54px): a 50px shift under the reader's thumb, caused by the
fold, the "Formatting" name and the tools group (More, layout, line numbers,
the chevron) all living in that bundle. The collapsed shape is the default
(`docToolbarCollapsed`: collapsed unless the saved choice is "0"), so it is the
markup's, and boot code undoes it for a saved "0". The name is drawn by a
`::before` until the bundle mounts the real one, so the swap moves nothing.
The measurement is `scratchpad/ui-sweeps/capturestrip.js`.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_the_capture_strip_is_collapsed_in_the_markup():
    html = _read("frontend", "index.html")
    tag = re.search(r'<div class="([^"]*)" id="note-toolbar"', html)
    assert tag, "the capture strip's opening tag changed shape"
    assert "is-collapsed" in tag.group(1).split()


def test_boot_code_unfolds_it_for_a_saved_expanded_choice():
    boot = _read("frontend", "js", "notes-list.js")
    body = boot.split("function foldNoteToolbarForFirstPaint() {", 1)[1].split("\n}\n", 1)[0]
    # The same key and the same default as the bundle's own reading.
    key = re.search(r'const DOC_TOOLBAR_COLLAPSED_KEY = "([^"]+)"', _read("frontend", "js", "documents.js")).group(1)
    assert f'"{key}"' in body
    assert '?? "1") === "1"' in body
    assert 'classList.toggle("is-collapsed"' in body


def test_the_name_is_drawn_until_the_real_one_is_mounted():
    css = "".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))
    rule = re.search(r"\.doc-toolbar\.is-collapsed:not\(:has\(\.doc-toolbar-tools\)\)::before\s*\{([^}]*)\}", css)
    assert rule, "no pre-mount name for a collapsed strip"
    assert 'content: "Formatting"' in rule.group(1)


# The folded capture strip opens when its word is pressed (owner 2026-10-10).


def test_the_folded_capture_strip_opens_when_pressed():
    """"The note capture subtab formatting toolbar wont open". Measured: before
    the box was focused the strip held only Source and the drawn word
    "Formatting", a label with nothing to press; a press on the word now
    focuses the box and the strip opens (Bold, Italic, ... 30 tools). The
    press goes through `startNewNote`, the one path that shows Capture before
    focusing (tests/test_note_making.py), so the box is never focused hidden."""
    lst = frontend_text("notes-list.js")
    body = lst[lst.index("function foldNoteToolbarForFirstPaint() {") :][:1500]
    assert 'startNewNote();' in body


def test_the_strip_is_wired_once_the_notes_surface_is_built():
    """Measured 2026-11-12 against the running app: pressing the folded strip did
    nothing (0 `startNewNote` calls, strip still 40px with only Source), because
    `#note-toolbar` is in the Notes surface's template and does not exist when
    notes-list.js loads, so the call at load found no bar and bound nothing. The
    string test above passed over a handler that never ran. It runs on the
    surface's build now."""
    lst = frontend_text("notes-list.js")
    assert "\nfoldNoteToolbarForFirstPaint();\n" not in lst
    assert 'onSurface("notes", foldNoteToolbarForFirstPaint);' in lst
