"""Saved chats as the agent sees them: list them sorted and grouped, pin one.

The chat list's own controls (Sort, Group by) are the sidebar's; these two
tools are the same choices for a turn, so "sort my chats by length" and "pin
the trip chat" work from the composer. Listing only reads. Pinning is an add
tool (it flips a flag and its card carries the Undo), the same class as
`pin_note`.

Listing is `search_chat_history` with `sort` or `group_by` and no query: a
tool of its own tipped the 32k window's schema budget.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError, _clip, _limit_arg
from tessellate.core import deps
from tessellate.core.config import user_now
from tessellate.core.database import Conversation

#: The sidebar's sorts (frontend `sortConversations`), plus the oldest first.
CHAT_SORTS = ("recent", "oldest", "turns", "tokens", "alpha")
#: The sidebar's Group by choices, plus "pinned", which the list always keeps first.
CHAT_GROUPS = ("none", "pinned", "day", "month", "size")


def _facts(conversation: Conversation) -> dict:
    try:
        messages = json.loads(conversation.messages)
    except ValueError:
        messages = []
    return {
        "id": conversation.id,
        "title": conversation.title,
        "pinned": bool(conversation.pinned),
        "updated_at": conversation.updated_at.isoformat(),
        "turns": len(messages) // 2,
        "tokens": sum(int(m.get("tokens") or 0) for m in messages if isinstance(m, dict)),
    }


def _local(iso: str, now: datetime) -> datetime:
    moment = datetime.fromisoformat(iso)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(now.tzinfo)


def _group_name(chat: dict, group_by: str, now: datetime) -> str:
    if chat["pinned"]:
        return "Pinned"
    if group_by == "pinned":
        return "Other chats"
    if group_by == "size":
        turns = chat["turns"]
        return "Short (1 to 2 turns)" if turns <= 2 else "Medium (3 to 8 turns)" if turns <= 8 else "Long (9 or more turns)"
    moment = _local(chat["updated_at"], now)
    if group_by == "month":
        return moment.strftime("%B %Y")
    gap = (now.date() - moment.date()).days
    return "Today" if gap <= 0 else "Yesterday" if gap == 1 else moment.date().isoformat()


def _list_chats(session: Session, args: dict) -> dict:
    """The saved chats, sorted and optionally grouped. Read-only."""
    sort = str(args.get("sort") or "recent").strip().lower()
    group_by = str(args.get("group_by") or "none").strip().lower()
    if sort not in CHAT_SORTS:
        raise ToolError(f"sort is one of {', '.join(CHAT_SORTS)}.")
    if group_by not in CHAT_GROUPS:
        raise ToolError(f"group_by is one of {', '.join(CHAT_GROUPS)}.")
    limit = _limit_arg(args, default=20)
    rows = session.scalars(select(Conversation).where(Conversation.archived_at.is_(None)))
    chats = [_facts(c) for c in rows]
    if args.get("pinned_only"):
        chats = [c for c in chats if c["pinned"]]
    #: Two stable passes: the sort, then pinned on top (the sidebar's rule).
    by, newest_first = {
        "recent": (lambda c: c["updated_at"], True), "oldest": (lambda c: c["updated_at"], False),
        "turns": (lambda c: c["turns"], True), "tokens": (lambda c: c["tokens"], True),
        "alpha": (lambda c: c["title"].casefold(), False),
    }[sort]
    chats.sort(key=by, reverse=newest_first)
    chats.sort(key=lambda c: not c["pinned"])
    total = len(chats)
    chats = chats[:limit]
    result: dict = {"total": total, "shown": len(chats), "sort": sort, "group_by": group_by}
    if group_by == "none":
        result["chats"] = chats
    else:
        now = user_now(deps.get_config())
        groups: dict[str, list[dict]] = {}
        for chat in chats:
            groups.setdefault(_group_name(chat, group_by, now), []).append(chat)
        result["groups"] = [{"name": name, "chats": members} for name, members in groups.items()]
    result["label"] = f"ph:chats Listed {total} {'chat' if total == 1 else 'chats'}, {sort}" + (
        f", grouped by {group_by}" if group_by != "none" else ""
    )
    return result


def _pin_chat(session: Session, args: dict) -> dict:
    """Pin a saved chat to the top of the chat list, or unpin it. Organising,
    not using: `updated_at` is written back as it was, so the chat keeps its
    place by date (the same rule as `PUT /conversations/{id}/pin`)."""
    try:
        chat_id = int(args.get("chat_id"))
    except (TypeError, ValueError):
        raise ToolError("chat_id is the chat's id number; search_chat_history lists them.") from None
    conversation = session.get(Conversation, chat_id)
    if conversation is None or conversation.archived_at is not None:
        raise ToolError(f"There is no saved chat with id {chat_id}; search_chat_history lists them.")
    pinned = bool(args.get("pinned", True))
    if pinned != bool(conversation.pinned):
        session.execute(
            update(Conversation).where(Conversation.id == chat_id).values(pinned=pinned, updated_at=conversation.updated_at)
        )
        session.commit()
        session.refresh(conversation)
    return {
        "id": chat_id, "title": conversation.title, "pinned": bool(conversation.pinned),
        "label": f"ph:push-pin {'Pinned' if pinned else 'Unpinned'} chat: {_clip(conversation.title, 50)}",
        "undo": {"tool": "pin_note", "arguments": {"chat_id": chat_id, "pinned": not pinned}},
    }


def _search_chat_history(session: Session, args: dict) -> dict:
    """The `search_chat_history` tool: a list of the saved chats when it is given a sort or a grouping and no query,
    the search otherwise."""
    from tessellate.ai.tools.tool_skills import _search_chat_history as _search

    if not str(args.get("query") or "").strip() and any(args.get(k) for k in ("sort", "group_by", "pinned_only")):
        return _list_chats(session, args)
    return _search(session, args)
