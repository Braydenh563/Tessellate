"""Audit 1028 low rows closed in the 1102 sweep (a30i): one pin per row.

Each test names its row. The numbers behind them are in
docs/roadmap/agent-remaining/audit-1028-ranked.md, next to the row.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "frontend" / "css"


def _rule(text: str, selector: str) -> str:
    start = text.index(selector + " {")
    return text[start : text.index("}", start)]


def test_u44_find_panel_labels_sit_on_the_type_scale():
    # CodeMirror sets `& label { font-size: 80% }` (11.776px at 14.72px) on a
    # scoped class; the app's rule has to beat it, so it names .cm-editor.
    body = _rule((CSS / "library-lazy.css").read_text(), ".doc-editor .cm-editor .cm-panel.cm-search label")
    assert "font-size: var(--text-xs)" in body


def test_u39_template_row_reserves_room_for_the_check():
    # The check is 16px wide, 8px in from the row's edge; the old 20px of
    # right padding let a full-width hint run 1px under it.
    css = (CSS / "05-sidebars-themes.css").read_text()
    row = _rule(css, "button.ghost.doc-template-choice")
    assert re.search(r"padding: var\(--space-2\) var\(--space-9\) var\(--space-2\) var\(--space-3\)", row)
