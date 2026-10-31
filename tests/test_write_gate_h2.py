"""Audit 1029 H2: the Agent tip says it asks before it changes or removes
something, so a write that changes or removes what the person already wrote
parks for a Confirm card, on the server, whatever the model was told. A write
that only adds runs and carries its Undo. `tools.CHANGE_TOOLS` and
`tools.ADD_TOOLS` hold the classes; every write tool is in exactly one.
"""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import agent, tools

from tests.test_injection_fence import _FakeModels, _FakeOllama, _Session


def _run(monkeypatch, calls):
    ran: list[str] = []

    def execute(session, name, arguments, **kwargs):
        ran.append(name)
        return {"ok": True, "label": name}

    monkeypatch.setattr(agent.tools, "ollama_tools", lambda allowed=None: [])
    monkeypatch.setattr(agent.tools, "execute_tool", execute)
    fake = _FakeOllama([calls, []])
    events = list(agent.run_agent(_Session(), "tidy my notes", [], _FakeModels(), fake))
    return ran, [e["name"] for e in events if e.get("type") == "confirm"]


def test_a_write_that_changes_existing_text_parks_with_nothing_outside_read(monkeypatch, app_state):
    ran, confirms = _run(monkeypatch, [
        {"name": "edit_note", "arguments": {"note_id": 5, "content": "replaced"}},
        {"name": "rename_tag", "arguments": {"old": "a", "new": "b"}},
        {"name": "unlink_notes", "arguments": {"note_a": 1, "note_b": 2}},
    ])
    assert ran == [], ran
    assert confirms == ["edit_note", "rename_tag", "unlink_notes"], confirms


def test_a_write_that_only_adds_runs_without_a_card(monkeypatch, app_state):
    ran, confirms = _run(monkeypatch, [
        {"name": "create_note", "arguments": {"content": "Buy oat milk"}},
        {"name": "tag_note", "arguments": {"note_id": 1, "add": ["home"]}},
    ])
    assert ran == ["create_note", "tag_note"], ran
    assert confirms == []


def test_removing_a_tag_parks_but_adding_one_does_not():
    assert tools.needs_confirm("tag_note", {"note_id": 1, "remove": ["x"]})
    assert not tools.needs_confirm("tag_note", {"note_id": 1, "add": ["x"]})
    assert tools.needs_confirm("delete_note", {})
    assert not tools.needs_confirm("get_note", {})


def test_every_write_tool_is_in_one_class():
    destructive = {n for n, s in tools.TOOLS.items() if s.destructive}
    changes = set(tools.CHANGE_TOOLS)
    adds = set(tools.ADD_TOOLS)
    assert not (destructive & changes) and not (changes & adds) and not (destructive & adds)
    unclassed = tools.WRITE_TOOLS - destructive - changes - adds
    assert not unclassed, unclassed
    assert changes <= tools.WRITE_TOOLS and adds <= tools.WRITE_TOOLS


def test_the_settings_group_says_which_tools_ask_first():
    groups = {row["name"]: row["group"] for row in tools.tool_catalog()}
    assert groups["edit_note"] == "confirm" and groups["delete_note"] == "confirm"
    assert groups["create_note"] == "write"


def test_the_tip_matches_the_gate():
    text = Path("frontend/js/chat.js").read_text("utf-8")
    assert "says so before it does" not in text
    assert "asks before changing a note" in text
