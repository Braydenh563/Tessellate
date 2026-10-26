"""Counts with a filter (composer work list 3).

"How many notes are not linked" answered the total, and "how many notes are
tagged work" with no such tag answered the number of tags. The class: a count
of notes narrowed by any of link state, tag, category and a window of days,
said together ("3 unlinked notes in Uni"), and a filter value the notebook
does not hold says so and offers the nearest one. Dates are read by
`ai/recognise.py` through `notebook_stats._window`; this module reads none."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass

from sqlalchemy import literal, select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Entry, EntryLink

_UNLINKED = re.compile(
    r"\b(?:orphan(?:s|ed)?|unlinked|unconnected|not (?:linked|connected)|(?:isn'?t|aren'?t|are not|is not|aren't) (?:linked|connected)"
    r"|(?:no|without(?: any)?) (?:links?|connections?))\b"
)
_LINKED = re.compile(r"\b(?:linked|connected|(?:have|has|with) (?:any )?(?:links?|connections?))\b")
_TAGGED = re.compile(r"\b(?:tagged(?: with)?|(?:with|has|have) (?:the )?tags?|tag)\s+(?:the |a |as )?([a-z0-9][\w-]*)")
_ANY_TAG = re.compile(r"\b(?:tagged|have (?:a|any) tags?|has (?:a|any) tags?|with (?:a|any) tags?)\s*(?:at all)?[?.!]*$")
_CATEGORY_WORD = re.compile(r"\b(?:categor(?:y|ies)|folders?|spaces?)\b")
_IN_CATEGORY = re.compile(r"\b(?:in|under|filed under|inside)\s+(?:the |my |a )?([a-z][\w-]*)(?:\s+(?:category|folder|space))?")
#: Values after "in" that are not a category: where a note sits, not a name.
_NOT_A_CATEGORY = frozenset(
    "total all each every my the notebook notebooks there here bin trash archive archived drafts draft progress general "
    "category categories folder folders space spaces tag tags common order full".split()
)
#: A note's state as the question says it: pinned, archived, or a checklist (a
#: note holding any `- [ ]` box).
_STATES = (("pinned", re.compile(r"\bpinned\b")), ("archived", re.compile(r"\barchived\b")),
           ("checklist", re.compile(r"\b(?:check ?lists?|to-?do lists?)\b")))
_BOX = re.compile(r"^[ \t]*(?:[-*+]|\d{1,3}[.)])[ \t]+\[[ xX]\]", re.M)
_STOP_TAG = frozenset("a an the any no not with this that it them".split())


@dataclass
class Narrowed:
    """What a question narrows the notes by."""

    linked: bool | None = None
    any_tag: bool = False
    tag: str = ""
    category: str = ""
    window: tuple | None = None
    state: str = ""

    @property
    def active(self) -> bool:
        return self.linked is not None or self.any_tag or bool(self.tag) or bool(self.category) or bool(self.state)


def _tags_of(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(t).strip() for t in parsed if str(t).strip()] if isinstance(parsed, list) else []


def _category_in(text: str, raw: str, names: list[str], is_date) -> str:  # noqa: ANN001
    """The category the question names: one the notebook has, or the value
    after "in" when it is written as a name ("in Work") or called a category."""
    for name in sorted(names, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", text):
            return name
    found = _IN_CATEGORY.search(text)
    if not found or found.group(1) in _NOT_A_CATEGORY or is_date(found.group(1)):
        return ""
    said = re.search(rf"\b(?:in|under|inside)\s+(?:the |my |a )?({re.escape(found.group(1))})\b", raw, re.I)
    if _CATEGORY_WORD.search(text) or (said and said.group(1)[:1].isupper()):
        return found.group(1)
    return ""


def read(text: str, raw: str, names: list[str], window: tuple | None, is_date) -> Narrowed:  # noqa: ANN001
    """The narrowing in a (lower-cased, spelling-corrected) question.
    `is_date` says whether a value is a day or span (the recogniser's)."""
    narrowed = Narrowed(window=window, state=next((name for name, rx in _STATES if rx.search(text)), ""))
    if _UNLINKED.search(text):
        narrowed.linked = False
    elif _LINKED.search(text):
        narrowed.linked = True
    tagged = _TAGGED.search(text)
    if _ANY_TAG.search(text):
        narrowed.any_tag = True
    elif tagged and tagged.group(1) not in _STOP_TAG:
        narrowed.tag = tagged.group(1)
    narrowed.category = _category_in(text, raw, names, is_date)
    return narrowed


def _nearest(value: str, names: list[str]) -> str:
    close = difflib.get_close_matches(value.lower(), [n.lower() for n in names], n=1, cutoff=0.6)
    return next((n for n in names if close and n.lower() == close[0]), "")


def _listed(label: str, names: list[str]) -> str:
    if not names:
        return f"You have no {label} yet."
    if len(names) > 6:
        return f"You have {len(names)} {label}."
    return f"Your {label} are " + (", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]) + "."


def _missing(kind: str, value: str, names: list[str]) -> str:
    """"No note is tagged work: there is no tag called work. The nearest is
    wok." when the filter's value is not in the notebook."""
    near = _nearest(value, names)
    head = f"No note is tagged {value}: you have no tag called {value}." if kind == "tag" else (
        f"You have no category called {value[:1].upper() + value[1:]}, so no notes in it."
    )
    listing = _listed("tags" if kind == "tag" else "categories", names)
    return f"{head} The nearest is {near}." if near else f"{head} {listing}"


def _linked_ids(session: Session) -> set[int]:
    linked: set[int] = set()
    for source, target in session.execute(select(EntryLink.source_entry_id, EntryLink.target_entry_id)).all():
        linked.update((source, target))
    return linked


def _phrase(n: int, narrowed: Narrowed, category_name: str, tag: str) -> str:
    adj = {False: "unlinked ", True: "linked ", None: ""}[narrowed.linked]
    adj += {"pinned": "pinned ", "archived": "archived "}.get(narrowed.state, "")
    note = ("checklist" if narrowed.state == "checklist" else "note") + ("" if n == 1 else "s")
    tail = [p for p in (
        f"in {category_name}" if category_name else "",
        f"tagged {tag}" if tag else "with a tag" if narrowed.any_tag else "",
        f"written {narrowed.window[2]}" if narrowed.window else "",
    ) if p]
    count = "no" if n == 0 else str(n)
    return f"You have {count} {adj}{note}{' ' + ' '.join(tail) if tail else ''}."


def _gap(narrowed: Narrowed, tag_names: list[str], names: list[str]) -> tuple[str, list[dict]] | None:
    """The answer for a tag or category the notebook does not hold."""
    if narrowed.tag and narrowed.tag.lower() not in {t.lower() for t in tag_names}:
        return _missing("tag", narrowed.tag, tag_names), [{"label": "tags", "count": len(tag_names)}]
    if narrowed.category and narrowed.category.lower() not in {n.lower() for n in names}:
        return _missing("category", narrowed.category, names), [{"label": "categories", "count": len(names)}]
    return None


def _in_state(state: str, row: tuple) -> bool:
    """Whether a note is in the state the question names: (pinned, archived
    at, content) is the tail of its row."""
    pinned, archived, content = row[4:7]
    if state == "archived":
        return archived is not None
    if state == "checklist":
        return archived is None and bool(_BOX.search(content or ""))
    return not state or (archived is None and bool(pinned))


def _keeps(narrowed: Narrowed, row: tuple, categories: dict, linked: set[int]) -> bool:
    eid, raw, cid, made = row[:4]
    tags = {t.lower() for t in _tags_of(raw)}
    return (
        (narrowed.linked is None or (eid in linked) == narrowed.linked)
        and (not narrowed.any_tag or bool(tags))
        and (not narrowed.tag or narrowed.tag.lower() in tags)
        and (not narrowed.category or (categories.get(cid) or "").lower() == narrowed.category.lower())
        and _in_state(narrowed.state, row)
        and (narrowed.window is None or narrowed.window[0] <= made.replace(tzinfo=narrowed.window[0].tzinfo) <= narrowed.window[1])
    )


def count(session: Session, narrowed: Narrowed, visible) -> tuple[str, list[dict]] | None:  # noqa: ANN001
    """The sentence and facts for a narrowed count, or None when nothing
    narrows it. `visible` is the live-notes filter of `notebook_stats`."""
    if not narrowed.active:
        return None
    categories = {c.id: c.name for c in session.scalars(select(Category))}
    body = Entry.content if narrowed.state == "checklist" else literal("")
    rows = session.execute(
        visible(select(Entry.id, Entry.tags, Entry.category_id, Entry.created_at, Entry.pinned, Entry.archived_at, body))
    ).all()
    tag_names = sorted({t for row in rows for t in _tags_of(row[1])}, key=str.lower)
    names = sorted({categories[row[2]] for row in rows if row[2] in categories})
    gap = _gap(narrowed, tag_names, names)
    if gap:
        return gap
    linked = _linked_ids(session)
    kept = [row for row in rows if _keeps(narrowed, tuple(row), categories, linked)]
    shown_tag = next((t for t in tag_names if t.lower() == narrowed.tag.lower()), narrowed.tag)
    shown_category = next((n for n in names if n.lower() == narrowed.category.lower()), narrowed.category)
    return _phrase(len(kept), narrowed, shown_category, shown_tag), [{"label": "notes", "count": len(kept)}, {"label": "total", "count": len(rows)}]
