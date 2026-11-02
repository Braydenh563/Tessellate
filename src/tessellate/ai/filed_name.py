"""The category or tag a listing names, split out of reading.py so commands.py can use it
without importing the reader that imports commands (an import cycle)."""

from __future__ import annotations

import re


#: "list my work notes", "show me all my baking notes", "notes in Work",
#: "my notes tagged harbor": a listing narrowed to one category or tag
#: (ledger row 442). The name is checked against the notebook by the route.
_FILED_LISTING = re.compile(
    r"^(?:(?:can|could|would) you |please |pls )?(?:(?:list|show|give)(?: me)?(?: all| every)?(?: of)? )?"
    r"(?:(?:my |the )(?P<a>[a-z][\w&-]{1,30}(?: [a-z][\w&-]{1,30})?) (?:notes|entries)"
    r"|(?:my |the )?(?:notes|entries) (?:in|under|filed under|tagged(?: with)?|with the tag) #?(?P<b>[a-z][\w&-]{1,30}(?: [a-z][\w&-]{1,30})?))"
    r"(?: (?:please|pls|plz))?[?.]*$",
    re.I,
)
#: Words before "notes" that are not a filing: "my recent notes", "all notes".
_NOT_FILED = frozenset({
    "recent", "newest", "latest", "last", "old", "oldest", "all", "every", "pinned", "favourite", "favorite",
    "starred", "new", "own", "other", "first", "untagged", "uncategorised", "uncategorized", "these", "those",
    "my", "the", "your", "some", "any", "more", "most", "older", "earlier", "today's", "todays",
})


#: "list my recipes", "what books do I have": a bare plural names a tag or
#: category (1324); a word the app has a list of its own for is not one.
_BARE_PLURAL = re.compile(
    r"^(?:(?:can|could|would) you |please |pls )?(?:(?:list|show)(?: me)?(?: all)?(?: of)? (?:my|the) (?P<c>[a-z]{3,20}s)"
    r"|what (?P<d>[a-z]{3,20}s) do i have)(?: (?:please|pls|plz))?[?.]*$",
    re.I,
)
_APP_LISTS = frozenset({
    "tags", "categories", "reminders", "tasks", "todos", "skills", "documents", "docs", "notes", "entries", "boards",
    "files", "photos", "chats", "conversations", "settings", "shortcuts", "personas", "spaces", "links", "dates",
    "deadlines", "themes", "models", "commands", "tools", "features", "templates", "backups", "exports", "meetings",
})


def filed_listing(text: str) -> str | None:
    """The category or tag a listing names ("work" in "list my work notes"),
    else None."""
    flat = " ".join((text or "").split())
    found = _FILED_LISTING.match(flat)
    if not found:
        bare = _BARE_PLURAL.match(flat)
        name = ((bare.group("c") or bare.group("d")) if bare else "") or ""
        return name.lower() if name and name.lower() not in _APP_LISTS and name.lower() not in _NOT_FILED else None
    name = (found.group("a") or found.group("b") or "").strip()
    name = re.sub(r"^(?:all|every|my|the) ", "", name, flags=re.I)
    return name if name and name.split()[0].lower() not in _NOT_FILED else None


#: "show me my study notes", "pull up my uni notes", "get my university notes",
#: "my uni notes": a subject's notes asked for with a verb that opens or shows
#: them, or with none (a topic, as decision 64's "games notes"). In Ask
#: that is the overview whether or not a tag or category has the name (the
#: verb decides, never the notebook, CHAT_PLAN decision 81); "list my X notes"
#: and "notes tagged X" are the listing.
SHOW_NOTES = (
    r"^\s*(?:please )?(?:(?:show|give|get|bring up|pull up|find)(?: me)? )?(?:all )?(?:of )?(?:my|the) "
    r"(?!(?:last|latest|newest|recent|first|oldest|next)\b)(?P<name>[\w&'-]+(?: [\w&'-]+)?)\s+(?:notes|entries)\s*[.?!]*$"
)
_SHOW_NOTES = re.compile(SHOW_NOTES, re.I)


def shows_the_lot(question: str) -> bool:
    """Whether `question` asks to be shown a subject's notes ("show me all of
    my university notes"); "my pinned notes" and the like are no subject."""
    found = _SHOW_NOTES.match(" ".join((question or "").split()))
    return bool(found) and found.group("name").split()[0].lower() not in _NOT_FILED
