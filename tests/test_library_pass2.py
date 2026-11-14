"""The Library's second pass and the list conventions it brought, held.

docs/roadmap/archive/agent-remaining/pass2.md. Two kinds of check:

- `libraryTitleAndPreview` is pure string work, so it runs in node against
  the cases that were measured wrong on a seeded notebook: an untitled note
  printed its first line twice (as the title and again as the preview), and a
  document's snippet began with its own title.
- The conventions (right-click opens the row's own menu, arrows between
  cards, Shift+click ranges, Escape / Ctrl+A / Delete on a selection, the
  Library keeping its scroll) live in delegated listeners that no unit test
  reaches, so their load-bearing pieces are held here by shape, and
  `scratchpad/ui-sweeps/listconventions.js` drives them in Chromium.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_JS = ROOT / "frontend" / "js" / "library.js"
def _function_source(text: str, name: str) -> str:
    start = text.find(f"function {name}(")
    assert start != -1, f"{name} is missing"
    depth = 0
    #: The body's brace, after the parameter list: a destructured parameter
    #: (`{ vertical = false } = {}`, kebabMenu's) has braces of its own.
    i = re.compile(r"\)\s*\{").search(text, start).end() - 1
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    raise AssertionError(f"{name} never closes")


def _run_split(cases: list[tuple[str, str, bool]]) -> list[dict]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    text = LIBRARY_JS.read_text(encoding="utf-8")
    consts = "\n".join(
        m.group(0) for m in re.finditer(r"^const LIBRARY_(?:TITLE_SENTENCE_MAX|CLIPPED_TITLE) = \d+;", text, re.M)
    )
    source = consts + "\n" + _function_source(text, "libraryTitleAndPreview")
    driver = source + "\nconst cases = " + json.dumps(cases) + ";\n"
    driver += "console.log(JSON.stringify(cases.map(([t, p, c]) => libraryTitleAndPreview(t, p, c))));\n"
    out = subprocess.run([node, "-e", driver], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_an_untitled_note_is_not_printed_twice():
    text = "Call the dentist about the appointment on Thursday; ask about the retainer."
    (split,) = _run_split([(text[:60], text, True)])
    # The whole sentence is the title, and nothing is repeated under it.
    assert split == {"title": text, "preview": ""}


def test_a_long_first_sentence_keeps_the_cut_and_carries_on():
    text = " ".join(f"w{i}" for i in range(60)) + ". Second sentence here."
    cut = text[:60]
    (split,) = _run_split([(cut, text, True)])
    # The preview carries on from where the title stopped, and both stop and
    # start on a whole word: this cut lands inside "w17", and a preview that
    # opened "…7 w18" (on the Library, "…ke \"what's in") read as a glitch.
    at = cut.rstrip().rfind(" ")
    assert split["title"] == cut[:at].strip() + "…"
    assert split["preview"] == "…" + text[at:].strip()


def test_a_document_snippet_drops_its_own_title():
    (split,) = _run_split([("Design system notes", "Design system notes Surface tiers, the ramp.", False)])
    assert split == {"title": "Design system notes", "preview": "Surface tiers, the ramp."}


def test_a_preview_that_does_not_start_with_the_title_is_left_alone():
    (split,) = _run_split([("Sprint retro", "What went well: measuring.", True)])
    assert split == {"title": "Sprint retro", "preview": "What went well: measuring."}


def test_a_document_title_is_never_treated_as_clipped():
    title = "A" * 70
    (split,) = _run_split([(title, title + " body text.", False)])
    assert split == {"title": title, "preview": "body text."}


def test_the_card_grid_measures_before_it_empties():
    """Reading the grid's width after `replaceChildren()` forces a layout of an
    empty grid, which clamped the section's scroll to 0: the Library came back
    from another tab at the top every time (traced, 400 to 0)."""
    body = _function_source(LIBRARY_JS.read_text(encoding="utf-8"), "renderLibrary")
    update = body[body.index("const updateDOM"):]
    assert update.index("libraryColumnCount(grid)") < update.index("grid.replaceChildren()")


def test_every_kebab_carries_its_items_for_the_right_click():
    body = _function_source(app_js_text(), "kebabMenu")
    assert "wrap.rowMenu = { items, ariaLabel }" in body


def test_the_row_menu_has_a_long_press_twin():
    text = app_js_text()
    assert "const ROW_MENU_HOSTS" in text
    block = text[text.index("const ROW_MENU_HOSTS") : text.index("function arrowNavTarget")]
    assert 'addEventListener("contextmenu"' in block
    assert "wireLongPress(" in block and "selector: ROW_MENU_HOSTS" in block


def test_selection_keys_stand_down_inside_a_field():
    """Escape, Ctrl+A and Delete already mean something in a text field; the
    selection keys must never take them from one."""
    text = app_js_text()
    block = text[text.index("function openSelectionScope") :]
    block = block[: block.index("function renderMarkdown")]
    assert "textarea" in block and "contenteditable" in block


# --- the performance work, held by shape (numbers in pass2.md, "Performance
# by trace"; the trace is scratchpad/ui-sweeps/scrolltrace.js) -------------

CONSISTENCY_CSS = ROOT / "frontend" / "css" / "07-whiteboard-misc.css"
DOCUMENTS_JS = ROOT / "frontend" / "js" / "documents.js"


def test_the_page_scrollers_ask_for_compositor_scrolling():
    css = CONSISTENCY_CSS.read_text(encoding="utf-8")
    rule = re.search(r"main,\s*\.tab-page,\s*\.library-view-section,\s*#chat-messages,\s*\.cm-scroller\s*\{\s*will-change: scroll-position;", css)
    assert rule, "the scrollers lost `will-change: scroll-position` (raster 0.25s to 2.8s on a Notes scroll)"


def test_the_caret_readout_rewrites_its_text_in_place():
    text = DOCUMENTS_JS.read_text(encoding="utf-8")
    caret = _function_source(text, "renderDocCaret")
    assert "docSetStatusText(caret" in caret and "caret.textContent =" not in caret


def test_the_back_to_top_check_never_matches_the_whole_document():
    text = app_js_text()
    body = _function_source(text, "formPrimaryButtons")
    assert "document.querySelectorAll" not in body
