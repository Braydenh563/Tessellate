"""Bringing notes in from another app: Notion, Obsidian, Evernote and Apple
Notes (WORLD_CLASS_PLAN H6 and 5.7, row 25).

One reader per app, each turning that app's export into the same plain
record (`Imported`), and one writer (`write`) that makes the notes. The
readers never touch the database and the writer never parses a file, so a
fifth app is one more reader.

**Idempotent by source.** Every note carries a key that names where it came
from, stored in `Entry.source_path` as `<app>:<key>`: Notion's page id,
Evernote's own note fingerprint (title, created time and the start of its
text), the path inside an Obsidian vault or an Apple Notes export. Importing
the same export twice makes nothing the second time; a note whose source
moved on is still the note the person may have edited since, so it is left
alone rather than overwritten, and the summary says how many were already
there. `source_path` is also what `manager.came_from_outside` reads, so an
imported note is text from outside for the agent's injection guard.

**What each export looks like** (checked against the apps' own exports):

- *Notion*, "Markdown & CSV": a zip (sometimes a zip of zips) of
  ``Page Title <32 hex>.md`` files, sub-pages in a folder of the same name,
  links between pages as relative ``.md`` paths. HTML exports are read the
  same way. Database CSVs are the rows' table; their rows are also pages, so
  the CSVs themselves are left out and said so.
- *Obsidian*: a vault, as a zip or as the files themselves with their
  relative paths. YAML front matter gives the category and tags; the
  ``[[wiki links]]`` are kept as written, which this app reads natively.
- *Evernote*: ``.enex``, one XML file per notebook, each ``<note>`` with its
  title, ENML body (XHTML), created time and tags. Parsed with defusedxml
  (no entity expansion, no external fetches); the notebook's file name is
  the category.
- *Apple Notes*: Apple has no bulk export, so this reads what the common
  exporters write: one ``.html``, ``.md`` or ``.txt`` per note in a folder
  per Notes folder. The folder is the category.
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import BinaryIO
from urllib.parse import unquote

SOURCES = ("notion", "obsidian", "evernote", "apple", "memorymap")
LABELS = {"notion": "Notion", "obsidian": "Obsidian", "evernote": "Evernote", "apple": "Apple Notes",
          "memorymap": "a Tessellate folder"}

#: Per file, and over a whole archive once unpacked: a zip bomb stops here.
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
MAX_NOTES = 5000

#: Every pattern here runs on an uploaded file, so none may backtrack
#: quadratically (CodeQL's `py/polynomial-redos`; the final scan measured
#: 2 to 10 s on 20 to 180 KB of the old shapes): a run that could restart at
#: every position is bounded by a character it may not contain (`[^\[\]]`,
#: `[^<>]`), and the Notion id is a fixed-width tail, not a regex.
_NOTION_LINK = re.compile(r"\[([^\[\]]*)\]\(([^()\[\]\s]+?\.(?:md|html))\)")
_HEX = frozenset("0123456789abcdefABCDEF")
_TEXT_SUFFIXES = (".md", ".markdown", ".txt")
_HTML_SUFFIXES = (".html", ".htm")


@dataclass
class Imported:
    key: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    created: datetime | None = None
    #: Front matter keys other than category and tags, kept in the text.
    path: str = ""
    #: A Tessellate folder's sidecar, every field (`export_folder.read`).
    record: dict | None = None
    #: Its attachments, by the file name the sidecar gives.
    files: dict = field(default_factory=dict)


@dataclass
class ReadResult:
    notes: list[Imported] = field(default_factory=list)
    #: "name: reason", one per file or note left out: the import report lists them.
    skipped: list[str] = field(default_factory=list)
    #: What a source carries besides notes (a Tessellate folder's documents).
    extra: dict = field(default_factory=dict)


class TooBig(ValueError):
    pass


# --- files in, files out ------------------------------------------------------


def size_of(data: "bytes | BinaryIO") -> int:
    if isinstance(data, bytes):
        return len(data)
    here = data.tell()
    end = data.seek(0, io.SEEK_END)
    data.seek(here)
    return end


def _bytes(data: "bytes | BinaryIO") -> bytes:
    if isinstance(data, bytes):
        return data
    data.seek(0)
    return data.read()


def expand(files: list[tuple[str, "bytes | BinaryIO"]], skipped: list[str] | None = None,
           max_file: int = MAX_FILE_BYTES) -> list[tuple[str, bytes]]:
    """Every file, with zips (and zips inside zips, one level) opened.

    Nothing is written to disk: members are read into memory, so a name with
    `..` in it is only a string. The sizes are capped as they are read. A
    file left out is named in `skipped`, with why, for the import report.

    A file may be bytes or a seekable file object (the spooled upload, K34):
    a zip is opened from it and read one member at a time, so the upload is
    never held whole in memory beside its members.
    """
    skipped = [] if skipped is None else skipped
    out: list[tuple[str, bytes]] = []
    total = 0

    def add(name: str, data: "bytes | BinaryIO", depth: int) -> None:
        nonlocal total
        if name.lower().endswith(".zip") and depth < 2:
            try:
                archive = zipfile.ZipFile(io.BytesIO(data) if isinstance(data, bytes) else data)
            except zipfile.BadZipFile:
                skipped.append(f"{name}: not a zip that can be opened")
                return
            for info in archive.infolist():
                if info.is_dir():
                    continue
                #: The declared size, checked before a byte is inflated; a
                #: member that lies about it is cut by `read`'s own CRC check.
                total += info.file_size
                if total > MAX_ARCHIVE_BYTES:
                    raise TooBig("That export is larger than 200 MB unpacked.")
                inner = info.filename.replace("\\", "/")
                if inner.startswith("__MACOSX/") or posixpath.basename(inner).startswith("._"):
                    continue
                add(inner, archive.read(info), depth + 1)
            return
        if size_of(data) > max_file and not name.lower().endswith(".enex"):
            skipped.append(f"{name}: larger than {max_file // (1024 * 1024)} MB")
            return
        out.append((name.replace("\\", "/").lstrip("/"), _bytes(data)))

    for name, data in files:
        add(name, data, 0)
    return out


def _text(data: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _title_from_body(body: str) -> str:
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:120]
    return ""


def _with_title(title: str, body: str) -> str:
    """The note's text with its title as the first heading, once."""
    body = body.strip()
    if not title:
        return body
    first = body.split("\n", 1)[0].strip().lstrip("#").strip()
    if first.casefold() == title.casefold():
        return body
    return f"# {title}\n\n{body}" if body else f"# {title}"


def _html_body(html: str) -> str:
    from tessellate.core.docview import html_to_markdown

    return html_to_markdown(html).strip()


# --- Notion -------------------------------------------------------------------


def _notion_name(stem: str) -> tuple[str, str | None]:
    """`("Page Title", "1a2b...")` from `Page Title 1a2b...`."""
    tail = stem[-32:]
    if len(stem) > 32 and stem[-33].isspace() and set(tail) <= _HEX:
        return stem[:-33].strip(), tail.lower()
    return stem.strip(), None


def _notion_links(body: str) -> str:
    """Notion's relative links between pages become `[[wiki links]]`."""

    def swap(match: re.Match) -> str:
        target = unquote(match.group(2))
        if "://" in target:
            return match.group(0)
        stem = posixpath.splitext(posixpath.basename(target))[0]
        title, _ = _notion_name(stem)
        return f"[[{title}]]" if title else match.group(0)

    return _NOTION_LINK.sub(swap, body)


def read_notion(files: list[tuple[str, bytes]]) -> ReadResult:
    result = ReadResult()
    for name, data in files:
        lower = name.lower()
        if lower.endswith(".csv"):
            result.skipped.append(f"{name}: a database table (its rows are imported as pages)")
            continue
        if not lower.endswith(_TEXT_SUFFIXES + _HTML_SUFFIXES):
            continue
        text = _text(data)
        if text is None:
            result.skipped.append(f"{name}: not a text file")
            continue
        stem = posixpath.splitext(posixpath.basename(name))[0]
        title, page_id = _notion_name(stem)
        body = _html_body(text) if lower.endswith(_HTML_SUFFIXES) else text
        body = _notion_links(body)
        if not body.strip() and not title:
            result.skipped.append(f"{name}: empty")
            continue
        parent = posixpath.dirname(name)
        category = _notion_name(posixpath.basename(parent))[0] if parent else None
        result.notes.append(
            Imported(
                key=page_id or name,
                title=title,
                body=_with_title(title, body),
                category=category or None,
                path=name,
            )
        )
    return result


# --- Obsidian -----------------------------------------------------------------


def read_obsidian(files: list[tuple[str, bytes]], parse_frontmatter) -> ReadResult:  # noqa: ANN001
    """`parse_frontmatter` is the markdown importer's own (routes_settings),
    passed in so a vault reads exactly as the existing Import markdown reads
    it, front matter properties kept in the text included."""
    result = ReadResult()
    for name, data in files:
        parts = name.split("/")
        if any(p.startswith(".") for p in parts):  # .obsidian/, .trash/
            continue
        if not name.lower().endswith(_TEXT_SUFFIXES):
            continue
        text = _text(data)
        if text is None:
            result.skipped.append(f"{name}: not a text file")
            continue
        meta, body = parse_frontmatter(text)
        if not body.strip():
            result.skipped.append(f"{name}: empty")
            continue
        tags = meta.get("tags") or []
        result.notes.append(
            Imported(
                key=name,
                title=posixpath.splitext(parts[-1])[0],
                body=body.strip(),
                tags=list(tags) if isinstance(tags, list) else [str(tags)],
                category=meta.get("category") or None,
                created=meta.get("created"),
                path=name,
            )
        )
    return result


# --- Evernote -----------------------------------------------------------------


def _enex_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Evernote writes UTC; the notebook stores naive UTC (`utcnow`).
        return datetime.strptime(value.strip(), "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None


def _enml(content: str) -> str:
    """An ENML body as markdown: `en-media` (an attached file the export
    carries as base64 elsewhere) and Evernote check boxes become words, the rest is
    XHTML."""
    content = re.sub(r"<\?xml[^<>]*\?>|<!DOCTYPE[^<>]*>", "", content or "")
    content = re.sub(r"<en-todo\s+checked=\"true\"\s*/>", "[x] ", content)
    content = re.sub(r"<en-todo[^<>]*/>", "[ ] ", content)
    #: An `en-media` element is empty in ENML, so its opening tag is the
    #: attachment and a closing tag is dropped; matching open-to-close with a
    #: lazy `.*?` scanned to the end of the file once per unclosed tag.
    content = re.sub(r"<en-media[^<>]*>", " [attachment] ", content)
    content = content.replace("</en-media>", "")
    content = content.replace("<en-note", "<div").replace("</en-note>", "</div>")
    return _html_body(content)


def read_evernote(files: list[tuple[str, bytes]]) -> ReadResult:
    from defusedxml import ElementTree

    result = ReadResult()
    for name, data in files:
        if not name.lower().endswith(".enex"):
            continue
        try:
            root = ElementTree.fromstring(data)
        except Exception as exc:  # noqa: BLE001  # defusedxml refuses entities by raising
            result.skipped.append(f"{name}: not a readable Evernote export ({type(exc).__name__})")
            continue
        notebook = posixpath.splitext(posixpath.basename(name))[0]
        for note in root.iter("note"):
            title = (note.findtext("title") or "").strip()
            content = note.findtext("content") or ""
            created = note.findtext("created")
            body = _enml(content)
            if not body and not title:
                result.skipped.append(f"{name}: an empty note")
                continue
            fingerprint = hashlib.sha1(f"{title}\n{created}\n{body[:200]}".encode("utf-8")).hexdigest()[:20]
            result.notes.append(
                Imported(
                    key=fingerprint,
                    title=title,
                    body=_with_title(title, body),
                    tags=[t.text.strip() for t in note.findall("tag") if t.text and t.text.strip()],
                    category=notebook or None,
                    created=_enex_time(created),
                    path=f"{name}#{title[:80]}",
                )
            )
    return result


# --- Apple Notes --------------------------------------------------------------


def read_apple(files: list[tuple[str, bytes]]) -> ReadResult:
    result = ReadResult()
    for name, data in files:
        lower = name.lower()
        if not lower.endswith(_TEXT_SUFFIXES + _HTML_SUFFIXES):
            continue
        text = _text(data)
        if text is None:
            result.skipped.append(f"{name}: not a text file")
            continue
        body = _html_body(text) if lower.endswith(_HTML_SUFFIXES) else text.strip()
        if not body:
            result.skipped.append(f"{name}: empty")
            continue
        title = posixpath.splitext(posixpath.basename(name))[0].strip() or _title_from_body(body)
        folder = posixpath.basename(posixpath.dirname(name))
        result.notes.append(Imported(key=name, title=title, body=_with_title(title, body), category=folder or None, path=name))
    return result


def read(source: str, files: list[tuple[str, "bytes | BinaryIO"]], parse_frontmatter=None) -> ReadResult:  # noqa: ANN001
    if source not in SOURCES:
        raise ValueError(source)
    skipped: list[str] = []
    result = _read_expanded(source, expand(files, skipped, _max_file(source)), parse_frontmatter)
    result.skipped[:0] = skipped
    if len(result.notes) > MAX_NOTES:
        result.skipped.append(f"{len(result.notes) - MAX_NOTES} more notes past the {MAX_NOTES} one import takes")
        result.notes = result.notes[:MAX_NOTES]
    return result


def _max_file(source: str) -> int:
    from tessellate.entry import export_folder

    return export_folder.MAX_ATTACHMENT_BYTES if source == "memorymap" else MAX_FILE_BYTES


def _read_expanded(source: str, expanded: list[tuple[str, bytes]], parse_frontmatter) -> ReadResult:  # noqa: ANN001
    if source == "memorymap":
        from tessellate.entry import export_folder

        notes, skipped, extra = export_folder.read(expanded, parse_frontmatter)
        return ReadResult(notes=[Imported(**note) for note in notes], skipped=skipped, extra=extra)
    if source == "notion":
        result = read_notion(expanded)
    elif source == "obsidian":
        result = read_obsidian(expanded, parse_frontmatter)
    elif source == "evernote":
        result = read_evernote(expanded)
    else:
        result = read_apple(expanded)
    return result


# --- the day a note was written (CHAT_PLAN section 2, the import row) -------------

#: The property lines an export writes the day under: Obsidian's `date:` and
#: `created:`, Notion's "Created:" and "Created time:", a hand-made "Written:".
_WRITTEN_KEYS = re.compile(r"^\s*(?:created(?: time| at| on)?|date(?: created)?|written(?: on)?)\s*:\s*(.+?)\s*$", re.I | re.M)
_YEAR = re.compile(r"\b\d{4}\b")


def _absolute_day(text: str) -> datetime | None:
    """The first day in `text` said with its year, read by the one
    recogniser (decision 46): "2024-03-14", "March 14, 2024 9:41 AM",
    "14 March 2024". A day said without a year ("friday", "tomorrow") is
    relative to a moment the export does not record, so it is not read."""
    from tessellate.ai import recognise

    for span in recognise.recognise(text, now=datetime.now(timezone.utc)):
        if span.rank or span.kind not in ("date", "datetime") or not _YEAR.search(span.text):
            continue
        value = span.value
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
        #: Midday, so the day stays the day in every zone the timeline is read in.
        return datetime.combine(value, time(12))
    return None


def written_on(title: str, body: str) -> datetime | None:
    """The day a note says it was written: a `created:` or `date:` line in
    its first lines, else its title (a daily note named "2024-03-14"). None
    when neither names a day with its year."""
    head = "\n".join((body or "").split("\n")[:12])
    for found in _WRITTEN_KEYS.finditer(head):
        day = _absolute_day(found.group(1))
        if day is not None:
            return day
    return _absolute_day(title or "")


def people_and_places(body: str) -> dict:
    """The people and places a note names, as the recogniser reads them, for
    the import's summary."""
    from tessellate.ai import recognise

    found: dict[str, set[str]] = {"person": set(), "place": set()}
    for span in recognise.recognise((body or "")[:20000], now=datetime.now(timezone.utc)):
        if span.kind in found and not span.rank:
            found[span.kind].add(span.text)
    return {"people": sorted(found["person"]), "places": sorted(found["place"])}


# --- the writer ---------------------------------------------------------------


def source_key(source: str, key: str) -> str:
    """What `Entry.source_path` holds for an imported note: the app and its key."""
    return f"{source}:{key}"[:500]


def _already_here(session, keys: list[str]) -> set[str]:  # noqa: ANN001
    from sqlalchemy import select

    from tessellate.core.database import Entry

    existing: set[str] = set()
    for at in range(0, len(keys), 500):
        existing.update(
            session.scalars(
                select(Entry.source_path).where(Entry.source_path.in_(keys[at : at + 500]), Entry.is_deleted.is_(False))
            ).all()
        )
    return existing


#: Most people, and most places, a note gets as tags from what it names.
NAME_TAGS_PER_KIND = 3


def name_tags(names: dict) -> list[str]:
    """The people and places a note names, as the tags it is written with (L575):
    the names as written, a few of each so a note that lists a whole team is not
    one tag per member."""
    return [*names["people"][:NAME_TAGS_PER_KIND], *names["places"][:NAME_TAGS_PER_KIND]]


def _make(session, note: Imported, key: str, names: dict | None = None):  # noqa: ANN001, ANN202
    from tessellate.entry import manager

    entry = manager.create_entry(
        session,
        note.body,
        category_name=note.category or manager.UNCATEGORISED,
        tags=[*note.tags, *name_tags(names or {"people": [], "places": []})],
        ai_confidence=100 if note.category else 0,
        commit=False,
        dates=False,
    )
    entry.source_path = key
    if note.category:
        entry.user_filed = True  # the app it came from said where it belongs
    created = note.created or written_on(note.title, note.body)
    if created is not None:
        entry.created_at = created
    #: "Tomorrow" in a note from 2024 meant a day in 2024: the dated mentions
    #: are read once, on the day the note was written (`dates=False` above).
    manager.record_dates(session, entry)
    return entry


#: The most rows one preview lists: a vault can hold tens of thousands, and a
#: list nobody can scroll is not a preview. Notes past it still import.
PREVIEW_LIMIT = 1000


def preview(session, source: str, notes: list[Imported], limit: int = PREVIEW_LIMIT) -> dict:  # noqa: ANN001
    """What a run would make, without making it (INBOX 1520, S36): a row per
    note with its title, the first words, where it came from and whether it is
    already here, so the person can untick before anything is written."""
    shown = notes[:limit]
    existing = _already_here(session, [source_key(source, n.key) for n in shown])
    rows = []
    for note in shown:
        body = " ".join(note.body.split())
        if body.startswith(note.title):
            body = body[len(note.title):].strip()
        rows.append({
            "key": note.key,
            "title": note.title or "Untitled",
            "snippet": body[:140],
            "path": note.path,
            "tags": note.tags[:5],
            "already": source_key(source, note.key) in existing,
        })
    return {"notes": rows, "more": max(0, len(notes) - len(shown))}


def write(session, source: str, notes: list[Imported], progress=None) -> dict:  # noqa: ANN001
    """Make the notes that are not already here. Returns the counts and ids.

    `progress` (`export_folder.Progress`) is told every hundred notes and
    asked before each one whether to stop; every hundred notes are
    committed (and the rest at the end or on a stop), so a stop keeps what was written."""
    from tessellate.entry import export_folder

    progress = progress or export_folder.Progress()
    keys = [source_key(source, n.key) for n in notes]
    existing = _already_here(session, keys)
    ids: list[int] = []
    made: list = []
    seen: set[str] = set()
    already = 0
    named: dict[str, set[str]] = {"people": set(), "places": set()}
    stopped = False
    for done, (note, key) in enumerate(zip(notes, keys), 1):
        if progress.stopped is not None and progress.stopped():
            stopped = True
            break
        if progress.step is not None and done % progress.every == 0:
            progress.step(done, len(notes))
        if key in existing or key in seen:
            already += 1
            continue
        seen.add(key)
        names = people_and_places(note.body)
        entry = _make(session, note, key, names)
        for kind, found in names.items():
            named[kind].update(found)
        ids.append(entry.id)
        made.append(entry)
        if done % progress.every == 0:
            session.commit()  # in batches, not one fsync per note
    session.commit()
    return {"imported": len(ids), "already": already, "ids": ids, "entries": made, "stopped": stopped,
            "people": sorted(named["people"])[:50], "places": sorted(named["places"])[:50]}
