"""What a document or a file is filed under: tags, a category and properties.

WORLD_CLASS_PLAN decision 65 (L-world-class-392, 393): the selection bars of
the Library's Documents and Media lists do what the Notes bar does, so the two
tables carry the same three things a note does. Every verb here flushes and
never commits (the route owns the transaction) and answers with `before`, the
state of each changed row, which `restore` takes back for one Undo.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.core.database import Category, Document, MediaUpload
from tessellate.entry.manager import category_label, get_or_create_category, tags_from_json
from tessellate.entry.tagnames import normalise_tags
from tessellate.repo import Invalid

MODELS = {"document": Document, "media": MediaUpload}
#: How many properties one row may hold, and how long a name and a value may be.
MAX_PROPERTIES = 50
MAX_NAME = 60
MAX_VALUE = 300


def _model(kind: str):  # noqa: ANN202
    try:
        return MODELS[kind]
    except KeyError:
        raise Invalid(f"kind must be one of {', '.join(MODELS)}.") from None


def properties_of(row) -> dict[str, str]:  # noqa: ANN001
    try:
        loaded = json.loads(row.properties or "{}")
    except (TypeError, ValueError):
        return {}
    return {str(k): str(v) for k, v in loaded.items()} if isinstance(loaded, dict) else {}


def _category_name(session: Session, row) -> str | None:  # noqa: ANN001
    if row.category_id is None:
        return None
    return session.scalar(select(Category.name).where(Category.id == row.category_id))


def state(session: Session, row) -> dict:  # noqa: ANN001
    """One row as the selection bars read and restore it."""
    return {
        "id": row.id,
        "tags": tags_from_json(row.tags),
        "category": _category_name(session, row),
        "properties": properties_of(row),
    }


def _rows(session: Session, kind: str, ids: list[int]) -> list:
    model = _model(kind)
    return list(session.scalars(select(model).where(model.id.in_(ids)).order_by(model.id)))


def read(session: Session, kind: str, ids: list[int]) -> list[dict]:
    return [state(session, row) for row in _rows(session, kind, ids)]


def _retag(row, add_tags: list[str], gone: set[str]) -> None:  # noqa: ANN001
    kept = [t for t in tags_from_json(row.tags) if t.casefold() not in gone]
    row.tags = json.dumps(normalise_tags([*kept, *add_tags]), ensure_ascii=False)


def _set_property(row, name: str, value: str) -> None:  # noqa: ANN001
    props = properties_of(row)
    if value:
        if name not in props and len(props) >= MAX_PROPERTIES:
            raise Invalid(f"A row holds at most {MAX_PROPERTIES} properties.")
        props[name] = value
    else:
        props.pop(name, None)
    row.properties = json.dumps(props, ensure_ascii=False)


def _property_args(prop_name: str | None, prop_value: str | None) -> tuple[str, str]:
    name = (prop_name or "").strip()[:MAX_NAME]
    if prop_name is not None and not name:
        raise Invalid("A property needs a name.")
    return name, (prop_value or "").strip()[:MAX_VALUE]


def _chosen_category(session: Session, category: str | None):  # noqa: ANN202
    if not (category and category.strip()):
        return None
    return get_or_create_category(session, category_label(category))


def bulk_edit(
    session: Session,
    kind: str,
    ids: list[int],
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
    category: str | None = None,
    clear_category: bool = False,
    prop_name: str | None = None,
    prop_value: str | None = None,
) -> list[dict]:
    """Tags added and taken off, a category set or cleared, one property set or
    (with no value) removed, on every chosen row. Answers each row's state
    from before, for `restore`."""
    rows = _rows(session, kind, ids)
    before = [state(session, row) for row in rows]
    add_tags = normalise_tags(add or [])
    gone = {t.casefold() for t in normalise_tags(remove or [], split=False)}
    name, value = _property_args(prop_name, prop_value)
    chosen = _chosen_category(session, category)
    for row in rows:
        if add_tags or gone:
            _retag(row, add_tags, gone)
        if chosen is not None or clear_category:
            row.category_id = chosen.id if chosen is not None else None
        if name:
            _set_property(row, name, value)
    session.flush()
    return before


def restore(session: Session, kind: str, items: list[dict]) -> list[dict]:
    """Put rows back to the given states: the Undo of `bulk_edit`."""
    by_id = {row.id: row for row in _rows(session, kind, [int(i["id"]) for i in items])}
    before = [state(session, row) for row in by_id.values()]
    for item in items:
        row = by_id.get(int(item["id"]))
        if row is None:
            continue
        row.tags = json.dumps(normalise_tags(item.get("tags") or []), ensure_ascii=False)
        wanted = item.get("category")
        row.category_id = get_or_create_category(session, category_label(wanted)).id if wanted else None
        props = {str(k)[:MAX_NAME]: str(v)[:MAX_VALUE] for k, v in list((item.get("properties") or {}).items())[:MAX_PROPERTIES]}
        row.properties = json.dumps(props, ensure_ascii=False)
    session.flush()
    return before
