"""Acts on a kind of thing named by its word (CHAT_PLAN X5 and X8): "rename
the tag gym to fitness", "rename the category Work to Job", "rename the note
Passport to Travel ID", "restore the passport note" from the bin.

The reader finds the kind word and the two names; the planner resolves them
against the notebook and gives the card that waits for Confirm, over tools
the agent already has (`rename_tag`, `rename_category`, `restore_note`). It
reads and previews only: nothing here writes, and a private note is not
touched (a locked vault refuses a tag that a private note holds, and a
private note in the bin is not restored from Chat). `commands.py` hands its
own card and note helpers in, as `task_acts.py` does, so this module imports
nothing above it.
"""

from __future__ import annotations

import difflib
import re

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session



class Helpers(NamedTuple):
    """What `commands.py` lends the planners: its card, confirm line, note
    item and title, and the "Not done" line."""

    card: object
    confirm: object
    item: object
    note_title: object
    summarise_done: object


_QUOTES = " '\"“”‘’"
_RENAME_HEADS = ("rename ", "retitle ", "change the name of ")
_KIND_OF = {"tag": "tag", "label": "tag", "category": "category", "folder": "category", "note": "note"}
_MAX_NAME = 100


def _name(text: str) -> str:
    return text.strip(_QUOTES).lstrip("#").strip(_QUOTES)


def _strip_article(rest: str) -> str:
    for article in ("the ", "my ", "our ", "a "):
        if rest.lower().startswith(article):
            return rest[len(article):]
    return rest


def _note_target(old: str) -> str:
    about = old[len("about "):].strip() if old.lower().startswith("about ") else old
    return about[4:] if about.lower().startswith("the ") else about


def read_rename(text: str) -> dict | None:
    """"rename the tag gym to fitness", "rename the category Work to Job",
    "rename the note passport to Travel ID": the kind word names what is
    renamed. A note said by its words around "note" ("rename the gym note to
    X") is `commands._rename`'s, and a question ("how do I rename a tag")
    has no two names, so neither is read here."""
    low = text.lower()
    head = next((h for h in _RENAME_HEADS if low.startswith(h)), None)
    if head is None:
        return None
    word, _, rest = _strip_article(text[len(head):].strip()).partition(" ")
    kind = _KIND_OF.get(word.lower())
    if kind is None:
        return None
    if rest.lower().startswith(("called ", "named ")):
        rest = rest.partition(" ")[2]
    old, sep, new = rest.partition(" to ")
    old, new = _name(old), _name(new)
    if not sep or not old or not new or len(old) > _MAX_NAME or len(new) > 200:
        return None
    if kind != "note":
        return {"intent": f"rename_{kind}", "old": old, "new": new}
    about = _note_target(old)
    return {"intent": "rename", "about": about, "single": True, "title": new} if about else None


#: Verbs that bring a binned note back; the note is named like any other.
_RESTORE_HEADS = ("restore ", "undelete ", "un-delete ", "bring back ", "get back ", "recover ")
_BIN_TAIL = re.compile(r"\s+(?:from|out of|in) (?:the |my )?(?:bin|trash|rubbish(?: bin)?|recycle bin|deleted(?: notes)?)$", re.IGNORECASE)
_OTHER_THING = re.compile(r"(?:the |a |my )?(?:tags?|labels?|reminders?|categor(?:y|ies)|boards?|maps?|documents?|settings?|defaults?)\b", re.IGNORECASE)


def read_restore(text: str, one_target) -> dict | None:  # noqa: ANN001
    """"restore the passport note", "bring back my boiler note from the bin",
    "undelete note 12". A title alone is read only with "from the bin" after
    it, so "restore the default settings" stays a sentence for the app-verb
    line (`act_registry.app_verb`)."""
    low = text.lower()
    head = next((h for h in _RESTORE_HEADS if low.startswith(h)), None)
    if head is None:
        return None
    rest = text[len(head):].strip(" .")
    binned = _BIN_TAIL.search(rest)
    if binned:
        rest = rest[: binned.start()].strip()
    if not rest or _OTHER_THING.match(rest):
        return None
    found = one_target(rest, bare=binned is not None)
    return {"intent": "restore", **found} if found else None


# --- plan -------------------------------------------------------------------------------


def _close(wanted: str, names: list[str]) -> list[str]:
    """The names near `wanted`: a slip away or holding it, nearest first."""
    key = wanted.casefold()
    by_key = {n.casefold(): n for n in names}
    near = difflib.get_close_matches(key, list(by_key), n=3, cutoff=0.6)
    near += [k for k in by_key if key in k and k not in near]
    return [by_key[k] for k in near[:3]]


def _unknown(kind: str, wanted: str, names: list[str]) -> str:
    """"I found no tag called “gimm”. Close: “gym”." or a few of the ones there are."""
    if not names:
        return f"You have no {kind}s yet, so there is nothing to rename."
    near = _close(wanted, names)
    if near:
        return f"I found no {kind} called “{wanted}”. Close: " + ", ".join(f"“{n}”" for n in near) + "."
    return f"I found no {kind} called “{wanted}”. Yours include " + ", ".join(f"“{n}”" for n in names[:5]) + "."


def _exact(wanted: str, names: list[str]) -> str | None:
    return next((n for n in names if n == wanted), None) or next((n for n in names if n.casefold() == wanted.casefold()), None)


def _private_hold(session: Session, tag: str) -> bool:
    """Whether a private note carries the tag while the vault is locked."""
    from tessellate.core import vault
    from tessellate.core.database import Entry
    from tessellate.entry import manager

    if vault.key() is not None:
        return False
    rows = session.scalars(select(Entry).where(Entry.is_private == True, Entry.is_deleted == False))  # noqa: E712
    return any(tag in manager.entry_tags(row) for row in rows)


def _plan_rename_tag(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.entry import tagnames
    from tessellate.repo import tags as tags_repo

    counts = tags_repo.counts(session)
    old = _exact(parsed["old"], list(counts))
    if old is None:
        return {"line": _unknown("tag", parsed["old"], list(counts))}
    cleaned = tagnames.normalise_tags([parsed["new"]], split=False)
    if not cleaned:
        return {"line": "A tag needs a name."}
    new = cleaned[0]
    if new == old:
        return {"line": f"That tag is already called “{old}”."}
    if _exact(new, list(counts)) is not None and new.casefold() != old.casefold():
        #: Renaming onto a tag that exists merges the two, and Undo could not split them.
        return {"line": f"There is already a tag called “{new}”. Renaming onto it would merge the two, which Undo cannot split, so I leave that to the Tag manager."}
    if _private_hold(session, old):
        return {"line": f"The tag “{old}” is also on private notes, and the vault is locked, so I will not rename it from here. Unlock the vault first, or use the Tag manager."}
    notes = counts[old]
    label = f"Rename the tag “{old}” to “{new}” on {notes} note{'' if notes == 1 else 's'}"
    card = c.card(label, [{"name": "rename_tag", "arguments": {"old": old, "new": new}}])
    return {"line": c.confirm(label), "card": card}


def _plan_rename_category(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.entry import manager

    rows = manager.all_categories(session)
    names = [row["name"] for row in rows]
    old = _exact(parsed["old"], names)
    if old is None:
        return {"line": _unknown("category", parsed["old"], names)}
    if old == manager.UNCATEGORISED:
        return {"line": f"“{old}” is where notes with no category sit, so it cannot be renamed."}
    new = manager.category_label(parsed["new"])
    if new == old:
        return {"line": f"That category is already called “{old}”."}
    if _exact(new, names) is not None and new.casefold() != old.casefold():
        return {"line": f"There is already a category called “{new}”. Renaming onto it would merge the two, which Undo cannot split, so I leave that to Manage categories."}
    notes = next(row["count"] for row in rows if row["name"] == old)
    label = f"Rename the category “{old}” to “{new}” ({notes} note{'' if notes == 1 else 's'} in it)"
    card = c.card(label, [{"name": "rename_category", "arguments": {"old": old, "new": new}}])
    return {"line": c.confirm(label), "card": card}


def _binned(session: Session, parsed: dict) -> list:
    """The notes in the bin that the name holds: every word of it in the
    note's text, newest binned first (the notes a write would touch are read
    as words, not by meaning, as `commands._notes_about` does)."""
    from tessellate.core.database import Entry

    number = parsed.get("note_id")
    rows = session.scalars(select(Entry).where(Entry.is_deleted == True).order_by(Entry.deleted_at.desc()).limit(500)).all()  # noqa: E712
    if number is not None:
        return [row for row in rows if row.id == number]
    words = [w for w in re.findall(r"[\w']+", str(parsed.get("about") or "").lower()) if len(w) > 1 and w not in ("the", "my", "of", "and", "note")]
    if not words:
        return []
    return [row for row in rows if all(re.search(rf"\b{re.escape(w)}", (row.content or "").lower()) for w in words)]


def _plan_restore(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    about = str(parsed.get("about") or "")
    found = _binned(session, parsed)
    public = [row for row in found if not row.is_private]
    if not found:
        return {"line": f"I found nothing in the bin about “{about}”."}
    if not public:
        return {"line": c.summarise_done([], [{"id": found[0].id, "reason": "private"}])}
    if len(public) > 1:
        titled = [row for row in public if c.note_title(row.content, size=48).lower().startswith(about.lower())]
        if len(titled) != 1:
            names = " or ".join(f"“{c.note_title(row.content, size=48)}”" for row in public[:3])
            return {"line": f"Which note in the bin about “{about}”: {names}?"}
        public = titled
    entry = public[0]
    label = f"Restore the note “{c.note_title(entry.content, size=48)}” from the bin"
    card = c.card(label, [{"name": "restore_note", "arguments": {"note_id": entry.id}}], items=[c.item(entry)])
    return {"line": c.confirm(label), "card": card}


def plan(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    """The line and card for a rename of a tag or category, or a restore."""
    return {"rename_tag": _plan_rename_tag, "rename_category": _plan_rename_category, "restore": _plan_restore}[parsed["intent"]](session, parsed, c)
