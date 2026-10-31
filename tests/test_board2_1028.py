"""Audit 1028 rows U4, U6 and B9: a non-drag reparent, the code editor under
New, and an Undo that waits for a delete still in flight.

The browser half is driven by hand (see agent-remaining/board2-1028.md); these
pin the wiring and run the pending-set logic in node.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from tests._app_js import app_js_text

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _read(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


# ---- U4: Move under... ------------------------------------------------------


def test_move_under_is_one_function_through_the_one_mover():
    src = _read("whiteboard-map.js")
    match = re.search(r"function wbMapMoveUnder\(id\) \{(.*?)\n\}\n", src, re.S)
    assert match, "wbMapMoveUnder is missing"
    body = match.group(1)
    # Reparenting goes through wbMapTransplant, which owns the cycle check
    # (/move) and the one undo step; a second writer would skip both.
    assert "wbMapTransplant(" in body
    # A topic cannot go under itself or its own branch.
    assert "wbMapSubtree(" in body
    assert "pickerDialog(" in body


def test_move_under_is_in_menu_palette_and_command_table():
    assert 'sub("Move under…"' in _read("whiteboard.js")
    assert "wbMapMoveUnder(node.id)" in _read("whiteboard-map.js")
    commands = _read("whiteboard-commands.js")
    assert 'id: "move-under"' in commands
    assert "wbMapMoveUnder(" in commands


def test_move_under_is_in_the_keys_sheet_with_a_key():
    commands = _read("whiteboard-commands.js")
    assert re.search(r'id: "move-under".*keys: "M"', commands)
    assert "wbMapMoveUnder(mapNode.id)" in _read("whiteboard.js")


# ---- U6: the code editor under New ------------------------------------------


def test_code_file_is_a_create_kind_in_the_library_picker():
    lib = _read("library.js")
    assert re.search(r"\n  code: \{\s*\n\s*label: \"ph:code New code file\"", lib)
    assert re.search(r'LIBRARY_CREATE_ORDER = \[[^\]]*"document", "code"', lib)
    assert re.search(r"\n  code: \[\"ph:code\"", lib)


def test_code_file_opens_the_template_dialog_on_the_code_group():
    lib = _read("library.js")
    block = lib[lib.index("\n  code: {") :][:1200]
    assert "doc-new-template" in block
    assert "doc-template-group" in block and '"Code"' in block


def test_code_file_is_in_the_palette():
    assert "New code file" in _read("settings-panes.js")


# ---- B9: undo waits for an in-flight delete ---------------------------------


def test_undo_and_redo_wait_for_pending_deletes():
    src = _read("whiteboard.js")
    for name in ("wbUndo", "wbRedo"):
        body = src[src.index(f"async function {name}() {{") :][:400]
        assert "await wbDeleting.settled()" in body, name


@pytest.mark.skipif(shutil.which("node") is None, reason="node needed")
def test_pending_set_settles_only_when_the_last_delete_does():
    src = _read("whiteboard.js")
    match = re.search(r"class WbPendingSet extends Set \{.*?\n\}\n", src, re.S)
    assert match, "WbPendingSet is missing"
    script = textwrap.dedent(
        """
        %s
        const s = new WbPendingSet();
        const log = [];
        s.add("a"); s.add("b");
        s.settled().then(() => log.push("settled"));
        (async () => {
          await Promise.resolve();
          log.push("before");
          s.delete("a");
          await Promise.resolve();
          log.push("one left");
          s.delete("b");
          await Promise.resolve(); await Promise.resolve();
          const idle = new WbPendingSet();
          await idle.settled();
          log.push("idle ok");
          console.log(JSON.stringify(log));
        })();
        """
    ) % match.group(0)
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == ["before", "one left", "settled", "idle ok"]


def test_changed_files_still_parse():
    assert app_js_text()  # the shared-scope concatenation still builds
