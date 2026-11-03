"""The line-number gutter's look, in every place it appears (INBOX 590).

The owner, of the Capture box's column (a card-filled, rounded, bordered strip
with a 16px "1" as heavy as the text): "can you redesign and make this line
numbers column cleaner and more modern and professional?? this is the one in
the capture a note subtab but also in the other similar sections like the
note edit form and others".

What the sweep measures (`scratchpad/ui-sweeps/gutter.js`), held here as
ratchets on the source: no box of its own, figures smaller than the text and
of one width, each centred on the row it counts, and the caret's line marked.
"""

from __future__ import annotations

from tests._app_js import documents_text

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = documents_text()
CSS = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "css").glob("*.css")))


def _rule(selector: str) -> str:
    """Every declaration block whose selector list is exactly `selector`."""
    out = []
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", CSS):
        selectors = [s.strip() for s in re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S).split(",")]
        if selectors == [selector]:
            out.append(match.group(2))
    return "\n".join(out)


def _function(name: str) -> str:
    start = DOCS.index(f"function {name}(")
    return DOCS[start : DOCS.index("\n}\n", start)]


def test_the_textarea_column_draws_no_box_and_smaller_figures():
    body = _rule(".doc-gutter")
    assert "border: 0;" in body and "border-radius: 0;" in body
    assert "background: transparent;" in body
    assert "font-size: var(--text-xs);" in body
    assert "font-variant-numeric: tabular-nums;" in body
    assert "text-align: right;" in body
    # The old box, gone for good.
    assert "var(--glass-border)" not in body and "background: var(--card)" not in body
    assert "color: var(--ink)" in _rule(".doc-gutter-current")


def test_the_column_copies_rows_from_the_box_not_its_type():
    """A copied font size made the figures as big as the text; only what
    places a row (line height and vertical padding) is the box's."""
    props = DOCS[DOCS.index("const DOC_GUTTER_PROPS = [") :]
    props = props[: props.index("];")]
    assert re.findall(r'"(\w+)"', props) == ["lineHeight", "paddingTop", "paddingBottom"]


def test_the_caret_line_is_marked_in_the_textarea_column():
    render = _function("renderDocGutter")
    assert "doc-gutter-current" in render and "document.activeElement === box" in render
    mount = _function("mountGutterFor")
    assert '"focus", "blur"' in mount


def test_the_editor_views_number_themselves_with_the_same_look():
    theme = _function("docCmTheme")
    block = theme[theme.index('".cm-lineNumbers .cm-gutterElement"') :]
    block = block[: block.index("}")]
    # 0.8em figures in a 2em line box: 1.6 of the text's size, its own row.
    assert 'fontSize: "0.8em"' in block and 'lineHeight: "2em"' in block
    assert 'fontVariantNumeric: "tabular-nums"' in block
    assert '"&.cm-focused .cm-activeLineGutter": { color: "var(--text)" }' in theme
    assert "highlightActiveLineGutter()" in _function("docCmGutter")
    gutter = _function("noteSurfaceGutter")
    assert "lineNumbers()" in gutter and "highlightActiveLineGutter()" in gutter
    assert "noteGutterSlot" in _function("noteSurfaceExtensions")
    assert "noteGutterSlot.reconfigure(" in _function("applyDocGutter")


def test_one_column_of_numbers_once_the_editor_mounts():
    assert ".gutter-wrap:has(> .note-surface > .cm-editor) > .doc-gutter" in CSS


def test_the_caret_line_is_washed_only_while_the_numbers_show():
    """INBOX 651: `highlightActiveLine()` rides with the gutter, never alone."""
    assert "highlightActiveLine()" in _function("docCmGutter")
    assert "highlightActiveLine()" in _function("noteSurfaceGutter")
    theme = _function("docCmTheme")
    # Half the veil (INBOX 684: "a little too strong").
    assert '"&.cm-focused .cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--hover-veil) 50%, transparent)" }' in theme
    # Nowhere else adds the extension, so numbers off means no line carries the class.
    assert DOCS.count("CM.view.highlightActiveLine()") == 2


# The capture box reserves the gutter column from first paint (INBOX 803).


def _front_css(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_the_capture_box_holds_its_line_number_column_from_first_paint():
    # INBOX 803: the gutter mounts with documents.js on the box's first focus,
    # and the text jumped 38.8px right when it did.
    css = _front_css("07-whiteboard-misc.css")
    rule = ':root[data-note-gutter="on"] .note-composer > textarea#entry-content {'
    block = css[css.index(rule):].split("}", 1)[0]
    assert "margin-inline-start: calc(2.1ch + var(--space-4) + var(--space-3))" in block
    assert "width: calc(100% - 2.1ch - var(--space-4) - var(--space-3))" in block
    settings = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    assert 'root.dataset.noteGutter = prefs.get("doc-gutter", null) === "1"' in settings
    documents = documents_text()
    # Turning Line numbers on or off moves the reserve with it.
    assert 'document.documentElement.dataset.noteGutter = on ? "on" : "off";' in documents
