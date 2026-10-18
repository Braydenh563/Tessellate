"""In the chat box a bare "/" shows the commands first.

INBOX 1300 C05, the owner: "I need / chat commands to be more findable,
like when I do / I wouldn't know the other's are there unless I scroll down
quite far". Measured by `scratchpad/ui-sweeps/slash1300.js`: the first
command row from 443 px down a 384 px menu (out of sight) to 27 px, active,
with ArrowDown moving to the next command.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ED = (ROOT / "frontend" / "js" / "editor.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = ED.index(f"function {name}(")
    return ED[start : ED.index("\n}\n", start) + 2]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_commands_lead_in_chat_only():
    js = _fn("editorBareSlashRows") + (
        "const g = [{id:'a',group:'Attach'},{id:'c1',group:'Commands'},{id:'c2',group:'Commands'},{id:'m',group:'Mode'}];"
        "const r = [{id:'a',group:'Recent'}];"
        "const ids = (rows) => rows.map((x) => x.group + ':' + x.id);"
        "console.log(JSON.stringify([ids(editorBareSlashRows('chat', r, g)), ids(editorBareSlashRows('note', r, g))]));"
    )
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    chat, note = json.loads(out)
    assert chat == ["Commands:c1", "Commands:c2", "Recent:a", "Attach:a", "Mode:m"]
    assert note == ["Recent:a", "Attach:a", "Commands:c1", "Commands:c2", "Mode:m"]


def test_the_bare_menu_uses_it():
    assert "items = editorBareSlashRows(context, recent, grouped);" in _fn("editorRefreshMenu")
