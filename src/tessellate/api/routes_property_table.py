"""Notes as a table, read-only (a document's ```base block; DOCUMENTS_PLAN gap row 6).

The query is over the properties index (`repo/properties.py`, `table`): notes
of a type, or with a property equal to a value, and the values of some named
properties. It writes nothing and holds no ORM calls of its own.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tessellate.ai.study import title_of
from tessellate.core.deps import get_session
from tessellate.repo import properties

router = APIRouter(tags=["properties"])

MAX_COLUMNS = 12
MAX_CONDITIONS = 6


@router.get("/property-table")
def property_table(
    type: str = Query(default="", max_length=60),
    where: list[str] = Query(default_factory=list, max_length=MAX_CONDITIONS),
    columns: str = Query(default="", max_length=600),
    sort: str = Query(default="", max_length=60),
    desc: bool = False,
    limit: int = Query(default=100, ge=1, le=properties.TABLE_ROWS),
    session: Session = Depends(get_session),
) -> dict:
    """`where` is `property=value`, repeated; `columns` is comma separated."""
    conditions: list[tuple[str, str]] = []
    for text in where:
        key, sep, value = text.partition("=")
        if not sep or not key.strip():
            raise HTTPException(status_code=422, detail="A condition reads property=value.")
        conditions.append((key.strip(), value.strip()))
    names = [c.strip() for c in columns.split(",") if c.strip()][:MAX_COLUMNS]
    if not (type.strip() or conditions or names):
        raise HTTPException(status_code=422, detail="Name a type, a condition or some columns.")
    rows, total = properties.table(
        session, kind=type, where=conditions, columns=names, sort=sort, descending=desc, limit=limit
    )
    return {
        "columns": names,
        "total": total,
        "rows": [
            {"id": r["id"], "title": title_of(r["content"]) or "Untitled note", "values": r["values"]} for r in rows
        ],
    }
