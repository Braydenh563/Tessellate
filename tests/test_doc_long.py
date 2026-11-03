"""Long documents in the documents editor: lints for what a static read can see.

Each test names the sweep that measures the behaviour in a browser; these hold
the shape that the measurement depends on, so a refactor cannot drop it
silently.
"""

from __future__ import annotations

from tests._app_js import documents_text

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_JS = documents_text()


def _live_plugin_update() -> str:
    start = DOCUMENTS_JS.index("docLivePluginCache = ViewPlugin.fromClass(")
    update = DOCUMENTS_JS.index("update(update) {", start)
    return DOCUMENTS_JS[update: DOCUMENTS_JS.index("decorations: (plugin)", update)]


def test_live_decorations_rebuild_when_the_parser_catches_up() -> None:
    """`doclonglive.js`: a jump into a long document drew its headings raw.

    The markdown parser works in slices, so the viewport can move somewhere
    the tree has not reached; the parser finishing sets no doc, viewport,
    selection or focus flag, so the plugin has to compare the tree itself.
    """
    body = _live_plugin_update()
    assert re.search(r"syntaxTree\(update\.startState\)\s*!==\s*syntaxTree\(update\.state\)", body), (
        "the live view's decoration plugin does not rebuild when the syntax tree changes"
    )


def test_the_breadcrumb_follows_the_view_when_the_caret_is_off_screen() -> None:
    """`doccrumbview.js`: the trail said `Top > Annual report` at 60% of a long document.

    The outline's mark already used "the caret's section while it is on
    screen, the top of the view otherwise"; the trail must be redrawn by the
    same scroll-driven pass, and every other redraw must use the same line.
    """
    start = DOCUMENTS_JS.index("function markDocOutline(known) {")
    body = DOCUMENTS_JS[start: DOCUMENTS_JS.index("\n}\n", start)]
    assert "renderDocCrumbs(" in body, "scrolling no longer redraws the breadcrumb"
    assert "docCaretLine()" in body and 'kind === "codemirror"' in body, "the textarea fallback keeps the caret"
    # The line is read once, before the outline writes (INBOX 1530 c), and
    # the same `where` goes to the mark and to both of the trail's redraws.
    assert DOCUMENTS_JS.count("const where = docWhereLine();") == 1
    assert DOCUMENTS_JS.count("renderDocCrumbs(where)") == 2 and "markDocOutline(where)" in DOCUMENTS_JS, (
        "the outline's redraws must give the trail the same line the mark uses"
    )


# The four helpers below take a DOM element. A document *surface* (the adapter
# from `docSurface()`, `docActiveBox()`, `noteSurfaceFor()`) looks like one and
# is not: `autoGrow` wrote `style.height` on it and every "/" command in the
# capture box threw, from a call site that read as correct. OPEN.md, "The
# document surface's aliases have no lint".
ELEMENT_ONLY = ("autoGrow", "mountGutterFor", "syncDocGutterMetrics", "watchDocGutter")
SURFACE_FACTORIES = ("docSurface", "docActiveBox", "noteSurfaceFor", "textareaSurface", "asSurface")


def _surface_names(text: str) -> set[str]:
    factories = "|".join(SURFACE_FACTORIES)
    pattern = rf"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:\w+\s*\?\s*)?(?:{factories})\("
    return {"surface"} | set(re.findall(pattern, text))


def _offending_calls(text: str) -> list[tuple[int, str, str]]:
    found = []
    for name in _surface_names(text):
        for helper in ELEMENT_ONLY:
            for match in re.finditer(rf"(?<!function )\b{helper}\(\s*{re.escape(name)}\s*[,)]", text):
                found.append((text.count("\n", 0, match.start()) + 1, helper, name))
    return found


def test_no_surface_is_handed_to_a_helper_that_wants_an_element() -> None:
    bad = []
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
        for line, helper, name in _offending_calls(path.read_text(encoding="utf-8")):
            bad.append(f"{path.name}:{line}: {helper}({name}) hands a surface to an element-only helper")
    assert not bad, "\n".join(bad)


def test_the_surface_lint_sees_the_shape_it_exists_for() -> None:
    """Proved against a simulated drift, so a regex that matches nothing cannot pass forever."""
    assert _offending_calls("const surface = docSurface();\nautoGrow(surface);\n") == [(2, "autoGrow", "surface")]
    assert _offending_calls("const s = noteSurfaceFor(box);\nwatchDocGutter(s);\n") == [(2, "watchDocGutter", "s")]
    assert _offending_calls("const surface = docSurface();\nautoGrow(surface.el);\n") == []


def test_a_document_reopens_where_it_was_left() -> None:
    """`docreturn.js`: a long document reopened at the top, caret 0, even after a reload.

    The place is kept per document in `localStorage` as two offsets (the caret
    and the first character in view, not a pixel count: unseen lines are
    height estimates in a fresh view), written before the surface is handed to
    another document, restored at the end of `openDocument`, and flushed when
    the page goes away.
    """
    start = DOCUMENTS_JS.index("async function openDocument(id) {")
    body = DOCUMENTS_JS[start: DOCUMENTS_JS.index("\n}\n", start)]
    assert body.index("docRememberPositionNow()") < body.index("await ensureDocEditor()"), (
        "the place being left must be written down before the surface is replaced"
    )
    assert body.rstrip().endswith("docRestorePosition(doc.id);"), "openDocument does not restore the place"
    assert 'addEventListener("pagehide", docRememberPositionNow)' in DOCUMENTS_JS
    assert "docRememberPosition();" in DOCUMENTS_JS[DOCUMENTS_JS.index("function wireDocSurfaceScroll("):]
    assert "const DOC_POSITIONS_MAX = 60;" in DOCUMENTS_JS, "the memory must stay bounded"
