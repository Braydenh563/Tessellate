"""Bookmarks: saved links, and the two join tables that attach one to a note or
a document. The first resource behind a repository (INBOX 1499); see
`repo/__init__.py` for the rules every repository keeps.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Bookmark, DocumentBookmark, EntryBookmark, utcnow
from tessellate.entry.manager import log_action
from tessellate.repo import Invalid, NotFound

MISSING = "That bookmark could not be found."

#: The same allowlist `safeHref()` in frontend/js/app.js applies to markdown
#: links (`tests/test_markdown_link_schemes.py`): web, mail, phone. A bare
#: host with no scheme at all ("google.com") is not on this list because it
#: never reaches it, see below.
ALLOWED_URL_SCHEMES = ("http", "https", "mailto", "tel")
#: Same shape as the scheme frontend/js/notes-list.js's `safeHref()` looks for
#: (`^[a-z][a-z0-9+.-]*:`): anything before the first colon that reads as a
#: URI scheme, case-insensitively.
_SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.-]*):", re.IGNORECASE)

#: The fields `update` may change, each already cleaned by `clean_fields`.
EDITABLE = ("url", "title", "note", "pinned", "is_read", "group_name")


def normalise_url(raw: str) -> str:
    """"google.com" is what most people actually type into a bookmark box,
    requiring a scheme up front would reject the common case for no benefit,
    since a bare host is unambiguous: it's never meant as a relative path.

    A URL that *does* carry a scheme is checked against `ALLOWED_URL_SCHEMES`
    instead of being stored verbatim: this used to only prepend `https://`
    when a URL had no scheme at all, so `javascript:alert(1)` passed through
    unchanged and was stored exactly as typed. Rejecting it here (422,
    naming the allowed schemes) is the write-time half of the fix; the CSP
    was already a backstop and `library.js` now runs saved URLs through the
    frontend's own `safeHref()` before ever setting `link.href`, so a
    bookmark saved before this existed can't become a live link either.
    """
    url = raw.strip()
    if not url:
        raise Invalid("A bookmark needs a web address.")
    match = _SCHEME_RE.match(url)
    if not match:
        return f"https://{url}"
    scheme = match.group(1).lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        allowed = ", ".join(f"{s}:" for s in ALLOWED_URL_SCHEMES)
        raise Invalid(
            f"Addresses starting with '{scheme}:' are not allowed. Pick one that starts with: {allowed}."
        )
    return url


def clean_fields(fields: dict) -> dict:
    """The given fields as they are stored: the address normalised, text trimmed."""
    out = dict(fields)
    if out.get("url") is not None:
        out["url"] = normalise_url(out["url"])
    for name in ("title", "note", "group_name"):
        if out.get(name) is not None:
            out[name] = out[name].strip()
    return out


def find(session: Session, bookmark_id: int) -> Bookmark | None:
    return session.get(Bookmark, bookmark_id)


def get(session: Session, bookmark_id: int) -> Bookmark:
    bookmark = find(session, bookmark_id)
    if bookmark is None:
        raise NotFound(MISSING)
    return bookmark


def page(session: Session, *, limit: int, offset: int) -> tuple[list[Bookmark], int]:
    """Pinned first, then newest first, one page at a time, and the total.

    The id is a tiebreaker in the ordering, not decoration: two links saved in
    the same second could otherwise swap places between two pages and hide one
    of them, which is the bug a paged list without a stable sort always has.
    """
    total = session.scalar(select(func.count(Bookmark.id))) or 0
    rows = session.scalars(
        select(Bookmark)
        .order_by(Bookmark.pinned.desc(), Bookmark.created_at.desc(), Bookmark.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


def create(session: Session, **fields) -> tuple[Bookmark, int | None]:
    """A new bookmark, and the id of an earlier one with the same address.

    Warn, don't block (asked for directly): re-saving a link you already have
    is a normal thing to do by accident, so the row is still made and the
    caller learns which earlier bookmark shares its URL, for a toast.
    """
    fields = clean_fields(fields)
    twin = session.scalar(select(Bookmark.id).where(Bookmark.url == fields["url"]).limit(1))
    bookmark = Bookmark(**fields)
    session.add(bookmark)
    session.flush()
    log_action(session, "created", "bookmark", bookmark.id, bookmark.title or bookmark.url)
    return bookmark, twin


def everything(session: Session) -> list[Bookmark]:
    """Every saved link, oldest first (an export keeps the order it was saved in)."""
    return list(session.scalars(select(Bookmark).order_by(Bookmark.created_at, Bookmark.id)))


def import_rows(session: Session, rows: list[dict]) -> tuple[list[Bookmark], int]:
    """Save the links of a browser's export; the ones already on the shelf (by address) are skipped.

    A link keeps the day the browser saved it (`added`, seconds since 1970) when that reads as a sane
    date, so a long export does not all land on today. Returns the new rows and the number skipped as
    twins, of the shelf or of an earlier row in the same file.
    """
    have = set(session.scalars(select(Bookmark.url)))
    made: list[Bookmark] = []
    twins = 0
    for row in rows:
        url = row["url"]
        if url in have:
            twins += 1
            continue
        have.add(url)
        bookmark = Bookmark(url=url, title=row.get("title", ""), group_name=row.get("group_name", ""))
        stamp = str(row.get("added") or "")
        if stamp.isdigit():
            try:
                when = datetime.fromtimestamp(int(stamp), tz=timezone.utc).replace(tzinfo=None)
            except (OverflowError, OSError, ValueError):
                when = None
            if when is not None and datetime(1995, 1, 1) <= when <= utcnow().replace(tzinfo=None):
                bookmark.created_at = when
        session.add(bookmark)
        made.append(bookmark)
    session.flush()
    if made:
        log_action(session, "imported", "bookmark", made[0].id, f"{len(made)} bookmarks from a file")
    return made, twins


def update(session: Session, bookmark_id: int, **fields) -> Bookmark:
    """Change the given fields; a field passed as None is left as it was."""
    bookmark = get(session, bookmark_id)
    for name, value in clean_fields(fields).items():
        if name in EDITABLE and value is not None:
            setattr(bookmark, name, value)
    return bookmark


def delete(session: Session, bookmark_id: int) -> None:
    """Delete a saved link, and the two join tables that attach it.

    `EntryBookmark` and `DocumentBookmark` hold real foreign keys with no
    cascade, and `PRAGMA foreign_keys=ON` is set, so a bookmark attached to a
    note or a document could not be deleted at all: the delete raised
    `FOREIGN KEY constraint failed`, answered 500, and the link stayed in the
    list. The join row goes, not the thing at the other end of it: a note does
    not disappear because a link saved on it did.
    """
    bookmark = get(session, bookmark_id)
    log_action(session, "deleted", "bookmark", bookmark.id)
    session.execute(sa_delete(EntryBookmark).where(EntryBookmark.bookmark_id == bookmark.id))
    session.execute(sa_delete(DocumentBookmark).where(DocumentBookmark.bookmark_id == bookmark.id))
    session.delete(bookmark)
    session.flush()


def attached_to_entry(session: Session, entry_id: int) -> list[Bookmark]:
    """A note's References, in the order they were attached."""
    return list(session.scalars(
        select(Bookmark)
        .join(EntryBookmark, EntryBookmark.bookmark_id == Bookmark.id)
        .where(EntryBookmark.entry_id == entry_id)
        .order_by(EntryBookmark.created_at)
    ))


def attach_to_entry(
    session: Session, entry_id: int, bookmark_id: int, *, created_at: datetime | None = None
) -> bool:
    """Attach once (True when a row was added); `created_at` puts an undone
    detach back in its place in the list."""
    get(session, bookmark_id)
    if _entry_join(session, entry_id, bookmark_id) is not None:
        return False
    row = EntryBookmark(entry_id=entry_id, bookmark_id=bookmark_id)
    if created_at is not None:
        row.created_at = created_at.replace(tzinfo=None)
    session.add(row)
    session.flush()
    return True


def detach_from_entry(session: Session, entry_id: int, bookmark_id: int) -> datetime | None:
    """Detach, answering when it was attached (None if it was not), so Undo
    puts it back in its place."""
    row = _entry_join(session, entry_id, bookmark_id)
    attached = row.created_at if row is not None else None
    session.execute(sa_delete(EntryBookmark).where(
        EntryBookmark.entry_id == entry_id, EntryBookmark.bookmark_id == bookmark_id
    ))
    return attached


def _entry_join(session: Session, entry_id: int, bookmark_id: int) -> EntryBookmark | None:
    return session.scalar(select(EntryBookmark).where(
        EntryBookmark.entry_id == entry_id, EntryBookmark.bookmark_id == bookmark_id
    ).limit(1))


def attached_to_document(session: Session, document_id: int, *, by_title: bool = False) -> list[Bookmark]:
    """A document's bookmarks, in attach order (or by title, for Connections)."""
    order = Bookmark.title if by_title else DocumentBookmark.created_at
    return list(session.scalars(
        select(Bookmark)
        .join(DocumentBookmark, DocumentBookmark.bookmark_id == Bookmark.id)
        .where(DocumentBookmark.document_id == document_id)
        .order_by(order)
    ))


def attach_to_document(session: Session, document_id: int, bookmark_id: int) -> bool:
    """Attach once (True when a row was added)."""
    get(session, bookmark_id)
    already = session.scalar(select(DocumentBookmark.id).where(
        DocumentBookmark.document_id == document_id, DocumentBookmark.bookmark_id == bookmark_id
    ).limit(1))
    if already is not None:
        return False
    session.add(DocumentBookmark(document_id=document_id, bookmark_id=bookmark_id))
    session.flush()
    return True


def detach_from_document(session: Session, document_id: int, bookmark_id: int) -> None:
    session.execute(sa_delete(DocumentBookmark).where(
        DocumentBookmark.document_id == document_id, DocumentBookmark.bookmark_id == bookmark_id
    ))
