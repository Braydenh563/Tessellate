"""The Documents, code, diagram and whiteboard surfaces at every zoom (2026-11-11).

The owner: "make sure the wrapping and ui issues arent an issue anywhere else
from zoom or resolution". Measured by scratchpad/ui-sweeps/wrapzoom-docs.js
across 1280x720 to 2560x1440 at 100 to 200 %, and 768x1024. Each test pins
one defect class's fix where a static read can see it; the sweep is the
measurement.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def _at_blocks(css: str, prelude: str) -> list[str]:
    """The bodies of every at-rule whose prelude is exactly `prelude`."""
    out = []
    start = 0
    while True:
        i = css.find(prelude, start)
        if i < 0:
            return out
        j = css.index("{", i)
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append(css[j + 1 : k - 1])
        start = k


def _rule(block: str, selector_part: str) -> str:
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
        if selector_part in sel:
            return body
    return ""


# ---- a header row whose items wrap onto a second line -----------------------


def test_a_code_documents_dock_folds_its_words_before_it_wraps():
    """A code file's actions were 808px (1062 with the Python line) in a 931px
    dock at 1280, so the name took a line and the actions broke in two. Below
    75rem of dock the lesser buttons are their icons and the Python line is
    cut with an ellipsis; under 820 it leaves the row for the card's notice."""
    css = _css("library-lazy.css")
    wide = "".join(_at_blocks(css, "@container docdock (max-width: 74.99rem)"))
    assert "#tab-documents.doc-is-code .doc-ai-label" in wide
    assert "#doc-code-format > .toolbar-word" in wide
    why = _rule(wide, "#doc-code-run-why")
    assert "text-overflow: ellipsis" in why and "white-space: nowrap" in why and "max-width" in why
    assert "flex-basis: 12rem" in _rule(wide, ".doc-dock > .doc-dock-identity")
    prose = "".join(_at_blocks(css, "@container docdock (max-width: 59.99rem)"))
    assert ".doc-ai-label" in prose and "#doc-format-show > span" in prose
    narrow = "".join(_at_blocks(css, "@container docdock (max-width: 819.98px)"))
    assert "display: none" in _rule(narrow, "#doc-code-run-why")
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    # The cut line's tooltip says it whole.
    assert 'title="Install Python in Settings, Packages, to run Python files">Install Python in Settings, Packages</button>' in html


# ---- a split button breaking apart ---------------------------------------------


def test_the_side_panes_no_model_line_places_the_split_button_under_the_words():
    """offline-split.js swaps the notice's `.ghost` action for
    `.split-button.ai-offline-split`; the grid that put the action under the
    words matched only `.ghost`, so the split took column 1 and the words
    stood in 42px, one per line."""
    css = _css("library-lazy.css")
    body = _rule(css, "#doc-assist-model-line > :is(.ghost, .ai-offline-split)")
    assert "grid-column: 2" in body and "margin-inline-start: 0" in body
    js = (ROOT / "frontend" / "js" / "offline-split.js").read_text(encoding="utf-8")
    assert 'split.className = "split-button ai-offline-split"' in js


# ---- a narrow pane in a wide window -----------------------------------------------


def test_the_diagram_dock_answers_to_its_pane_not_the_window():
    """Split view at 1280 gave the builder 428px; the one-row dock's word
    drop and scroll fallback keyed on the window (under 600), so the menu sat
    22px past the pane. The pane (`.dgm`, an inline-size container) decides,
    and the scroller does not shrink in the pane's column."""
    css = _css("diagram-lazy.css")
    narrow = "".join(_at_blocks(css, "@container (max-width: 599.98px)"))
    assert "display: none" in _rule(narrow, ".dgm-kindword")
    dock = _rule(narrow, ".dgm-dock:has(> .dgm-addsplit)")
    assert "overflow-x: auto" in dock and "flex-shrink: 0" in dock


# ---- a hover bar over the content it acts on --------------------------------------


def test_the_rendered_tables_bar_has_its_own_strip_under_the_table():
    """The bar sat half over the table's bottom edge (translateY(50%)) and
    covered the last row's last cell. It now sits in a strip the block keeps
    below the table on a screen that hovers."""
    css = _css("09-editor.css")
    bar = _rule(css, "#doc-preview .md-table-block > .code-bar")
    assert "translateY" not in bar and "inset-block-end: 0" in bar
    hover = "".join(_at_blocks(css, "@media (hover: hover)"))
    assert "padding-block-end: 2.5rem" in _rule(hover, "#doc-preview .md-table-block")
