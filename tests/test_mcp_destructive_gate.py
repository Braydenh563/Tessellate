"""An outside agent over MCP can never run a destructive tool (L-world-class-12).

The in-app agent shows a confirm card before a destructive call; an outside
client has no card, so the server does not offer those tools at all, with
writes switched on or off, and every other change needs the writes switch.
`tests/test_mcp_server.py` checks the first destructive tool; these check all
of them, both switch states, and that a note really survives a `delete_note`
sent by name.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate import mcp_server
from tessellate.ai import tools
from tessellate.mcp_server import handle_request, offered_tools

DESTRUCTIVE = sorted(name for name, spec in tools.TOOLS.items() if spec.destructive)


def _call(name: str, arguments: dict | None = None) -> dict:
    return handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}
    )["result"]


def test_there_are_destructive_tools_to_guard():
    assert {"delete_note", "delete_tag", "merge_categories"} <= set(DESTRUCTIVE)


@pytest.mark.parametrize("writes", [False, True])
def test_no_destructive_tool_is_offered_or_run_by_name(app_state, writes):
    app_state.set_preference("mcp_writes_enabled", writes)
    assert not {spec.name for spec in offered_tools()} & set(DESTRUCTIVE)
    listed = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert not {tool["name"] for tool in listed} & set(DESTRUCTIVE)
    for name in DESTRUCTIVE:
        result = _call(name)
        assert result["isError"] is True, name
        assert "Unknown or unavailable" in result["content"][0]["text"], name


def test_a_note_survives_delete_note_sent_by_name_with_writes_on(app_state):
    from tessellate.core import deps
    from tessellate.core.database import Entry

    app_state.set_preference("mcp_writes_enabled", True)
    created = _call("create_note", {"content": "keep me"})
    assert created["isError"] is False
    session = deps.get_db().session()
    try:
        note_id = session.query(Entry).filter(Entry.content == "keep me").one().id
    finally:
        session.close()
    refused = _call("delete_note", {"id": note_id})
    assert refused["isError"] is True
    session = deps.get_db().session()
    try:
        kept = session.get(Entry, note_id)
        assert kept is not None and not kept.is_deleted
    finally:
        session.close()


def test_every_other_changing_tool_waits_for_the_writes_switch(app_state):
    """The agent's own change tools that are not flagged destructive (renames,
    edits, unlinking) are still writes: refused until the switch is on."""
    changing = sorted(name for name in tools.CHANGE_TOOLS if name in tools.TOOLS and not tools.TOOLS[name].destructive)
    assert "edit_note" in changing
    app_state.set_preference("mcp_writes_enabled", False)
    offered = {spec.name for spec in offered_tools()}
    for name in changing:
        if name in offered:
            # A tool the server counts read-only (an audit) is allowed; a write is not.
            assert mcp_server._is_read_only(tools.TOOLS[name]), name
        else:
            assert _call(name)["isError"] is True, name
    assert {"edit_note", "rename_tag", "rename_category", "unlink_notes", "save_skill"} <= set(changing) - offered


def test_the_resources_path_runs_only_two_reads():
    """`_run_tool` skips the offer check, so it must only ever be called with a reader."""
    source = Path(mcp_server.__file__).read_text(encoding="utf-8")
    called = set(re.findall(r'_run_tool\("([a-z_]+)"', source))
    assert called == {"list_notes", "get_note"}
    assert all(mcp_server._is_read_only(tools.TOOLS[name]) for name in called)
