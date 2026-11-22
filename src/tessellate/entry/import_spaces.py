"""The space an imported note goes back to (L979, L-world-class-871): a space of the exported name and
privacy already here, else one made now. Split from export_folder.py, which is at its size cap (L624)."""

from __future__ import annotations

import re

from tessellate.core import paths


def space_for(session, space: object, made: dict) -> str | None:  # noqa: ANN001
    """The id of the space a note was exported from: a space of that name and
    privacy already here, else one made now (L979). None keeps the note in the
    space open. A private space, found or made, is only used with the vault
    open; locked, its note stays in the open space, sealed as it came."""
    from tessellate.core import vault
    from tessellate.core.database import Space
    from tessellate.entry.cleantext import clean_name, name_key

    if not isinstance(space, dict):
        return None
    private = bool(space.get("is_private"))
    if not clean_name(space.get("name")):
        return vault_space(session, made) if private else None
    name = clean_name(space["name"])[:60]
    key = (name_key(name), private)
    if key not in made:
        found = next((sp for sp in session.query(Space) if (name_key(sp.name), bool(sp.is_private)) == key), None)
        if private and vault.key() is None:
            made[key] = None
        elif found is None and key[0] in {"all", "all spaces", "everything"}:
            made[key] = None
        else:
            made[key] = (found or new_space(session, name, space, private)).id
    return made[key]


def vault_space(session, made: dict) -> str | None:  # noqa: ANN001
    """A sealed note exported without its space's name (L-world-class-871):
    the first private space here, made ("Private") when there is none; with
    the vault locked, the open space."""
    from tessellate.core import vault
    from tessellate.core.database import Space

    if vault.key() is None:
        return None
    if None not in made:
        found = session.query(Space).filter(Space.is_private.is_(True)).order_by(Space.id).first()
        made[None] = (found or new_space(session, "Private", {}, True)).id
    return made[None]


def new_space(session, name: str, space: dict, private: bool):  # noqa: ANN001, ANN202
    """A space made for an imported note: an unused ascii id, the exported icon if it is one."""
    from tessellate.core.database import Space

    taken = {sp.id for sp in session.query(Space)} | {"all", "default"}
    base, n = paths.slug(name, 49, ascii_only=True, fallback="space"), 2
    candidate = base
    while candidate in taken:
        suffix = f"-{n}"
        candidate, n = f"{base[: 49 - len(suffix)]}{suffix}", n + 1
    icon = space.get("icon") if isinstance(space.get("icon"), str) and re.fullmatch(r"ph-[a-z0-9-]{1,40}", space["icon"]) else "ph-circles-four"
    found = Space(id=candidate, name=name, icon=icon, is_private=private)
    session.add(found)
    session.flush()
    return found
