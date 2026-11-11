"""Every reading of a file, in one shape (WORLD_CLASS_PLAN section 10, F10).

"Extracted text, captions and OCR live in three columns with three UIs. The
Files card shows one, hides one, and the search indexes some." Measured when
this was written: a file has up to five places its text can be, the
`caption`, `ocr_text` and `vision_ocr_text` columns on `attachments` and on
`media_uploads`, and per-page rows in `page_reads` for a document read page by
page; the search index read three of them for an attachment and two for an
upload, so an upload read by the vision model, and every page read in the OCR
workspace, could not be found by its words.

**One `readings` table, as a view.** `readings(source, source_id, kind, page,
text, model, ts)` is a SQLite view over those five places, created at startup
(`database_manager.DatabaseManager`) and replaced whenever its definition changes. A
view rather than a table the writers move onto: the four extractors, the
caption editor and the page reader keep writing where they write, and a
derived table cannot drift from them, which a second copy kept in step by
hand eventually does. `source` is "attachment" or "upload", the vocabulary
`page_reads.kind` already uses; `kind` is "caption", "ocr", "vision" or
"page"; `page` is 0 for a reading of the whole file.

`text_of` is what the search index takes for a file's body, every kind.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import object_session

SOURCES = {"attachment": "attachments", "upload": "media_uploads"}
KINDS = ("caption", "ocr", "vision", "page")


def _columns(source: str, table: str) -> str:
    parts = []
    for kind, column, model in (
        ("caption", "caption", "caption_model"),
        ("ocr", "ocr_text", "''"),
        ("vision", "vision_ocr_text", "vision_ocr_model"),
    ):
        parts.append(
            f"SELECT '{source}' AS source, id AS source_id, '{kind}' AS kind, 0 AS page, "
            f"{column} AS text, COALESCE({model}, '') AS model, created_at AS ts "
            f"FROM {table} WHERE {column} IS NOT NULL AND trim({column}) != ''"
        )
    return " UNION ALL ".join(parts)


#: The view's definition. Fixed names only: nothing here comes from a request.
VIEW_SQL = (
    "CREATE VIEW readings AS "
    + " UNION ALL ".join(_columns(source, table) for source, table in SOURCES.items())
    + " UNION ALL SELECT kind AS source, source_id, 'page' AS kind, page, text, "
    "COALESCE(model, '') AS model, created_at AS ts FROM page_reads "
    "WHERE text IS NOT NULL AND trim(text) != ''"
    + " UNION ALL SELECT kind AS source, source_id, 'caption' AS kind, page, caption AS text, "
    "COALESCE(caption_model, '') AS model, created_at AS ts FROM page_reads "
    "WHERE caption IS NOT NULL AND trim(caption) != ''"
)


def ensure_view(connection) -> None:  # noqa: ANN001  # a SQLAlchemy connection
    """Create the view, or replace it when its definition has changed."""
    current = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'view' AND name = 'readings'"
    ).scalar()
    if current == VIEW_SQL:
        return
    connection.exec_driver_sql("DROP VIEW IF EXISTS readings")
    connection.exec_driver_sql(VIEW_SQL)




def text_of(obj, source: str) -> str:  # noqa: ANN001  # an Attachment or a MediaUpload
    """All of a file's readings as one body, for the search index.

    Reads the object's own columns and, through its session, its pages: a
    person searching for a word on page 4 of a scan does not know or care
    which reader found it.
    """
    parts = [getattr(obj, name, None) for name in ("caption", "ocr_text", "vision_ocr_text")]
    session = object_session(obj)
    if session is not None and getattr(obj, "id", None) is not None:
        try:
            pages = session.execute(
                text(
                    "SELECT text, caption FROM page_reads WHERE kind = :source AND source_id = :id "
                    "ORDER BY page"
                ),
                {"source": source, "id": int(obj.id)},
            ).all()
        except Exception:  # noqa: BLE001  # an index row without pages beats no row
            pages = []
        for body, caption in pages:
            parts.extend((body, caption))
    seen: set[str] = set()
    kept = []
    for part in parts:
        part = (part or "").strip()
        if part and part not in seen:
            seen.add(part)
            kept.append(part)
    return "\n".join(kept)
