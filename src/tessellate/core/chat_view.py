"""How the sidebar lists saved chats: the sort, the grouping and whether pinned chats lead
(L-world-class-180). Kept on the server in one preference so the page's menu and the agent's
`edit_chats` tool change the same thing, and so it survives a browser change."""

from __future__ import annotations

KEY = "chat_list_view"
SORTS = ("recent", "oldest", "name", "messages")
GROUPS = ("none", "day", "week", "folder")


def clean(stored) -> dict:  # noqa: ANN001
    """`stored` with each field checked, so a hand-edited preference reads as the default."""
    stored = stored if isinstance(stored, dict) else {}
    return {
        "sort": stored.get("sort") if stored.get("sort") in SORTS else "recent",
        "group": stored.get("group") if stored.get("group") in GROUPS else "none",
        "pinned": stored["pinned"] if isinstance(stored.get("pinned"), bool) else True,
    }


def read(config) -> dict:  # noqa: ANN001
    return clean(config.get_preference(KEY, None))


def write(config, **changes) -> dict:  # noqa: ANN001
    """The view with `changes` saved (an unknown or invalid value reads as the default); returns it."""
    view = clean({**read(config), **{k: v for k, v in changes.items() if v is not None}})
    config.set_preference(KEY, view)
    return view
