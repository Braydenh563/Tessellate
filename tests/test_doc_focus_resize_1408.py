"""The document editor's side panels are resizable in focus mode (INBOX 1408).

Measured in the real app by `scratchpad/ui-sweeps/docfocusresize.js`: the
sidebar's grip drawn 11px wide beside a 320px panel, a drag of +80 gives 400px,
-400 stops at the 170px floor, the width is the windowed sidebar's own, and the
suggestions panel's grip widens it from 320 to 400. What this holds is the
wiring those numbers depend on, so a later edit cannot quietly hide a grip.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_the_sidebar_grip_is_not_hidden_in_focus_mode() -> None:
    css = _read("frontend", "css", "07-whiteboard-misc.css")
    start = css.index(".doc-sidebar > .sidebar-collapse-toggle,")
    selectors = css[css.rfind("}", 0, start) + 1 : css.index("{", start)]
    assert "sidebar-resize" not in selectors, "the grip must stay drawn in focus mode"


def test_the_sidebar_width_is_the_one_the_windowed_grip_sets() -> None:
    js = _read("frontend", "js", "sheets-selects.js")
    assert '--doc-focus-sidebar-w' in js and 'aside.id === "doc-sidebar"' in js


def test_the_suggestions_grip_is_placed_in_focus_mode_and_hidden_on_a_phone() -> None:
    css = _read("frontend", "css", "library-lazy.css")
    assert "#tab-documents.doc-focus .doc-prose-resize.sidebar-resize {\n  position: fixed;" in css
    assert "#tab-documents.doc-focus .doc-prose-resize {\n  display: none;" not in css
    js = _read("frontend", "js", "documents.js")
    assert "applyDocProseDock();" in js.split('tab.classList.toggle("doc-focus", on);')[1][:300]
