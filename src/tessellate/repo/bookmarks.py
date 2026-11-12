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
EDITABLE = ("url", "title", "note", "pinned", "is_read", "group_name", "tags", "icon", "color")

#: The highlight colours a link or folder may take (L5): palette keys the stylesheet draws from its tokens
#: (`.look-<key>`), never a free colour, so a dark theme and a light one both stay readable.
COLORS = ("red", "orange", "yellow", "green", "teal", "blue", "purple", "pink", "gray")
#: An icon is a Phosphor name ("ph:star") or a few emoji; markup never gets in.
_ICON_RE = re.compile(r"^ph:[a-z0-9-]{1,60}$")
MAX_EXCERPT = 400
MAX_PAGE_TEXT = 20_000
#: A fetched icon larger than this (as a data address) is not stored.
MAX_FAVICON = 60_000


def clean_icon(raw: str) -> str:
    """"" (automatic), a Phosphor name or a short emoji; anything else is refused."""
    icon = (raw or "").strip()
    if not icon or _ICON_RE.match(icon):
        return icon
    if len(icon) <= 16 and not any(ch in icon for ch in "<>&\"'\\") and not any(ch.isalnum() and ch.isascii() for ch in icon):
        return icon
    raise Invalid("Pick an icon from the list or an emoji.")


def clean_color(raw: str) -> str:
    color = (raw or "").strip().lower()
    if color and color not in COLORS:
        raise Invalid(f"Pick a colour from: {', '.join(COLORS)}.")
    return color

#: A link's tags: how many, and how long one may be. A tag never holds a comma (the stored form is comma-joined).
MAX_TAGS = 12
MAX_TAG_CHARS = 30


def clean_tags(raw: object) -> str:
    """Tags as stored: a list or a comma-separated string, trimmed, one space between words, no '#' lead,
    without repeats (case ignored, the first spelling kept), at most `MAX_TAGS` of `MAX_TAG_CHARS`."""
    parts = raw.split(",") if isinstance(raw, str) else [str(p).replace(",", " ") for p in (raw or [])]
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        tag = " ".join(part.split()).lstrip("#").strip()[:MAX_TAG_CHARS].strip()
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return ",".join(out[:MAX_TAGS])


def tag_list(stored: str | None) -> list[str]:
    """The stored tags as a list."""
    return [t for t in (stored or "").split(",") if t]


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
    if out.get("tags") is not None:
        out["tags"] = clean_tags(out["tags"])
    if out.get("icon") is not None:
        out["icon"] = clean_icon(out["icon"])
    if out.get("color") is not None:
        out["color"] = clean_color(out["color"])
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
        bookmark = Bookmark(
            url=url, title=row.get("title", ""), group_name=row.get("group_name", ""), tags=clean_tags(row.get("tags", ""))
        )
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
            if name == "url" and value != bookmark.url:
                # What was fetched belongs to the old address: a kept icon here was the "saved a website but the
                # icon didn't change" bug. The next fetch (at save, or Refresh) fills it from the new page.
                bookmark.favicon = bookmark.excerpt = bookmark.page_text = ""
            setattr(bookmark, name, value)
    return bookmark


def excerpt_of(text: str) -> str:
    """The first words of a page's text, markdown marks dropped, for the card's two lines."""
    plain = re.sub(r"[#>*_`\[\]]|\(https?://[^)]*\)", " ", text or "")
    return " ".join(plain.split())[:MAX_EXCERPT]


def apply_fetch(bookmark: Bookmark, *, title: str, excerpt: str, text: str, favicon: str) -> None:
    """Keep what a fetch found. The title is only filled in when the link has none (a name the person
    typed is theirs); the icon, excerpt and text always replace the old ones, so a changed site shows."""
    if title and not bookmark.title:
        bookmark.title = title.strip()[:200]
    bookmark.excerpt = " ".join(excerpt.split())[:MAX_EXCERPT]
    bookmark.page_text = text.strip()[:MAX_PAGE_TEXT]
    bookmark.favicon = favicon if len(favicon) <= MAX_FAVICON else ""


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
