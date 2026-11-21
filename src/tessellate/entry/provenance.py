"""Where a note came from, said in one word and one label (L-general-13).

Derived from columns every such note already carries, so nothing is
migrated: a clipped page has `source_url`, an imported file or a document
section has `source_path` (the importers set it, see `manager.came_from_outside`),
and a note a recording was made into has a `Recording` row with a transcript.
A note typed by hand has none of them and gets no kind.
"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Recording

#: What the document importer (markitdown) takes beyond plain text and markdown.
#: A section of one of these is "extracted from a document"; a `.md` or `.txt`
#: from a folder import is "imported from a file".
DOCUMENT_SUFFIXES = frozenset(
    {"pdf", "doc", "docx", "odt", "rtf", "epub", "ppt", "pptx", "odp", "xls", "xlsx", "ods", "html", "htm"}
)

#: The apps `entry/app_import.py` writes as `<app>:<key>` into `source_path`.
APP_LABELS = {
    "notion": "Notion",
    "obsidian": "Obsidian",
    "evernote": "Evernote",
    "apple": "Apple Notes",
    "memorymap": "a Tessellate folder",
}


def transcribed_ids(session: Session, ids: list[int]) -> set[int]:
    """Which of these notes have a recording with a transcript, in one query."""
    if not ids:
        return set()
    found: set[int] = set()
    for at in range(0, len(ids), 500):
        rows = session.execute(
            select(Recording.entry_id)
            .where(
                Recording.entry_id.in_(ids[at : at + 500]),
                Recording.deleted_at.is_(None),
                Recording.segments.not_in(("", "[]")),
            )
            .distinct()
        )
        found.update(row[0] for row in rows)
    return found


def source_kind(source_url: str | None, source_path: str | None, transcribed: bool = False) -> tuple[str, str]:
    """`(kind, label)`, kind one of "url", "document", "file", "audio" or "" for
    a note typed by hand. The label is sentence case and says the origin."""
    if source_url:
        host = (urlparse(source_url).hostname or "").removeprefix("www.")
        return "url", f"Clipped from {host}" if host else "Clipped from a web page"
    path = (source_path or "").strip()
    if path:
        app, _, key = path.partition(":")
        if key and app in APP_LABELS:
            return "file", f"Imported from {APP_LABELS[app]}"
        name = path.rsplit("/", 1)[-1]
        suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if name == "document":
            return "document", "Extracted from a document"
        if suffix in DOCUMENT_SUFFIXES:
            return "document", f"Extracted from {name}"
        return "file", f"Imported from {name}"
    if transcribed:
        return "audio", "Transcribed from audio"
    return "", ""
