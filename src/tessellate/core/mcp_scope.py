"""Which notes one outside client's token may see (L-world-class-560, B52).

A scope is `{"categories": [...], "tags": [...]}`: a note is inside when it is
filed in one of the categories or carries one of the tags (any case, a tag's
`#` ignored). Both empty is the whole notebook, as every token was before.

**One gate, set per request.** `routes_mcp` works out the ids inside the scope
for each message and sets `current`; the reading tools' one where-clause
(`ai/tools/_common._visible`) and their one id check (`_require_note`) read
it, so a list, a count, a search, a get, a graph walk and a path all leave the
rest out without each handler remembering to. An id outside reads exactly like
a missing one, so a client cannot learn which notes exist beyond its scope.

**Writes keep notes inside.** `write_refusal` runs before a write tool: a new
note must land inside the scope, and an edit or a retag may not move one out,
which is checked on the state the write would leave, before anything changes.
Private notes stay out for every token, scoped or not (`_visible`).
"""

from __future__ import annotations

from contextvars import ContextVar

#: Tools a scoped token is offered: the ones whose every read goes through the
#: gate above, the writes `write_refusal` can check, and two that read no
#: notes. Anything else (documents, boards, reminders, whole-notebook summaries,
#: renames, the web) is left out rather than trusted to filter itself.
SCOPED_TOOLS = frozenset({
    "search_notes", "get_note", "list_notes", "count_notes", "related_notes", "path_between",
    "find_similar_notes", "create_note", "edit_note", "tag_note", "pin_note", "link_notes",
    "unlink_notes", "get_current_time", "calculate",
})
MAX_NAMES = 20
MAX_NAME = 60

#: The ids inside the scope of the request being answered, or None for the
#: whole notebook. Per request (a ContextVar), so two clients never share one.
current: ContextVar[frozenset[int] | None] = ContextVar("mcp_note_scope", default=None)


def _names(values: object, strip_hash: bool) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values if isinstance(values, list) else []:
        name = " ".join(str(raw or "").split())[:MAX_NAME]
        if strip_hash:
            name = name.lstrip("#").strip()
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            out.append(name)
    return out[:MAX_NAMES]


def clean(scope: object) -> dict:
    """A scope as stored: two short lists of names, deduplicated by case."""
    scope = scope if isinstance(scope, dict) else {}
    return {"categories": _names(scope.get("categories"), False), "tags": _names(scope.get("tags"), True)}


def is_whole(scope: object) -> bool:
    scope = clean(scope)
    return not scope["categories"] and not scope["tags"]


def allows(scope: dict, category: str | None, tags: list[str]) -> bool:
    """Whether a note filed under `category` with `tags` is inside `scope`."""
    scope = clean(scope)
    if not scope["categories"] and not scope["tags"]:
        return True
    cats = {name.casefold() for name in scope["categories"]}
    wanted = {name.casefold() for name in scope["tags"]}
    return (category or "").strip().casefold() in cats or bool(wanted & {str(t).lstrip("#").casefold() for t in tags})


def describe(scope: object) -> str:
    """The scope in words, for Settings, the refusal and `initialize`."""
    scope = clean(scope)
    parts = []
    if scope["categories"]:
        parts.append("notes in " + " or ".join(scope["categories"]))
    if scope["tags"]:
        parts.append(("tagged " if parts else "notes tagged ") + " or ".join(scope["tags"]))
    return ", or ".join(parts) if parts else "the whole notebook"


def note_ids(session, scope: dict) -> frozenset[int]:  # noqa: ANN001  # a Session, imported late
    """Every readable note inside `scope` (deleted, private and board rows never)."""
    from sqlalchemy import select

    from tessellate.core.database import Category, Entry
    from tessellate.entry import manager

    rows = session.execute(
        select(Entry.id, Entry.tags, Category.name)
        .outerjoin(Category, Entry.category_id == Category.id)
        .where(Entry.is_deleted == False, Entry.is_private == False, Entry.is_board == False)  # noqa: E712
    ).all()
    return frozenset(
        note_id for note_id, tags, category in rows
        if allows(scope, category or manager.UNCATEGORISED, manager.tags_from_json(tags))
    )


def in_scope(note_id: int) -> bool:
    ids = current.get()
    return ids is None or int(note_id) in ids


def _note_state(session, note_id: int) -> tuple[str, list[str]] | None:  # noqa: ANN001
    from tessellate.core.database import Entry
    from tessellate.entry import manager

    entry = session.get(Entry, int(note_id))
    if entry is None:
        return None
    return manager.category_name_for(session, entry), manager.entry_tags(entry)


def _after(session, name: str, args: dict, raw: object) -> tuple[str, list[str]] | None:  # noqa: ANN001
    """The category and tags note `raw` would have after an edit or a retag; None if unseen."""
    from tessellate.entry import tagnames

    try:
        state = _note_state(session, int(raw)) if in_scope(int(raw)) else None
    except (TypeError, ValueError):
        state = None
    if state is None:
        return None
    category, tags = state
    if name == "edit_note":
        tags = [str(t) for t in args["tags"]] if args.get("tags") is not None else tags
        return str(args.get("category") or category), tags
    removed = {str(r).casefold() for r in args.get("remove") or []}
    return category, tagnames.retagged(tags, args.get("add") or [], removed)


def write_refusal(session, scope: dict, name: str, args: dict) -> str:  # noqa: ANN001
    """Empty when the write keeps every note it touches inside `scope`, else why not.

    Ids outside the scope are refused by `_require_note` when the tool runs;
    this checks the state a create, an edit or a retag would leave, and refuses
    a whole batch before any of it is written."""
    if is_whole(scope):
        return ""
    why = f"This link reaches only {describe(scope)}, so that change would put a note outside it."
    if name == "create_note":
        return "" if allows(scope, str(args.get("category") or ""), [str(t) for t in args.get("tags") or []]) else why
    ids = [args.get("note_id"), *(args.get("note_ids") or [])] if name in ("edit_note", "tag_note") else []
    for raw in [value for value in ids if value is not None]:
        state = _after(session, name, args, raw)
        if state is None:
            return f"No note with id {raw}"
        if not allows(scope, *state):
            return why
    return ""
