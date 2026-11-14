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
    item and title, and the `commands.not_done` line."""

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


_NUMBERED = re.compile(r"(?:(?:note|entry) ?)?#?(\d{1,9})", re.IGNORECASE)
_PAIRS = {"“": "”", '"': '"', "‘": "’", "'": "'"}
#: A second request on the end of a rename ("... and delete the boiler note").
_THEN_VERB = re.compile(
    r",?\s+(?:and|then)\s+(?:then\s+|also\s+)?(?=(?:delete|remove|rename|restore|add|put|tag|untag|move|pin|unpin|link|unlink|create|make|remind|bin|trash|merge|open|show|find|summari[sz]e)\b)",
    re.IGNORECASE,
)
_QUOTED_NEW = re.compile(r"(?P<old>.+?) to [“\"‘'](?P<new>.+)[”\"’']", re.IGNORECASE)


def _splits(rest: str) -> tuple[list[tuple[str, str]], str]:
    """Every way `rest` reads as "old to new", the likeliest first, and what
    was left over after a second request. A quoted old name ends at its
    closing quote and a quoted new name starts after " to " and a quote, so
    a name holding "to" ("back to school") is said whole; unquoted, each
    " to " is a candidate and the planner takes the one that names something."""
    first = rest[:1]
    close = rest.find(_PAIRS[first], 1) if first in _PAIRS else -1
    quoted_old = close > 1 and rest[close + 1:].lower().startswith(" to ")
    start = close + 1 if quoted_old else rest.lower().find(" to ")
    leftover = ""
    if start >= 0 and (then := _THEN_VERB.search(rest, start + 4)):
        rest, leftover = rest[: then.start()], rest[then.end():]
    if quoted_old:
        return [(rest[1:close], rest[close + 5:])], leftover
    if quoted := _QUOTED_NEW.fullmatch(rest):
        return [(quoted.group("old"), quoted.group("new"))], leftover
    return [(rest[:m.start()], rest[m.end():]) for m in re.finditer(r" to ", rest, re.IGNORECASE)], leftover


def _kind_and_rest(text: str) -> tuple[str, str] | None:
    """(what is renamed, the words after its kind word), or None."""
    low = text.lower()
    head = next((h for h in _RENAME_HEADS if low.startswith(h)), None)
    if head is None:
        return None
    word, _, rest = _strip_article(text[len(head):].strip()).partition(" ")
    kind = _KIND_OF.get(word.lower())
    if kind is None and word.startswith("#") and _NUMBERED.fullmatch(word):
        kind, rest = "note", f"{word} {rest}"
    if kind is None:
        return None
    return kind, (rest.partition(" ")[2] if rest.lower().startswith(("called ", "named ")) else rest)


def read_rename(text: str) -> dict | None:
    """"rename the tag gym to fitness", "rename the category Work to Job",
    "rename the note passport to Travel ID", "rename note 12 to Travel": the
    kind word names what is renamed. A note said by its words around "note"
    ("rename the gym note to X") is `commands._rename`'s, and a question
    ("how do I rename a tag") has no two names, so neither is read here."""
    found = _kind_and_rest(text)
    if found is None:
        return None
    kind, rest = found
    pairs, leftover = _splits(rest.strip())
    pairs = [(_name(old), _name(new)) for old, new in pairs]
    pairs = [(old, new) for old, new in pairs if old and new and len(old) <= _MAX_NAME and len(new) <= 200]
    if not pairs:
        return None
    (old, new), more = pairs[0], pairs[1:]
    extra = {"leftover": leftover.strip(" .")} if leftover.strip(" .") else {}
    if kind != "note":
        alts = {"alts": [{"old": o, "new": n} for o, n in more]} if more else {}
        return {"intent": f"rename_{kind}", "old": old, "new": new, **alts, **extra}
    return _note_rename(old, new, more, extra)


def _note_rename(old: str, new: str, more: list[tuple[str, str]], extra: dict) -> dict | None:
    """A note renamed: by its number ("note 12"), else by the words around it."""
    if number := _NUMBERED.fullmatch(old):
        return {"intent": "rename", "about": f"note {number.group(1)}", "note_id": int(number.group(1)), "single": True, "title": new, **extra}
    about = _note_target(old)
    if not about:
        return None
    alts = {"alts": [{"about": _note_target(o), "title": n} for o, n in more if _note_target(o)]} if more else {}
    return {"intent": "rename", "about": about, "single": True, "title": new, **alts, **extra}


def pick_note_split(parsed: dict, finds) -> dict:  # noqa: ANN001
    """The reading of a note rename whose title holds " to " that names a
    note: the longest old name `finds` answers for, else the first reading.
    "rename the note how to cook to Recipes" is the note "how to cook"."""
    options = [{"about": parsed["about"], "title": parsed["title"]}, *parsed.get("alts", [])]
    for option in sorted(options, key=lambda o: -len(o["about"])):
        if finds(option["about"]):
            return {**parsed, **option}
    return parsed


_MAKE = re.compile(
    r"^(?:(?:please|pls|can you|could you|would you|and|then)\s+)*(?:create|make|add|start|set up|new)\s+(?:me )?(?:a |an |my |the )?(?:new |another )?(?:category|folder)\b\s*(?::|called|named|for|-)?\s*(?P<name>.*)$",
    re.IGNORECASE,
)


def read_make(text: str) -> dict | None:
    """"create a category called Hobbies", "make a new category Hobbies", "new
    category: Hobbies": a category made by name, the agent's `create_category`.
    A question ("how do I make a category") has no name after the kind word
    that is not a question, so it is left to the Guide."""
    found = _MAKE.match(" ".join(text.split()))
    if found is None:
        return None
    name = _name(found.group("name").rstrip(" .!"))
    if not name or len(name) > _MAX_NAME or name.endswith("?") or name.lower().split(" ", 1)[0] in ("to", "with", "in", "if", "so", "that", "which"):
        return None
    return {"intent": "create_category", "name": name}


#: Verbs that bring a binned note back; the note is named like any other.
_RESTORE_HEADS = ("restore ", "undelete ", "un-delete ", "bring back ", "get back ", "recover ")
#: These two heads are ordinary English, so they restore only with the bin said.
_BIN_ONLY_HEADS = ("get back ", "recover ")
#: "restore the last deleted note", "bring back the note I just deleted", "undelete the last one": the newest in the bin.
_LATEST = re.compile(
    r"(?:the |my )?(?:(?:last|latest|most recent|newest|previous)(?: (?:deleted|binned))?(?: one| note| thing)?|(?:note|one|thing) i (?:just |last |recently )?(?:deleted|binned|threw away)|deleted note|one i just deleted)",
    re.IGNORECASE,
)
_ALL_NOTES = re.compile(r"(?:all|every|everything)(?: of)?(?: (?:my|the))?(?: notes?)?", re.IGNORECASE)
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
    if head in _BIN_ONLY_HEADS and binned is None:
        #: "get back to John about the boiler note" and "recover from the flu" are sentences.
        return None
    if not rest or _OTHER_THING.match(rest):
        return None
    if _LATEST.fullmatch(rest):
        return {"intent": "restore", "latest": True, "about": rest}
    if _ALL_NOTES.fullmatch(rest) and (binned or "note" in rest.lower()):
        return {"intent": "restore", "all": True, "about": rest}
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


def _unknown(kind: str, wanted: str, names: list[str], verb: str = "rename") -> str:
    """"I found no tag called “gimm”. Close: “gym”." or a few of the ones there are."""
    if not names:
        return f"You have no {kind}s yet, so there is nothing to {verb}."
    near = _close(wanted, names)
    if near:
        return f"I found no {kind} called “{wanted}”. Close: " + ", ".join(f"“{n}”" for n in near) + "."
    return f"I found no {kind} called “{wanted}”. Yours include " + ", ".join(f"“{n}”" for n in names[:5]) + "."


def _exact(wanted: str, names: list[str]) -> str | None:
    return next((n for n in names if n == wanted), None) or next((n for n in names if n.casefold() == wanted.casefold()), None)


def _spaced(text: str) -> str:
    """A name with its spaces, hyphens and underscores folded to one, so
    "back to school" finds the tag “back-to-school”."""
    return re.sub(r"[\s_-]+", "-", text.casefold())


def _find(wanted: str, names: list[str]) -> str | None:
    return _exact(wanted, names) or next((n for n in names if _spaced(n) == _spaced(wanted)), None)


def _reading(parsed: dict, names: list[str]) -> dict:
    """Which " to " of an unquoted rename splits it: the longest old name that
    is one of `names`, else the first reading."""
    options = [{"old": parsed["old"], "new": parsed["new"]}, *parsed.get("alts", [])]
    for option in sorted(options, key=lambda o: -len(o["old"])):
        if _find(option["old"], names) is not None:
            return {**parsed, **option}
    return parsed


def _every_tag(session: Session) -> list[str]:
    """Every tag on any note at all, binned and private too: `tags_repo.counts`
    leaves out a locked private note's tags and a binned note is not in use,
    but `tags_repo.rename` changes both, so a merge hides behind either."""
    from tessellate.core.database import Entry
    from tessellate.entry import manager

    names: dict[str, None] = {}
    for raw in session.scalars(select(Entry.tags)):
        for tag in manager.tags_from_json(raw):
            names[tag] = None
    return list(names)


def _private_hold(session: Session, *tags: str) -> bool:
    """Whether a private note, binned or not, carries any of the tags while
    the vault is locked."""
    from tessellate.core import vault
    from tessellate.core.database import Entry
    from tessellate.entry import manager

    if vault.key() is not None:
        return False
    wanted = set(tags)
    #: Tags only: a private note's body is never loaded just to read them.
    rows = session.scalars(select(Entry.tags).where(Entry.is_private == True))  # noqa: E712
    return any(wanted.intersection(manager.tags_from_json(raw)) for raw in rows)


def _tag_refusal(session: Session, old: str, new: str) -> str | None:
    """Why a tag rename is left to the Tag manager, or None. The plan and the
    confirmed step both ask it, so a hand-made step gets no way round it."""
    if new.casefold() != old.casefold() and _exact(new, _every_tag(session)) is not None:
        #: Renaming onto a tag that exists merges the two, and Undo could not split them.
        return f"There is already a tag called “{new}”. Renaming onto it would merge the two, which Undo cannot split, so I leave that to the Tag manager."
    if _private_hold(session, old, new):
        return f"The tag “{old}” is also on private notes, and the vault is locked, so I will not rename it from here. Unlock the vault first, or use the Tag manager."
    return None


def _category_refusal(session: Session, old: str, new: str) -> str | None:
    from tessellate.entry import manager_categories

    names = [row["name"] for row in manager_categories.all_categories(session)]
    if new.casefold() != old.casefold() and _exact(new, names) is not None:
        return f"There is already a category called “{new}”. Renaming onto it would merge the two, which Undo cannot split, so I leave that to Manage categories."
    return None


def guard(session: Session, name: str, args: dict) -> str | None:
    """The refusal for a confirmed rename step, or None: the planner's checks
    again at run time, since `POST /chat/command/run` takes its steps from the
    page and a card is not the only way there."""
    from tessellate.entry import manager, tagnames

    old, new = str(args.get("old") or ""), str(args.get("new") or "")
    if name == "rename_tag":
        cleaned = tagnames.normalise_tags([new], split=False)
        return _tag_refusal(session, old, cleaned[0] if cleaned else new)
    if name == "rename_category":
        return _category_refusal(session, old, manager.category_label(new))
    if name == "delete_tag" and _private_hold(session, str(args.get("name") or "")):
        return f"The tag “{args.get('name')}” is also on private notes, and the vault is locked, so I will not remove it from here. Unlock the vault first, or use the Tag manager."
    if name == "restore_note":
        from tessellate.core.database import Entry

        note = session.get(Entry, int(args.get("note_id") or 0))
        return "A board comes back from the bin view, not from Chat." if note is not None and note.is_board else None
    return None


def _plan_rename_tag(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.entry import tagnames
    from tessellate.repo import tags as tags_repo

    counts = tags_repo.counts(session)
    parsed = _reading(parsed, list(counts))
    old = _find(parsed["old"], list(counts))
    if old is None:
        return {"line": _unknown("tag", parsed["old"], list(counts))}
    cleaned = tagnames.normalise_tags([parsed["new"]], split=False)
    if not cleaned:
        return {"line": "A tag needs a name."}
    new = cleaned[0]
    if new == old:
        return {"line": f"That tag is already called “{old}”."}
    if refusal := _tag_refusal(session, old, new):
        return {"line": refusal}
    notes = counts[old]
    label = f"Rename the tag “{old}” to “{new}” on {notes} note{'' if notes == 1 else 's'}"
    card = c.card(label, [{"name": "rename_tag", "arguments": {"old": old, "new": new}}])
    return {"line": c.confirm(label), "card": card}


def _plan_rename_category(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.entry import manager
    from tessellate.entry import manager_categories

    rows = manager_categories.all_categories(session)
    names = [row["name"] for row in rows]
    parsed = _reading(parsed, names)
    old = _find(parsed["old"], names)
    if old is None:
        return {"line": _unknown("category", parsed["old"], names)}
    if old == manager.UNCATEGORISED:
        return {"line": f"“{old}” is where notes with no category sit, so it cannot be renamed."}
    new = manager.category_label(parsed["new"])
    if new == old:
        return {"line": f"That category is already called “{old}”."}
    if refusal := _category_refusal(session, old, new):
        return {"line": refusal}
    notes = next(row["count"] for row in rows if row["name"] == old)
    label = f"Rename the category “{old}” to “{new}” ({notes} note{'' if notes == 1 else 's'} in it)"
    card = c.card(label, [{"name": "rename_category", "arguments": {"old": old, "new": new}}])
    return {"line": c.confirm(label), "card": card}


#: Most notes `_binned` hands back for a "restore all" count or a words match.
_BIN_SCAN = 500


def _binned(session: Session, parsed: dict) -> list:
    """The notes in the bin that the name holds: every word of it in the
    note's text, newest binned first (the notes a write would touch are read
    as words, not by meaning, as `commands._notes_about` does). A private note
    and a board are not here at all: Chat says nothing of what a sealed note
    holds, and a board comes back from the bin view."""
    from tessellate.core.database import Entry

    visible = (Entry.is_deleted == True, Entry.is_private.is_not(True), Entry.is_board.is_not(True))  # noqa: E712
    number = parsed.get("note_id")
    if number is not None:
        return list(session.scalars(select(Entry).where(Entry.id == number, *visible)))
    newest_first = Entry.deleted_at.desc()
    if parsed.get("all"):
        return list(session.scalars(select(Entry).where(*visible).order_by(newest_first).limit(_BIN_SCAN)))
    words = [w for w in re.findall(r"[\w']+", str(parsed.get("about") or "").lower()) if len(w) > 1 and w not in ("the", "my", "of", "and", "note")]
    if not words:
        return []
    #: SQLite's LIKE folds ASCII case only, so a word with any other letter is left to the regex below.
    #: `autoescape` makes `_` (a word character) and `%` literal.
    narrowed = [Entry.content.contains(w, autoescape=True) for w in words if w.isascii()]
    found: list = []
    for row in session.scalars(select(Entry).where(*visible, *narrowed).order_by(newest_first)).yield_per(200):
        if all(re.search(rf"\b{re.escape(w)}(?:e?s)?\b", (row.content or "").lower()) for w in words):
            found.append(row)
            if len(found) >= _BIN_SCAN:
                break
    return found


def _binned_latest(session: Session) -> list:
    """The note most recently binned ("restore the last deleted note"); a private note and a board are not here (`_binned`)."""
    from tessellate.core.database import Entry

    return list(session.scalars(
        select(Entry).where(Entry.is_deleted == True, Entry.is_private.is_not(True), Entry.is_board.is_not(True))  # noqa: E712
        .order_by(Entry.deleted_at.desc(), Entry.id.desc()).limit(1)))


def _plan_restore(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    about = str(parsed.get("about") or "")
    found = _binned_latest(session) if parsed.get("latest") else _binned(session, parsed)
    if not found:
        return {"line": "The bin has no notes I can restore." if parsed.get("all") or parsed.get("latest") else f"I found nothing in the bin about “{about}”."}
    if parsed.get("all"):
        many = f"{len(found)} notes" if len(found) > 1 else "1 note"
        newest = c.note_title(found[0].content, size=48)
        return {"line": f"There {'are' if len(found) > 1 else 'is'} {many} in the bin. I restore one at a time: say which, like “restore the {newest} note”, or open the bin to restore more than one."}
    public = found
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


def _plan_create_category(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    from tessellate.core.database import Category
    from sqlalchemy import func

    name = parsed["name"]
    if session.scalar(select(Category.id).where(func.lower(Category.name) == name.lower())) is not None:
        return {"line": f"There is already a category called “{name}”."}
    label = f"Create the category “{name}”"
    return {"line": c.confirm(label), "card": c.card(label, [{"name": "create_category", "arguments": {"name": name}}])}


def plan(session: Session, parsed: dict, c) -> dict:  # noqa: ANN001
    """The line and card for a rename of a tag or category, a new category, or a restore."""
    from tessellate.ai import address

    plans = {"create_category": _plan_create_category, "rename_tag": _plan_rename_tag, "rename_category": _plan_rename_category, "restore": _plan_restore,
             "set_name": lambda _session, found, helpers: address.plan(found, helpers.card, helpers.confirm)}
    return plans[parsed["intent"]](session, parsed, c)
