"""Every inline mark the documents toolbar and the "/" menu can insert has a live render.

Reported by the owner: in Live view `<sup>`, `<sub>`, `<u>` and `++blue|text++`
showed their raw syntax while bold, code and highlight rendered. The marks were
inserted by `MD_ACTIONS` and the toolbar's "More" menu, and nothing tied that
list to `docLivePlugin`. `docLivePlugin.marks` (documents-cm.js) is the one table of
how Live draws each mark; this test reads the insert side from the JS source and
fails when a mark has no entry, so a new toolbar mark cannot ship as raw text.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _live_table() -> dict[str, str]:
    body = re.search(r"docLivePlugin.marks = Object\.freeze\(\{(.*?)\}\);", _read("documents-cm.js"), re.S)
    assert body, "docLivePlugin.marks table missing from documents-cm.js"
    return dict(re.findall(r"(\w+):\s*\"(\w+)\"", body.group(1)))


def _action_block() -> str:
    text = _read("documents.js")
    start = text.index("const MD_ACTIONS = {")
    return text[start : text.index("\n};", start)]


def _insertable_inline_marks() -> set[str]:
    """Keys of every inline mark the toolbar or the slash menu can put in the text."""
    marks: set[str] = set()
    # MD_ACTIONS entries that wrap or bracket the selection (not a line, block or custom).
    for key, spec in re.findall(r"^  (\w+): (\{.*?\}),?$", _action_block(), re.M):
        if re.search(r"\b(?:wrap|pre):", spec):
            marks.add(key)
    documents = _read("documents.js")
    # The toolbar's "More" menu rows: ["underline", "Underline"].
    menus = re.search(r"const EDITOR_TOOLBAR_MENUS = \[(.*?)\n\];", documents, re.S)
    assert menus
    marks.update(re.findall(r"\[\"(\w+)\", \"[^\"]+\"\]", menus.group(1)))
    # The colour menu writes `++colour|words++`; a run is `{{size=..|words}}`.
    if "const mark = kind === \"ink\" ? \"++\"" in documents:
        marks.add("ink")
    if "const MD_RUN = " in documents:
        marks.add("run")
    # The "/" menu's rows that call an inline MD_ACTIONS entry.
    inline_actions = {k for k in marks if k in _action_block()}
    for kind in re.findall(r"act\(\"(\w+)\"\)", _read("editor.js")):
        if kind in inline_actions:
            marks.add(kind)
    return marks


def test_every_insertable_inline_mark_has_a_live_render() -> None:
    table = _live_table()
    marks = _insertable_inline_marks()
    # Guard the extraction itself: these are the marks the owner named.
    assert {"bold", "highlight", "sup", "sub", "underline", "ink", "run"} <= marks, marks
    missing = sorted(marks - set(table))
    assert not missing, f"inline marks with no live render in docLivePlugin.marks: {missing}"


def test_live_table_names_a_real_mechanism() -> None:
    assert set(_live_table().values()) <= {"tree", "scan", "widget"}


def test_scanned_tag_marks_are_drawn_and_styled() -> None:
    cm = _read("documents-cm.js")
    theme = _read("documents-cm-theme.js")
    assert "<(sup|sub|u)>" in cm
    assert "text-ink text-ink-${match[1]}" in cm
    for cls in ("cm-md-sup", "cm-md-sub", "cm-md-u"):
        assert f'"{cls}"' in theme or f".{cls}" in theme, cls
