"""Acts on the saved chats in the sidebar (L-world-class-180): sort and group the list, and rename, pin or file one
chat in a folder. One sentence is one card that waits for Confirm, over the `edit_chats` tool; its Undo is
the tool's own. The reader finds the sentence, the planner resolves the chat's name. Nothing here writes.
`commands.py` lends its card helpers (`_parity_helpers`)."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

INTENTS = frozenset({"chat_sort", "chat_group", "chat_rename", "chat_pin", "chat_folder"})

_LEAD = r"^(?:(?:please|pls|can you|could you|would you)\s+)*"
_CHATS = r"(?:my |the |all )?(?:saved |sidebar )?chats?(?: list)?"
_CHAT = r"(?:the |my )?chat\s+(?:about |called |named |titled |with )?"
_SORT_OF = (
    ("name", r"name|title|alphabet\w*|a-z|a to z"),
    ("messages", r"most messages|message count|messages|most turns|turns|longest|most active|length"),
    ("oldest", r"oldest(?: first)?|earliest|first used"),
    ("recent", r"recent(?:ly used)?|newest|latest|date|last used|most recent"),
)
_SORT = re.compile(rf"{_LEAD}(?:sort|order|arrange|list|show)\s+{_CHATS}\s+(?:by|from|with)\s+(?P<s>.+)$", re.I)
_GROUP = re.compile(rf"{_LEAD}(?:group|bundle|organi[sz]e|arrange|split)\s+{_CHATS}\s+(?:by|into|per)\s+(?:a |the )?(?P<g>day|days|week|weeks|folder|folders|nothing)$", re.I)
_UNGROUP = re.compile(rf"{_LEAD}(?:ungroup|stop grouping)\s+{_CHATS}$", re.I)
_RENAME = re.compile(rf"{_LEAD}(?:rename|retitle)\s+{_CHAT}(?P<c>.+?)\s+(?:to|as)\s+(?P<t>.+)$", re.I)
_PIN = re.compile(rf"{_LEAD}(?P<v>pin|unpin)\s+{_CHAT}(?P<c>.+)$", re.I)
_FOLDER = re.compile(rf"{_LEAD}(?:move|put|file|add)\s+{_CHAT}(?P<c>.+?)\s+(?:to|into|in)\s+(?:the |a )?(?:folder|group)\s+(?:called |named )?(?P<f>.+)$", re.I)
_UNFOLDER = re.compile(rf"{_LEAD}(?:take|move|remove|get)\s+{_CHAT}(?P<c>.+?)\s+(?:out of|from)\s+(?:its|the|any)\s+(?:folder|group)$", re.I)


def _name(text: str) -> str:
    return " ".join(text.split()).strip(" .!?\"'“”‘’")


def _sort_word(said: str) -> str | None:
    said = _name(said).lower()
    return next((key for key, words in _SORT_OF if re.fullmatch(words, said)), None)


def read(text: str) -> dict | None:
    """The chat act `text` is, or None."""
    if found := _SORT.match(text):
        sort = _sort_word(found.group("s"))
        return {"intent": "chat_sort", "sort": sort, "about": sort} if sort else None
    if found := _GROUP.match(text):
        word = found.group("g").lower().rstrip("s")
        group = "none" if word == "nothing" else word
        return {"intent": "chat_group", "group": group, "about": group}
    if _UNGROUP.match(text):
        return {"intent": "chat_group", "group": "none", "about": "none"}
    if found := _RENAME.match(text):
        return {"intent": "chat_rename", "chat": _name(found.group("c")), "title": _name(found.group("t")), "about": _name(found.group("c"))}
    if found := _PIN.match(text):
        return {"intent": "chat_pin", "chat": _name(found.group("c")), "pinned": found.group("v").lower() == "pin", "about": _name(found.group("c"))}
    if found := _FOLDER.match(text):
        return {"intent": "chat_folder", "chat": _name(found.group("c")), "folder": _name(found.group("f")), "about": _name(found.group("c"))}
    if found := _UNFOLDER.match(text):
        return {"intent": "chat_folder", "chat": _name(found.group("c")), "folder": "", "about": _name(found.group("c"))}
    return None


def _words(intent: str) -> frozenset[str]:
    """The words of these acts' own phrases, for a real word one slip from one (as `board_acts.words`)."""
    from tessellate.ai import act_registry

    return frozenset(w for a in act_registry.ACTS.values() if a.intent == intent for w in re.findall(r"[a-z]{4,}", f"{a.verb} {a.label} {a.example}".lower()))


def words() -> frozenset[str]:
    return frozenset().union(*(_words(i) for i in INTENTS))


def _step(**arguments) -> list[dict]:  # noqa: ANN003
    return [{"name": "edit_chats", "arguments": arguments}]


def plan(session: Session, parsed: dict, c: dict) -> dict:
    """The line and card for one of `INTENTS`. `c` is `commands`' lending (`commands._parity_helpers`)."""
    from tessellate.ai.tools.tool_chats import _GROUP_WORDS, _SORT_WORDS, _no_single_chat, match_chats

    intent = parsed["intent"]
    if intent == "chat_sort":
        label = f"Sort your chats {_SORT_WORDS[parsed['sort']]}"
        return {"line": c["confirm"](label), "card": c["card"](label, _step(action="sort", sort=parsed["sort"]))}
    if intent == "chat_group":
        label = f"Show your chats {_GROUP_WORDS[parsed['group']]}"
        return {"line": c["confirm"](label), "card": c["card"](label, _step(action="group", group=parsed["group"]))}
    #: The line is said from the matches, never from a caught error's text: exception text
    #: never reaches the page (CodeQL py/stack-trace-exposure on /read/act).
    wanted = str(parsed["chat"] or "").strip()
    if not wanted:
        return {"line": "Say which chat: its id, or words from its title."}
    rows = match_chats(session, wanted)
    if len(rows) != 1:
        return {"line": f"{_no_single_chat(wanted, rows)}."}
    chat = rows[0]
    title = c["clip"](chat.title, 48) if callable(c.get("clip")) else chat.title[:48]
    if intent == "chat_rename":
        label = f"Rename the chat “{title}” to “{parsed['title'][:60]}”"
        steps = _step(action="rename", chat=str(chat.id), title=parsed["title"])
    elif intent == "chat_pin":
        label = f"{'Pin' if parsed['pinned'] else 'Unpin'} the chat “{title}”"
        steps = _step(action="pin" if parsed["pinned"] else "unpin", chat=str(chat.id))
    else:
        label = f"Move the chat “{title}” into the folder “{parsed['folder'][:40]}”" if parsed["folder"] else f"Take the chat “{title}” out of its folder"
        steps = _step(action="move", chat=str(chat.id), folder=parsed["folder"])
    return {"line": c["confirm"](label), "card": c["card"](label, steps)}
