"""Settings, Tools it can use, grouped by what a tool does (CHAT_PLAN,
INBOX 71): the catalog names each tool's group, and the list draws a head
per group (`scratchpad/ui-sweeps/ai1005-toolgroups.js` measures it)."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai import tools

GROUPS = {"read", "write", "confirm", "online"}


def test_every_tool_has_one_of_the_four_groups(app_state):
    catalog = {row["name"]: row for row in tools.tool_catalog()}
    assert {row["group"] for row in catalog.values()} <= GROUPS
    assert catalog["search_notes"]["group"] == "read"
    assert catalog["create_note"]["group"] == "write"
    assert catalog["delete_note"]["group"] == "confirm"
    assert catalog["web_search"]["group"] == "online"


def test_a_write_is_never_filed_as_a_read(app_state):
    for row in tools.tool_catalog():
        if row["name"] in tools.WRITE_TOOLS:
            assert row["group"] != "read", row["name"]


def test_the_list_draws_the_heads_and_the_filter_reads_only_tool_rows():
    """The heads are drawn in settings-controls.js (`renderTools`, moved out of
    skills.js with the pane); the filter that skips them stays in skills.js."""
    js_dir = Path(__file__).resolve().parents[1] / "frontend" / "js"
    drawn = (js_dir / "settings-controls.js").read_text(encoding="utf-8")
    assert "tool-group-head" in drawn and "setting-subhead" in drawn
    filtered = (js_dir / "skills.js").read_text(encoding="utf-8")
    assert "li[data-tool]" in filtered
