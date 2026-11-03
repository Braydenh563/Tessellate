"""Per-tool pre and post conditions, checked in Python (WORLD_CLASS_PLAN B5).

**Why this exists.** A tool's schema says what shape its arguments take; it
cannot say what must be true of the notebook before the call makes sense, or
what must be true after it for the call to count as done. Both used to live,
when they lived anywhere, inside each handler, and some were missing:

* `link_notes` skipped a target id that did not exist and reported success
  for the rest, so "link 4 to 99" read as done with nothing linked to 99;
* `tag_note` with neither `add` nor `remove` was a successful no-op the model
  then reported as "tagged";
* `edit_note {"category": "heath"}` beside an existing "Health" quietly made
  a second category, the duplicate the 3B made on "File the dentist note
  under Health" (AGENT_SKILLS_REFORM H4);
* nothing re-read a row after a write, so a handler that returned a label
  without the change holding (a stale session, a rename that merged instead)
  was reported to the model, and so to the person, as done.

**The rule.** A precondition refuses the call before the handler runs, with
one line that names what is wrong and what to do instead, the same shape
`check_arguments` gives a missing parameter. A postcondition re-reads the
rows the call claimed to change and turns a claim that did not hold into an
error, so the agent's "you said you saved it" net and the skill verifier see
the truth rather than the label.

A condition that cannot be evaluated (a stub session in a test, a locked
database) is skipped, never failed: the contract is a second check on top of
the handler's own, and a fault in the checker must not cost the person the
write. Only the core note, tag, category and reminder tools carry one; the
document, board and map tools have their own managers' checks.
"""

from __future__ import annotations

import difflib
import logging
from typing import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entry, EntryLink, Reminder
from tessellate.entry import manager
from tessellate.repo import tags as tags_repo
from tessellate.entry.tagnames import normalise_tags

_log = logging.getLogger("tessellate.tools")

Pre = Callable[[Session, dict], "str | None"]
Post = Callable[[Session, dict, dict], "str | None"]

#: How close a new category name must be to an existing one to read as a
#: misspelling of it ("Heath" for "Health", "Recipe" for "Recipes") rather
#: than a new category. 0.8 keeps "Work" and "Words" apart (0.67).
NEAR_NAME_RATIO = 0.8


def _ids(value) -> list[int]:
    raw = value if isinstance(value, list) else [value]
    out = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _fold(text: object) -> str:
    return " ".join(str(text or "").split()).casefold()


def _category_names(session: Session) -> list[str]:
    return [row["name"] for row in manager.all_categories(session)]


def near_category(session: Session, wanted: str) -> tuple[str | None, str | None]:
    """(the existing spelling, None) when `wanted` names a category that
    exists in any case; (None, the near name) when it reads as a misspelling
    of one; (None, None) for a genuinely new name."""
    folded = _fold(wanted)
    names = _category_names(session)
    for name in names:
        if _fold(name) == folded:
            return name, None
    for name in names:
        other = _fold(name)
        plural = other.rstrip("s") == folded.rstrip("s")
        if plural or difflib.SequenceMatcher(None, folded, other).ratio() >= NEAR_NAME_RATIO:
            return None, name
    return None, None


# --- preconditions ---------------------------------------------------------------


def _pre_category(session: Session, args: dict) -> str | None:
    """A named category is the one that exists, in its own spelling; a near
    miss of one is refused naming it. A new name is allowed: "make a note in
    a new category Travel" is a real request, and the duplicate is the harm."""
    wanted = str(args.get("category") or "").strip()
    if not wanted:
        return None
    existing, near = near_category(session, wanted)
    if existing:
        args["category"] = existing
        return None
    if near:
        return (
            f"There is no category called “{wanted}”, but there is “{near}”. "
            f"Use “{near}”, or call create_category first if a new one is meant."
        )
    return None


def _pre_targets_live(field: str, plural: str | None = None) -> Pre:
    def check(session: Session, args: dict) -> str | None:
        wanted = _ids(args.get(field)) + (_ids(args.get(plural) or []) if plural else [])
        source = _ids(args.get("note_id"))
        for note_id in wanted:
            if source and note_id == source[0]:
                return f"Note #{note_id} can't be linked to itself. Name a different note."
            entry = session.get(Entry, note_id)
            if entry is None or entry.is_deleted:
                return f"There is no note #{note_id}. Call search_notes to find the right id."
        return None

    return check


def _pre_tag_change(session: Session, args: dict) -> str | None:
    if not (args.get("add") or args.get("remove")):
        return 'Say which tags to change: "add" (a list), "remove" (a list), or both.'
    return None


def _pre_tag_exists(field: str) -> Pre:
    def check(session: Session, args: dict) -> str | None:
        name = str(args.get(field) or "").strip()
        if not name:
            return None
        if _fold(name) in {_fold(tag) for tag in tags_repo.counts(session)}:
            return None
        known = ", ".join(list(tags_repo.counts(session))[:12])
        return f"No note has the tag “{name}”." + (f" Tags in use: {known}." if known else "")

    return check


def _pre_rename_differs(session: Session, args: dict) -> str | None:
    #: Exact, not folded: "work" to "Work" is a real rename of a spelling.
    old = str(args.get("old") or "").strip()
    if old and old == str(args.get("new") or "").strip():
        return "The old and new names are the same, so there is nothing to rename."
    return None


def _pre_restorable(session: Session, args: dict) -> str | None:
    entry = session.get(Entry, _ids(args.get("note_id"))[0]) if _ids(args.get("note_id")) else None
    if entry is not None and not entry.is_deleted:
        return f"Note #{entry.id} is not in the recycle bin, so there is nothing to restore."
    return None


# --- postconditions ----------------------------------------------------------------


def _entry(session: Session, note_id) -> Entry | None:
    ids = _ids(note_id)
    if not ids:
        return None
    session.expire_all()
    return session.get(Entry, ids[0])


def _post_note_written(session: Session, args: dict, result: dict) -> str | None:
    entry = _entry(session, result.get("id"))
    if entry is None or entry.is_deleted:
        return "the note was not saved"
    content = args.get("content")
    if content is not None and _fold(content) and _fold(content) not in _fold(entry.content):
        return f"note #{entry.id} does not hold the new text"
    category = str(args.get("category") or "").strip()
    if category and _fold(manager.category_name_for(session, entry)) != _fold(category):
        return f"note #{entry.id} is not filed under “{category}”"
    if args.get("tags") is not None:
        #: Compared as stored: a tag is normalised on the way in (trimmed,
        #: cut to its length cap), and a raw 80-character tag read as
        #: "missing" made a real save look failed, the one way a postcondition
        #: can cause the duplicate it exists to prevent.
        held = {_fold(t) for t in manager.entry_tags(entry)}
        missing = [t for t in _wanted_tags(args["tags"]) if _fold(t) not in held]
        if missing:
            return f"note #{entry.id} is missing the tag {missing[0]}"
    return None


def _wanted_tags(raw) -> list[str]:
    """The tags a call asked for, as the store will hold them."""
    if isinstance(raw, str):
        raw = [raw]
    return normalise_tags([str(t) for t in raw or []])


def _post_tags(session: Session, args: dict, result: dict) -> str | None:
    session.expire_all()
    for note_id in result.get("tagged") or []:
        entry = session.get(Entry, note_id)
        if entry is None:
            continue
        held = {_fold(t) for t in manager.entry_tags(entry)}
        removed = {_fold(t) for t in _wanted_tags(args.get("remove"))}
        added = {_fold(t) for t in _wanted_tags(args.get("add"))}
        missing = sorted(added - held)
        if missing:
            return f"note #{note_id} does not carry the tag {missing[0]}"
        left = sorted((removed - added) & held)
        if left:
            return f"note #{note_id} still carries the tag {left[0]}"
    return None


def _post_pinned(session: Session, args: dict, result: dict) -> str | None:
    entry = _entry(session, args.get("note_id"))
    wanted = bool(args.get("pinned", True))
    if entry is not None and bool(entry.pinned) != wanted:
        return f"note #{entry.id} is {'not ' if wanted else ''}in Favourites"
    return None


def _linked(session: Session, a: int, b: int) -> bool:
    return (
        session.scalar(
            select(func.count(EntryLink.id)).where(
                or_(
                    (EntryLink.source_entry_id == a) & (EntryLink.target_entry_id == b),
                    (EntryLink.source_entry_id == b) & (EntryLink.target_entry_id == a),
                )
            )
        )
        or 0
    ) > 0


def _post_linked(session: Session, args: dict, result: dict) -> str | None:
    ids = result.get("linked") or []
    for other in ids[1:]:
        if not _linked(session, ids[0], other):
            return f"notes #{ids[0]} and #{other} are not linked"
    return None


def _post_unlinked(session: Session, args: dict, result: dict) -> str | None:
    pair = result.get("unlinked") or []
    if len(pair) == 2 and _linked(session, pair[0], pair[1]):
        return f"notes #{pair[0]} and #{pair[1]} are still linked"
    return None


def _post_binned(wanted: bool) -> Post:
    def check(session: Session, args: dict, result: dict) -> str | None:
        entry = _entry(session, args.get("note_id"))
        if entry is not None and bool(entry.is_deleted) != wanted:
            return f"note #{entry.id} is {'not ' if wanted else 'still '}in the recycle bin"
        return None

    return check


def _post_reminder(session: Session, args: dict, result: dict) -> str | None:
    session.expire_all()
    reminder = session.get(Reminder, int(result.get("id") or 0))
    if reminder is None:
        return "the reminder was not saved"
    if "done" in result and bool(reminder.done) != bool(result["done"]):
        return f"reminder #{reminder.id} is not marked {'done' if result['done'] else 'not done'}"
    return None


def _category_exists(session: Session, name: object, exact: bool = False) -> bool:
    """Exact for "is it gone": merging "work" into "Work" leaves "Work"."""
    session.expire_all()
    test = Category.name == str(name).strip() if exact else func.lower(Category.name) == _fold(name)
    return (session.scalar(select(func.count(Category.id)).where(test)) or 0) > 0


def _post_category_present(field: str) -> Post:
    def check(session: Session, args: dict, result: dict) -> str | None:
        name = result.get(field)
        if name and not _category_exists(session, name):
            return f"there is no category “{name}”"
        return None

    return check


def _post_category_gone(arg: str) -> Post:
    def check(session: Session, args: dict, result: dict) -> str | None:
        if arg == "old":
            if _fold(args.get("old")) == _fold(args.get("new")):
                return None
            name = args.get("old")
        else:
            name = result.get(arg)
        if name and _category_exists(session, name, exact=True):
            return f"the category “{name}” is still there"
        return None

    return check


def _post_tag_gone(session: Session, args: dict, result: dict) -> str | None:
    old = _fold(args.get("old") or args.get("name"))
    if old and _fold(args.get("new")) != old and old in {_fold(t) for t in tags_repo.counts(session)}:
        return f"the tag “{args.get('old') or args.get('name')}” is still on a note"
    return None


def _post_moved(session: Session, args: dict, result: dict) -> str | None:
    """Each note the call says it moved is under the category it was sent to."""
    name = str(args.get("category") or "").strip()
    ids = result.get("ids") or []
    if not name or not ids or args.get("restore_categories"):
        return None
    session.expire_all()
    for note_id in ids:
        entry = session.get(Entry, int(note_id))
        if entry is not None and manager.category_name_for(session, entry) != name:
            return f"note #{note_id} is not under “{name}”"
    return None


#: tool name -> (preconditions, postconditions). The order inside a tuple is
#: the order they run; the first refusal wins.
CONTRACTS: dict[str, tuple[tuple[Pre, ...], tuple[Post, ...]]] = {
    "create_note": ((_pre_category,), (_post_note_written,)),
    "edit_note": ((_pre_category,), (_post_note_written,)),
    "tag_note": ((_pre_tag_change,), (_post_tags,)),
    "pin_note": ((), (_post_pinned,)),
    "link_notes": ((_pre_targets_live("other_note_id", "other_note_ids"),), (_post_linked,)),
    "unlink_notes": ((_pre_targets_live("other_note_id"),), (_post_unlinked,)),
    "delete_note": ((), (_post_binned(True),)),
    "restore_note": ((_pre_restorable,), (_post_binned(False),)),
    "set_reminder": ((), (_post_reminder,)),
    "complete_reminder": ((), (_post_reminder,)),
    "rename_tag": ((_pre_rename_differs, _pre_tag_exists("old")), (_post_tag_gone,)),
    "delete_tag": ((_pre_tag_exists("name"),), (_post_tag_gone,)),
    "create_category": ((), (_post_category_present("name"),)),
    "rename_category": ((_pre_rename_differs,), (_post_category_present("name"), _post_category_gone("old"))),
    "merge_categories": ((), (_post_category_present("into"), _post_category_gone("from"))),
    "delete_category": ((), (_post_category_gone("name"),)),
    "move_notes": ((), (_post_moved,)),
}


def _loggable(name: str) -> str:
    """A tool name as a model wrote it, on one log line (CodeQL, log injection)."""
    return str(name).replace("\r", " ").replace("\n", " ")[:80]


def precondition(session: Session, name: str, args: dict) -> str | None:
    """The one-line reason `name` cannot run on `args`, or None. May fold an
    argument to the notebook's own spelling (a category's case)."""
    for check in CONTRACTS.get(name, ((), ()))[0]:
        try:
            problem = check(session, args)
        except Exception:  # noqa: BLE001  # a checker's fault is not the call's
            _log.debug("precondition of %s skipped", _loggable(name), exc_info=True)
            continue
        if problem:
            return f"{name}: {problem}"
    return None


def postcondition(session: Session, name: str, args: dict, result: dict) -> str | None:
    """What the call claimed and the rows do not show, or None."""
    for check in CONTRACTS.get(name, ((), ()))[1]:
        try:
            problem = check(session, args, result)
        except Exception:  # noqa: BLE001
            _log.debug("postcondition of %s skipped", _loggable(name), exc_info=True)
            continue
        if problem:
            return f"{name} did not take effect: {problem}. Say so rather than claim it."
    return None
