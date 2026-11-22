"""`edit_chats`: sort and group the sidebar's chat list, and rename, pin or file a saved chat in a folder
(L-world-class-180). The sort and grouping are one server-held view (`core/chat_view`) the sidebar reads, so a
sentence, a card's Confirm and the menu all change the same thing; each result carries the Undo that puts the
earlier state back."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError, ToolSpec
from tessellate.core import chat_view, deps
from tessellate.core.database import Conversation

ACTIONS = ("sort", "group", "rename", "pin", "unpin", "move")
_SORT_WORDS = {"recent": "most recent first", "oldest": "oldest first", "name": "by name", "messages": "most messages first"}
_GROUP_WORDS = {"none": "not grouped", "day": "grouped by day", "week": "grouped by week", "folder": "grouped by folder"}


def match_chats(session: Session, text: str) -> list[Conversation]:
    """The live chats `text` names: by id, then by an exact title, then by words of a title."""
    text = str(text or "").strip()
    if text.isdigit() and (row := session.get(Conversation, int(text))) is not None and row.archived_at is None:
        return [row]
    live = select(Conversation).where(Conversation.archived_at.is_(None)).order_by(Conversation.updated_at.desc())
    rows = [c for c in session.scalars(live) if text.lower() in (c.title or "").lower()]
    return [c for c in rows if (c.title or "").lower() == text.lower()] or rows


def find_chat(session: Session, ref) -> Conversation:  # noqa: ANN001
    """A chat by id, or by the words of its title (the one it names, never a guess between two)."""
    text = str(ref or "").strip()
    if not text:
        raise ToolError("Say which chat: its id, or words from its title")
    rows = match_chats(session, text)
    if len(rows) != 1:
        raise ToolError(_no_single_chat(text, rows))
    return rows[0]


def _no_single_chat(text: str, rows: list) -> str:
    if not rows:
        return f"No saved chat matches “{text}”"
    return f"{len(rows)} chats match “{text}”: " + "; ".join(f"{c.id} {c.title[:40]}" for c in rows[:5])


def _organise(session: Session, chat: Conversation, **values) -> None:  # noqa: ANN003
    """Filing is organising, not using: `updated_at` is passed back as it was, so the chat keeps its place by date."""
    session.execute(update(Conversation).where(Conversation.id == chat.id).values(updated_at=chat.updated_at, **values))
    session.commit()
    session.refresh(chat)


def _undo(**arguments) -> dict:  # noqa: ANN003
    return {"tool": "edit_chats", "arguments": arguments}


def _view_change(action: str, args: dict) -> dict:
    config = deps.get_config()
    before = chat_view.read(config)
    value = str(args.get(action) or "").strip().lower()
    allowed = chat_view.SORTS if action == "sort" else chat_view.GROUPS
    if value not in allowed:
        raise ToolError(f"{action} is one of: " + ", ".join(allowed))
    view = chat_view.write(config, **{action: value})
    words = (_SORT_WORDS if action == "sort" else _GROUP_WORDS)[value]
    return {"view": view, "label": f"ph:sort-descending Chats are {words}", "undo": _undo(action=action, **{action: before[action]})}


def _rename(session: Session, chat: Conversation, args: dict) -> dict:
    name = chat.title
    title = " ".join(str(args.get("title") or "").split())[:120]
    if not title:
        raise ToolError("title is the chat's new name")
    _organise(session, chat, title=title)
    return {"id": chat.id, "title": title, "label": f"ph:pencil-simple Renamed the chat “{name[:50]}” to “{title[:50]}”", "undo": _undo(action="rename", chat=str(chat.id), title=name)}


def _pin(session: Session, chat: Conversation, pinned: bool) -> dict:
    _organise(session, chat, pinned=pinned)
    return {"id": chat.id, "pinned": pinned, "label": f"ph:push-pin {'Pinned' if pinned else 'Unpinned'} the chat “{chat.title[:50]}”", "undo": _undo(action="unpin" if pinned else "pin", chat=str(chat.id))}


def _move(session: Session, chat: Conversation, args: dict) -> dict:
    folder = " ".join(str(args.get("folder") or "").split())[:60]
    old = chat.folder or ""
    _organise(session, chat, folder=folder)
    where = f"into the folder “{folder}”" if folder else "out of its folder"
    return {"id": chat.id, "folder": folder, "label": f"ph:folder Moved the chat “{chat.title[:50]}” {where}", "undo": _undo(action="move", chat=str(chat.id), folder=old)}


def _edit_chats(session: Session, args: dict) -> dict:
    action = str(args.get("action") or "").strip().lower()
    if action not in ACTIONS:
        raise ToolError("action is one of: " + ", ".join(ACTIONS))
    if action in ("sort", "group"):
        return _view_change(action, args)
    chat = find_chat(session, args.get("chat"))
    if action == "rename":
        return _rename(session, chat, args)
    if action == "move":
        return _move(session, chat, args)
    return _pin(session, chat, action == "pin")


EDIT_CHATS = ToolSpec(
    "edit_chats",
    "Sort, group, rename, pin or file saved chats.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ACTIONS)},
            "sort": {"type": "string", "enum": list(chat_view.SORTS)},
            "group": {"type": "string", "enum": list(chat_view.GROUPS)},
            "chat": {"type": "string"},
            "title": {"type": "string"},
            "folder": {"type": "string"},
        },
        "required": ["action"],
    },
    _edit_chats,
)
