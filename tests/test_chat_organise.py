"""L-world-class-180: sort, group and pin saved chats from the agent, and the
chat list's Group by control. The model is a fake transport; the clock is fixed."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from tessellate.ai import agent, tools
from tessellate.core.database import Conversation
from tests._clock import pin_clock
from tests.test_injection_fence import _FakeModels, _FakeOllama, _Session

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _chat(session, title, turns, days_ago, pinned=False, tokens=0):
    messages = []
    for i in range(turns):
        messages += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}", "tokens": tokens}]
    when = (NOW - timedelta(days=days_ago)).replace(tzinfo=None)
    row = Conversation(title=title, messages=json.dumps(messages), pinned=pinned, created_at=when, updated_at=when)
    session.add(row)
    session.commit()
    return row


@pytest.fixture()
def chats(session, monkeypatch):
    pin_clock(monkeypatch, NOW)
    return {
        "trip": _chat(session, "Trip plan", 12, 40, tokens=50),
        "tax": _chat(session, "Tax questions", 2, 0, tokens=10),
        "dinner": _chat(session, "Dinner ideas", 5, 1, pinned=True, tokens=300),
        "bike": _chat(session, "Bike repair", 1, 1, tokens=5),
    }


def _titles(result):
    return [c["title"] for c in result["chats"]]


def test_sorts_keep_pinned_first(session, chats):
    out = tools.execute_tool(session, "search_chat_history", {"sort": "turns"})
    assert _titles(out) == ["Dinner ideas", "Trip plan", "Tax questions", "Bike repair"]
    assert _titles(tools.execute_tool(session, "search_chat_history", {"sort": "alpha"})) == ["Dinner ideas", "Bike repair", "Tax questions", "Trip plan"]
    assert _titles(tools.execute_tool(session, "search_chat_history", {"sort": "oldest"}))[-1] == "Tax questions"
    assert _titles(tools.execute_tool(session, "search_chat_history", {"sort": "tokens"}))[1] == "Trip plan"


def test_group_by_day_month_size_and_pinned(session, chats):
    day = tools.execute_tool(session, "search_chat_history", {"group_by": "day"})
    assert [g["name"] for g in day["groups"]] == ["Pinned", "Today", "Yesterday", "2026-10-12"]
    month = tools.execute_tool(session, "search_chat_history", {"group_by": "month"})
    assert [g["name"] for g in month["groups"]] == ["Pinned", "November 2026", "October 2026"]
    size = tools.execute_tool(session, "search_chat_history", {"group_by": "size", "sort": "turns"})
    assert [g["name"] for g in size["groups"]] == ["Pinned", "Long (9 or more turns)", "Short (1 to 2 turns)"]
    pinned = tools.execute_tool(session, "search_chat_history", {"group_by": "pinned"})
    assert [g["name"] for g in pinned["groups"]] == ["Pinned", "Other chats"]


def test_pinned_only_and_a_bad_sort(session, chats):
    assert _titles(tools.execute_tool(session, "search_chat_history", {"pinned_only": True})) == ["Dinner ideas"]
    assert "error" in tools.execute_tool(session, "search_chat_history", {"sort": "sideways"})


def test_pinning_keeps_the_date_and_carries_an_undo(session, chats):
    before = chats["trip"].updated_at
    out = tools.execute_tool(session, "pin_note", {"chat_id": chats["trip"].id})
    session.refresh(chats["trip"])
    assert chats["trip"].pinned is True and chats["trip"].updated_at.replace(tzinfo=None) == before
    assert out["undo"] == {"tool": "pin_note", "arguments": {"chat_id": chats["trip"].id, "pinned": False}}
    tools.execute_tool(session, "pin_note", out["undo"]["arguments"])
    session.refresh(chats["trip"])
    assert chats["trip"].pinned is False
    assert "error" in tools.execute_tool(session, "pin_note", {"chat_id": 9999})


def test_pinning_a_chat_is_an_add_tool_and_listing_a_read():
    assert "pin_note" in tools.ADD_TOOLS
    assert "search_chat_history" not in tools.WRITE_TOOLS
    assert tools.needs_confirm("pin_note", {"chat_id": 1})
    assert not tools.needs_confirm("search_chat_history", {})


def test_a_turn_about_chats_is_offered_both_tools(monkeypatch, app_state):
    from tests.test_harness_tiers import _rounds

    first, _forced = _rounds(monkeypatch, "List the chat list grouped by day and pin the longest chat")[0]
    assert {"search_chat_history", "pin_note"} <= set(first), first


def test_a_fake_model_pins_a_chat_and_the_turn_parks_for_confirm(monkeypatch, app_state):
    ran: list[str] = []
    monkeypatch.setattr(agent.tools, "ollama_tools", lambda allowed=None: [])
    monkeypatch.setattr(agent.tools, "execute_tool", lambda session, name, arguments, **kw: ran.append(name) or {"ok": True, "label": name})
    fake = _FakeOllama([[{"name": "pin_note", "arguments": {"chat_id": 1}}], []])
    events = list(agent.run_agent(_Session(), "pin this chat", [], _FakeModels(), fake))
    assert [e["name"] for e in events if e.get("type") == "confirm"] == ["pin_note"]


def test_the_group_control_is_lazy_and_persisted():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend"
    lazy = (root / "js" / "chat-groups.js").read_text(encoding="utf-8")
    assert lazy.lstrip().split("\n", 2)[-1].lstrip().startswith("(() => {") or "(() => {" in lazy
    assert "Object.assign(window, { chatGroups })" in lazy
    assert 'prefs.set("chatSidebarGroup"' in lazy and "kebabMenu(" in lazy
    boot = (root / "js" / "sheets-selects.js").read_text(encoding="utf-8")
    assert 'lazyScript("/js/chat-groups.js")' in boot
    assert "chat-groups.js" not in (root / "index.html").read_text(encoding="utf-8")
