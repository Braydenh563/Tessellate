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


def test_s67_timeline_and_notes_views_use_the_one_plural_helper():
    # timelineUnitText, timelineKindsText, the open-questions chip and the
    # suggested-links toggle each had their own `n === 1 ? "" : "s"`.
    js = ROOT / "frontend" / "js"
    for name in ("timeline.js", "notes-list.js", "note-edit-panels.js", "timeline-calendar.js"):
        for line in (js / name).read_text().split("\n"):
            # a thousands-separated count ("1,204 words") keeps its own guard
            assert '=== 1 ? "" : "s"' not in line or "toLocaleString" in line, (name, line)
    timeline = (js / "timeline.js").read_text()
    assert "return nounCount(n, unit);" in timeline
    assert "return nounCount(n, name);" in timeline


def test_s66_no_two_scripts_declare_the_same_global_name():
    # The function-only lint in test_global_scope_ratchet misses a const, let,
    # var or class declared in two scripts (the second one throws at load, or
    # in a lazy bundle, at first use).
    from collections import defaultdict

    from tests import _js_scope

    owners: dict[str, list[str]] = defaultdict(list)
    for path in sorted((ROOT / "frontend" / "js").glob("*.js")):
        if path.name.endswith("-worker.js"):
            continue  # a worker has its own scope
        for name in _js_scope.global_names(path.read_text(encoding="utf-8")):
            owners[name].append(path.name)
    twice = {n: files for n, files in owners.items() if len(files) > 1}
    assert not twice, f"declared in two scripts of the one global scope: {twice}"
