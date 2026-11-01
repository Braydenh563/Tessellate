"""Kinds of link (GRAPH_PLAN KG3, INBOX 528): the six built-ins (`LINK_TYPES`)
and the ones a person adds (`RelationType`), each with the name it has from
the other end. The second resource behind a repository (INBOX 1499); the rules
every repository keeps are in `repo/__init__.py`.

A custom kind's key is its name made safe (`part_of`), which is what
`EntryLink.link_type` stores, so a rename never touches a link. Deleting one
leaves its links untyped, never gone, and a restore types them again.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from tessellate.core.database import LINK_TYPE_INVERSES, LINK_TYPES, EntryLink, RelationType
from tessellate.repo import Conflict, Invalid, NotFound, ReadOnly

#: A kind's colour is a palette key or `#rrggbb`, as a category's is.
_COLOUR = re.compile(r"^(#[0-9a-fA-F]{6}|[a-z]{3,12})$")
_CACHE = "relation_types"
#: Links retyped per statement on a restore, under SQLite's variable limit.
_CHUNK = 500


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")[:24]


def _clean(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    return text[:60] or None


def _colour(value: str | None) -> str | None:
    if value and not _COLOUR.match(value):
        raise Invalid("A colour is a palette name or #rrggbb.")
    return value or None


def kinds(session: Session) -> dict[str, dict]:
    """Every kind of link this notebook knows, by key: the built-ins (with
    `LINK_TYPE_INVERSES`) then the custom ones by name. Kept on the session
    for the request (a notes list reads it once per note); a write here drops
    it (`forget`)."""
    cached = session.info.get(_CACHE)
    if cached is not None:
        return cached
    out: dict[str, dict] = {}
    for key, label in LINK_TYPES.items():
        inverse = LINK_TYPE_INVERSES.get(key)
        out[key] = {
            "key": key,
            "name": label.split(":", 1)[0],
            "description": label.split(":", 1)[-1].strip(),
            "inverse": inverse,
            "directed": inverse is not None,
            "colour": None,
            "built_in": True,
        }
    for row in session.scalars(select(RelationType).order_by(RelationType.name)):
        out[row.key] = {
            "key": row.key,
            "name": row.name,
            "description": "",
            "inverse": row.inverse,
            "directed": bool(row.directed),
            "colour": row.colour,
            "built_in": False,
        }
    session.info[_CACHE] = out
    return out


def forget(session: Session) -> None:
    session.info.pop(_CACHE, None)


def _fresh(session: Session, key: str) -> dict:
    session.flush()
    forget(session)
    return kinds(session)[key]


def _custom(session: Session, key: str) -> RelationType:
    row = session.scalar(select(RelationType).where(RelationType.key == key))
    if row is None:
        if key in kinds(session):
            raise ReadOnly("The built-in kinds of link can't be changed.")
        raise NotFound("That kind of link could not be found.")
    return row


def create(
    session: Session,
    *,
    name: str,
    inverse: str | None = None,
    directed: bool = True,
    colour: str | None = None,
    key: str | None = None,
    link_ids: Iterable[int] = (),
) -> dict:
    """A new custom kind. `key` and `link_ids` are Undo's (undo-1005): a
    deleted kind made again under its old key (a rename kept it), and the
    links its delete untyped take it back unless they have another since."""
    cleaned = _clean(name)
    key = _key(key) if key else _key(cleaned or "")
    if not cleaned or not key:
        raise Invalid("A kind of link needs a name.")
    known = kinds(session)
    if key in known or any(k["name"].casefold() == cleaned.casefold() for k in known.values()):
        raise Conflict("There is already a kind of link with that name.")
    session.add(RelationType(key=key, name=cleaned, inverse=_clean(inverse), directed=directed, colour=_colour(colour)))
    ids = list(link_ids)
    links = EntryLink.__table__  # every space's, as the delete was
    for start in range(0, len(ids), _CHUNK):
        chunk = ids[start:start + _CHUNK]
        session.execute(
            sa_update(links).where(links.c.id.in_(chunk), links.c.link_type.is_(None)).values(link_type=key)
        )
    return _fresh(session, key)


def update(session: Session, key: str, fields: dict) -> dict:
    """Change the fields present in `fields` (a None inverse or colour clears it)."""
    row = _custom(session, key)
    if "name" in fields:
        name = _clean(fields["name"])
        if not name:
            raise Invalid("A kind of link needs a name.")
        row.name = name
    if "inverse" in fields:
        row.inverse = _clean(fields["inverse"])
    if fields.get("directed") is not None:
        row.directed = fields["directed"]
    if "colour" in fields:
        row.colour = _colour(fields["colour"])
    return _fresh(session, key)


def delete(session: Session, key: str) -> tuple[int, dict]:
    """Delete a custom kind: how many links it left untyped, and everything
    Undo needs to put it back exactly (the row and which links carried it).

    On the table, not the mapped class: a kind is the whole notebook's, and an
    ORM statement here took the request's space filter, so a delete made while
    one space was open left that kind on every other space's links.
    """
    row = _custom(session, key)
    links = EntryLink.__table__
    link_ids = list(session.scalars(select(links.c.id).where(links.c.link_type == key)))
    restore = {
        "key": row.key, "name": row.name, "inverse": row.inverse,
        "directed": bool(row.directed), "colour": row.colour, "link_ids": link_ids,
    }
    untyped = session.execute(sa_update(links).where(links.c.link_type == key).values(link_type=None)).rowcount
    session.delete(row)
    session.flush()
    forget(session)
    return untyped or 0, restore
