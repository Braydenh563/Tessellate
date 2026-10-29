"""A note's properties: the `---` block at the top of its text (GRAPH_PLAN KG4).

The note's text is the source of truth, written the way Obsidian writes it,
so an imported vault keeps its properties and an exported note carries them.
`EntryProperty` is only an index of this, rebuilt on every save.

**Read with the documents' reader.** `core/docmeta.properties` already reads
the subset every editor in the plan's table writes (`key: value`, inline and
block lists, quotes) with its own bounds; this module adds only where the
block ends, so the rest of the app can skip it (a note opening with
properties is named by its first line after them), and a writer.

**The writer rewrites the block and never the body.** A person editing a
property changes the lines between the fences; every character after the
closing fence is copied as it was. A value that would not read back as
itself unquoted (a colon, a leading quote or bracket, a `#`) is quoted.
"""

from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import NoteType
from tessellate.core.docmeta import block_end, properties as read_block

_NEEDS_QUOTES = re.compile(r"""^[\s"'\[{>|*&!%@`-]|:\s|\s#|[,\]]|\s$""")


def split(text: str) -> tuple[dict[str, list[str]], str]:
    """`(properties, body)`; `({}, text)` when there is no block."""
    end = block_end(text)
    if not end:
        return {}, str(text or "")
    return read_block(text), str(text)[end:]


def strip(text: str) -> str:
    """The text after the block, for anything that reads a note's name."""
    end = block_end(text)
    return str(text or "")[end:] if end else str(text or "")


def note_type(props: dict[str, list[str]]) -> str | None:
    values = props.get("type") or []
    return values[0] if values else None


def _scalar(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    text = " ".join(str(value).split())
    if text and _NEEDS_QUOTES.search(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def _line(key: str, value: object) -> str:
    if isinstance(value, (list, tuple)):
        return f"{key}: [{', '.join(_scalar(v) for v in value if str(v).strip())}]"
    text = _scalar(value) if value is not None else ""
    return f"{key}: {text}" if text else f"{key}:"


def write(text: str, props: dict[str, object]) -> str:
    """The text with its block replaced by `props` (or added at the top, or
    removed when `props` is empty); the body is untouched."""
    body = strip(text)
    lines = [_line(" ".join(str(k).split()), v) for k, v in props.items() if str(k).strip()]
    if not lines:
        return body
    return "---\n" + "\n".join(lines) + "\n---\n" + body


#: WORLD_CLASS_PLAN D5's built-in kinds: the five a notebook starts with, so
#: "this note is a person" is one pick rather than a type to design first.
#: Each colour is what the graph's "Note type" rule paints (`routes_graph`).
#: Ordinary rows once seeded: renamed, re-coloured or deleted like any other.
BUILTIN_TYPES: tuple[dict, ...] = (
    {"name": "Person", "icon": "ph-user", "colour": "#2f80ed",
     "fields": [{"name": "role", "kind": "text"}, {"name": "email", "kind": "text"}, {"name": "met", "kind": "date"}]},
    {"name": "Project", "icon": "ph-kanban", "colour": "#76b041",
     "fields": [{"name": "status", "kind": "text"}, {"name": "due", "kind": "date"}, {"name": "people", "kind": "list"}]},
    {"name": "Meeting", "icon": "ph-users-three", "colour": "#e4572e",
     "fields": [{"name": "date", "kind": "date"}, {"name": "attendees", "kind": "list"}, {"name": "project", "kind": "note"}]},
    {"name": "Book", "icon": "ph-book-open", "colour": "#a06cd5",
     "fields": [{"name": "author", "kind": "text"}, {"name": "finished", "kind": "date"}, {"name": "rating", "kind": "number"}]},
    {"name": "Place", "icon": "ph-map-pin", "colour": "#17bebb",
     "fields": [{"name": "address", "kind": "text"}, {"name": "visited", "kind": "date"}]},
)

#: The preference that says the five were offered once. A flag rather than
#: "seed when the table is empty", because a person who deletes every type
#: has said they want none, and a restart must not hand them back.
BUILTINS_SEEDED_PREF = "note_types_seeded"


def ensure_builtin_types(session: Session, config) -> None:  # noqa: ANN001
    """Seed `BUILTIN_TYPES` once per notebook. A name already taken (an
    imported or hand-made "Book") is left as the person made it. `config` is
    the caller's (`deps.get_config()` in a route): reaching for `deps` from
    here put this module in the import_module cycle (ARCH-10's ratchet)."""
    if config.get_preference(BUILTINS_SEEDED_PREF):
        return
    added = False
    for spec in BUILTIN_TYPES:
        if find_type(session, spec["name"]) is None:
            session.add(NoteType(name=spec["name"], icon=spec["icon"], colour=spec["colour"], fields=list(spec["fields"])))
            added = True
    if added:
        session.commit()
    config.set_preference(BUILTINS_SEEDED_PREF, True)


def find_type(session: Session, name: str | None) -> NoteType | None:
    if not name:
        return None
    return session.scalar(select(NoteType).where(func.lower(NoteType.name) == name.strip().lower()))


def with_type_fields(session: Session, content: str, type_name: str, config) -> str:  # noqa: ANN001
    """`content` with `type:` and the type's fields first in its block (KG4).
    A field the note already has keeps its value; an unknown type is written
    as the type alone, which is what an imported vault's notes do."""
    ensure_builtin_types(session, config)
    row = find_type(session, type_name)
    found, _ = split(content)
    props: dict[str, object] = {"type": row.name if row else type_name.strip()}
    for field in (row.fields or []) if row else []:
        name = field.get("name")
        if name and name not in found:
            props[name] = [] if field.get("kind") == "list" else ""
    for key, values in found.items():
        if key != "type":
            props[key] = values if len(values) != 1 else values[0]
    return write(content, props)
