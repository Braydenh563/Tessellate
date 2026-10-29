"""Ctrl+Z after an agent run takes back its last write (AGENT_SKILLS_REFORM
"Deepened 2026-10-10" row 4, WORLD_CLASS decision 53): every write the agent
makes goes on the app-wide undo stack as its tool event arrives, in Chat and
in the agent panel, and the run's own Undo stays for the whole.

The browser half was driven with `scratchpad/ui-sweeps/agentplan87.js`
against the scripted fake model; these hold the wiring and the server half.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from tests._app_js import app_js_text

APP = app_js_text()
JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _function(name: str) -> str:
    start = APP.index(f"function {name}(")
    return APP[start : APP.index("\n}\n", start)]


def test_a_write_goes_on_the_stack_with_its_undo_and_its_redo():
    body = _function("pushAgentChangeUndo")
    assert "pushUndo(" in body
    #: Undo runs the change's inverse; redo runs the call again and keeps the
    #: inverse of that run, whose ids are new.
    assert "inverse.tool" in body and "call.name" in body and "inverse = again.undo" in body


def test_chat_and_the_agent_panel_both_push_each_write():
    pushes = r"pushAgentChangeUndo\(event\??\.change, event\)"
    for name in ("chat-attach.js", "palette.js"):
        assert len(re.findall(pushes, (JS / name).read_text("utf-8"))) == 1, name


def test_a_rows_own_undo_takes_its_entry_off_the_stack():
    """Or Ctrl+Z would run the same inverse a second time."""
    body = _function("changeRow")
    assert "agentUndoActions.get(" in body and "settleUndoFromToast(" in body


def test_the_runs_own_undo_stays():
    assert "Undo the run" in APP and "undoSkillRun(span" in APP


def test_the_last_write_undone_restores_the_note_byte_equal(ai_client, fake_ollama, app_state):
    """The server half of the row's measure: the change the tool event
    carries puts the note back exactly, content, tags and pin."""
    note = ai_client.post("/entries", json={"content": "# Boiler\n\nPressure 1.5 bar.", "tags": ["home"]}).json()
    before = ai_client.get(f"/entries/{note['id']}").json()
    fake_ollama.tool_script = [[{"name": "edit_note", "arguments": {"note_id": note["id"], "content": "# Boiler\n\nPressure 2 bar."}}]]
    with ai_client.stream("POST", "/chat/stream", json={"question": "set the boiler pressure to 2 bar", "use_tools": True}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line.strip()]
    #: An edit to existing text parks for a Confirm card (audit 1029 H2); the
    #: click runs it through /chat/tools/execute, whose result carries the undo.
    park = next(e for e in events if e.get("type") == "confirm")
    ran = ai_client.post("/chat/tools/execute", json={"name": park["name"], "arguments": park["arguments"]}).json()
    assert ai_client.get(f"/entries/{note['id']}").json()["content"] != before["content"]
    undo = ran["undo"]
    ai_client.post("/chat/tools/execute", json={"name": undo["tool"], "arguments": undo["arguments"]})
    after = ai_client.get(f"/entries/{note['id']}").json()
    assert (after["content"], after["tags"], after.get("pinned")) == (before["content"], before["tags"], before.get("pinned"))
