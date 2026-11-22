"""Audit 1028 low rows closed in the 1102 sweep (a30i): one pin per row.

Each test names its row. The numbers behind them are in
docs/roadmap/agent-remaining/audit-1028-ranked.md, next to the row.
"""

from __future__ import annotations

from tests._app_js import frontend_text
import json
import re
from pathlib import Path

import pytest

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


def _js_function(path: str, name: str) -> str:
    """The source of one top-level function, by brace matching (no braces in its strings)."""
    text = (ROOT / "frontend" / "js" / path).read_text(encoding="utf-8")
    start = text.index(f"function {name}(")
    depth, i = 0, text.index("{", start)
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[start : j + 1]
    raise AssertionError(name)


def _node(script: str) -> str:
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout.strip()


def test_e46_many_pinned_chats_leave_room_for_the_recent_ones():
    source = _js_function("sheets-selects.js", "sortConversations")
    script = (
        source
        + ";"
        + "const pins = Array.from({length: 9}, (_, i) => ({id: i, pinned: true}));"
        "const rest = Array.from({length: 6}, (_, i) => ({id: 100 + i, pinned: false}));"
        "const out = sortConversations([...pins, ...rest], 'recent', 8);"
        "const few = sortConversations([...pins.slice(0, 2), ...rest], 'recent', 8);"
        "const none = sortConversations(pins, 'recent', 8);"
        "console.log(JSON.stringify([out.map((c) => c.id), few.map((c) => c.id), none.length]));"
    )
    out, few, none = json.loads(_node(script))
    assert out == [0, 1, 2, 3, 4, 100, 101, 102]  # five pinned, the newest three recents
    assert few == [0, 1, 100, 101, 102, 103, 104, 105]  # two pinned leave six rows to the rest
    assert none == 8


def test_k29_an_async_route_touches_its_database_session_only_in_a_thread():
    # One blocking SQLite call in an `async def` route stalls every SSE stream
    # on the loop. A route that takes a Session hands it to run_in_threadpool
    # or asyncio.to_thread, never calls a helper with it directly.
    import ast

    offenders = []
    for path in sorted((ROOT / "src" / "tessellate" / "api").glob("routes_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            sessions = {
                a.arg
                for a in fn.args.args + fn.args.kwonlyargs
                if a.annotation is not None and "Session" in ast.unparse(a.annotation)
            }
            if not sessions:
                continue
            threaded = set()
            for call in ast.walk(fn):
                if isinstance(call, ast.Call) and ast.unparse(call.func).endswith(("run_in_threadpool", "to_thread")):
                    for node in ast.walk(call):
                        if isinstance(node, ast.Name):
                            threaded.add(id(node))
            for node in ast.walk(fn):
                if isinstance(node, ast.Name) and node.id in sessions and id(node) not in threaded:
                    offenders.append(f"{path.name}:{node.lineno} {fn.name} uses {node.id} on the loop")
    assert not offenders, offenders


def test_k16_spaces_are_documented_as_organisation_not_a_boundary():
    assert "not a security boundary" in (ROOT / "docs" / "SECURITY.md").read_text()
    assert "Organisation, not a boundary" in (ROOT / "src" / "tessellate" / "core" / "database.py").read_text()


def test_b38_a_selection_nudge_saves_through_one_request():
    # wbFlushNudge (a burst of arrow presses) and the align/distribute tail both end in
    # wbSaveMany, which sends /whiteboard/items/save-many for two or more items.
    wb = frontend_text("whiteboard.js")
    flush = wb[wb.index("async function wbFlushNudge()") :]
    assert "await wbSaveMany(burst.items);" in flush[: flush.index("\n}\n")]
    assert "async function wbCommitMoves(rows, entries) {\n  //: A refused batch has reloaded the board, so there is nothing to undo.\n  if (await wbSaveMany(rows))" in wb
    assert '"/whiteboard/items/save-many", { method: "PUT"' in wb


def test_b29_map_topics_render_bold_italic_and_code_as_dom_nodes():
    wb = frontend_text("whiteboard-map.js")
    # Inline links (L375) joined bold, italic and code in the same pattern.
    assert r"const WB_MAP_INLINE = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`|" in wb
    fn = wb[wb.index("function wbMapInlineText") :]
    assert 'document.createElement(tag)' in fn[: fn.index("\n}\n")]


def test_u40_an_empty_board_ghosts_loose_cards_not_a_mind_map_tree():
    js = (ROOT / "frontend" / "js" / "map-preview.js").read_text()
    empty = js[js.index("if (!items.length) {") :][:1800]
    assert 'const isMap = board?.type === "map";' in empty
    # the branch curves are drawn for a map's ghost only
    assert "for (const child of isMap ? shape.slice(1) : [])" in empty


def test_s93_a_jump_to_a_note_that_is_not_there_says_so_and_returns_the_address():
    js = (ROOT / "frontend" / "js" / "capture-ask.js").read_text()
    flash = js[js.index("async function flashEntry(id)") :]
    missing = flash[flash.index("if (!card) {") :][:600]
    assert 'recordTabVisit("notes", "browse", "", { refine: true });' in missing
    assert 'announce("");' in missing and 'toast("No such note.")' in missing
