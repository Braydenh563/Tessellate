"""Sorting, grouping and filing the saved chats (L-world-class-180): the view route, the folder route,
the `edit_chats` tool with its Undo, the sentences that reach it, and the sidebar's own ordering code."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import chat_acts
from tessellate.ai.tools import tool_chats
from tessellate.ai.tools._common import ToolError
from tessellate.core import chat_view, deps
from tessellate.core.database import Conversation

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _chat(client, question: str) -> dict:
    return client.post("/conversations", json={"question": question, "answer": "Fine."}).json()


def test_the_view_starts_plain_and_keeps_what_is_put(client):
    first = client.get("/conversations/view").json()
    assert first == {"sort": "recent", "group": "none", "pinned": True}
    put = client.put("/conversations/view", json={"sort": "name", "group": "week"}).json()
    assert put == {"sort": "name", "group": "week", "pinned": True}
    kept = client.get("/conversations/view").json()
    assert kept == put
    unpinned = client.put("/conversations/view", json={"pinned": False}).json()
    assert unpinned["sort"] == "name"


def test_an_unknown_sort_is_refused_or_ignored_never_stored(client):
    client.put("/conversations/view", json={"sort": "sideways"})
    stored = client.get("/conversations/view").json()
    assert stored["sort"] in chat_view.SORTS


def test_a_folder_is_stored_listed_and_keeps_the_chats_place_by_date(client):
    made = _chat(client, "Plan the Paris trip")
    before = client.get(f"/conversations/{made['id']}").json()["updated_at"]
    filed = client.put(f"/conversations/{made['id']}/folder", json={"folder": "  Trips "})
    assert filed.status_code == 200
    listed = client.get("/conversations").json()[0]
    assert listed["folder"] == "Trips"
    after = client.get(f"/conversations/{made['id']}").json()["updated_at"]
    assert after == before


def test_the_tool_sorts_and_groups_and_its_undo_puts_the_old_view_back(app_state):
    with deps.get_db().session() as session:
        out = tool_chats._edit_chats(session, {"action": "sort", "sort": "name"})
        assert chat_view.read(deps.get_config())["sort"] == "name"
        tool_chats._edit_chats(session, out["undo"]["arguments"])
        assert chat_view.read(deps.get_config())["sort"] == "recent"
        grouped = tool_chats._edit_chats(session, {"action": "group", "group": "week"})
        assert grouped["view"]["group"] == "week"
        with pytest.raises(ToolError):
            tool_chats._edit_chats(session, {"action": "group", "group": "decade"})


def test_the_tool_renames_pins_and_files_a_chat_and_each_undo_restores_it(app_state):
    with deps.get_db().session() as session:
        chat = Conversation(title="Paris trip planning")
        session.add(chat)
        session.commit()
        stamp = chat.updated_at
        for args in (
            {"action": "rename", "chat": "paris", "title": "Trip plans"},
            {"action": "pin", "chat": "paris"},
            {"action": "move", "chat": "paris", "folder": "Trips"},
        ):
            before = (chat.title, chat.pinned, chat.folder)
            out = tool_chats._edit_chats(session, args)
            session.refresh(chat)
            assert (chat.title, chat.pinned, chat.folder) != before
            tool_chats._edit_chats(session, out["undo"]["arguments"])
            session.refresh(chat)
            assert (chat.title, chat.pinned, chat.folder) == before
        assert chat.updated_at == stamp, "filing is not using the chat"


def test_two_chats_that_match_are_never_guessed_between(app_state):
    with deps.get_db().session() as session:
        session.add_all([Conversation(title="Paris flights"), Conversation(title="Paris hotels")])
        session.commit()
        with pytest.raises(ToolError, match="2 chats match"):
            tool_chats.find_chat(session, "paris")
        assert tool_chats.find_chat(session, "flights").title == "Paris flights"


@pytest.mark.parametrize(
    "text, intent",
    [
        ("sort my chats by name", "chat_sort"),
        ("sort my chats by most messages", "chat_sort"),
        ("group my chats by week", "chat_group"),
        ("rename the chat about Paris to Trip plans", "chat_rename"),
        ("pin the chat about Paris", "chat_pin"),
        ("move the chat about Paris to the folder Trips", "chat_folder"),
    ],
)
def test_the_sentences_are_read(text, intent):
    assert chat_acts.read(text)["intent"] == intent


@pytest.mark.parametrize("text", ["sort my notes by name", "group my notes by week", "pin the note about Paris", "chat about Paris"])
def test_a_sentence_about_notes_is_not_a_chat_act(text):
    assert chat_acts.read(text) is None


def _node(script: str) -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    return subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=30).stdout.strip()


def _ordering_script(body: str) -> str:
    source = (JS / "chat-order.js").read_text(encoding="utf-8")
    start = source.index("function sortConversations(")
    stub = (
        "const RECENT_CHATS_SHOWN = 8; const parseServerTime = (t) => (t ? new Date(t) : null);"
        "let chatView = { sort: 'recent', group: 'none', pinned: true };"
    )
    return stub + source[start : source.index("//: A group's heading row")] + ";" + body


def _rows(group: str, sort: str = "recent", pinned: bool = True) -> list:
    chats = [
        {"id": 1, "title": "Zeta", "pinned": False, "folder": "Work", "turns": 2, "updated_at": "2026-11-20T10:00:00", "last_at": "2026-11-20T10:00:00"},
        {"id": 2, "title": "alpha", "pinned": True, "folder": "", "turns": 9, "updated_at": "2026-11-01T10:00:00", "last_at": "2026-11-01T10:00:00"},
        {"id": 3, "title": "Mid", "pinned": False, "folder": "", "turns": 5, "updated_at": "2026-11-10T10:00:00", "last_at": "2026-11-10T10:00:00"},
    ]
    script = _ordering_script(
        f"const now = new Date('2026-11-21T12:00:00');"
        f"const rows = chatListRows({json.dumps(chats)}, {{ sort: '{sort}', group: '{group}', pinned: {str(pinned).lower()} }}, 50);"
        "console.log(JSON.stringify(rows.map((r) => r.heading ? 'H:' + r.heading : r.id)));"
    )
    return json.loads(_node(script))


def test_ungrouped_rows_follow_the_sort_with_pinned_first():
    assert _rows("none", "name") == [2, 3, 1]
    assert _rows("none", "messages") == [2, 3, 1]
    assert _rows("none", "oldest") == [2, 3, 1]
    assert _rows("none", "name", pinned=False) == [2, 3, 1]
    assert _rows("none", "recent", pinned=False) == [1, 3, 2]


def test_grouping_by_week_and_folder_puts_a_heading_before_each_group():
    by_folder = _rows("folder")
    assert by_folder == ["H:Pinned", 2, "H:Work", 1, "H:No folder", 3]
    heads = [r for r in _rows("week") if isinstance(r, str)]
    assert heads[0] == "H:Pinned" and len(heads) == 3
    days = [r for r in _rows("day") if isinstance(r, str)]
    assert days[1] == "H:Yesterday" and len(days) == 3


def test_the_lazy_view_sheet_and_script_are_the_ones_the_sidebar_loads():
    sidebar = (JS / "sheets-selects.js").read_text(encoding="utf-8")
    assert '/js/chat-order.js' in sidebar
    assert "/css/chat-order-lazy.css" in (JS / "chat-order.js").read_text(encoding="utf-8")
