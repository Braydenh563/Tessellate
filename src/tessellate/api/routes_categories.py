"""Category management: list, create, rename, merge, split, move and delete.

Categories are created implicitly by the AI as it files notes, so over time
they drift: near-duplicates, typos, ones that stopped being useful. These
endpoints are how the user tidies that up.

None of them ever loses a note: renaming onto an existing category merges the
two, and deleting one moves its notes to Uncategorised or to a category named
for them.

**Everything the agent can do, a person can** (INBOX 431 (e), the owner: "the
user needs to be able to easily do anything the ai can do"). Create and merge
call the agent's own tool functions (`ai/tools/categories.py`), so the two
paths cannot come to disagree about what a merge is; moving chosen notes, a
split and a proposed split are what managing by hand needs besides. Every
answer that moves notes names them (`moved_ids`, or `previous` with each
note's old category), which is what the Manage categories panel's undo uses.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError
from tessellate.ai.tools.categories import _create_category, _merge_categories
from tessellate.core.database import Entry
from tessellate.core import deps
from tessellate.core.deps import get_session
from tessellate.entry import manager, moving
from tessellate.entry import manager_categories
from tessellate.entry import manager_text
from tessellate.repo import categories as categories_repo

router = APIRouter(prefix="/categories", tags=["categories"])


class RenameBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


#: The swatches the Manage categories panel offers, in the order it draws them
#: (notes-list.js `CATEGORY_PALETTE` holds the same keys with their hexes, and
#: `tests/test_category_colour.py` compares the two). Twelve hues picked so each
#: reads at 3:1 or better as a dot on both the lightest and the darkest surface
#: of either theme, so one hex serves light and dark.
CATEGORY_PALETTE_KEYS = (
    "red", "orange", "amber", "lime", "green", "teal",
    "cyan", "blue", "indigo", "violet", "magenta", "pink",
)
_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


class ColourBody(BaseModel):
    """A palette key, a `#rrggbb` hex, or null for automatic.

    Required, so an empty body is refused rather than read as "clear". The
    value ends up in a CSS custom property and a canvas fill, so nothing but
    these two shapes is ever stored: no named colours, no `rgb()`, no
    whitespace, nothing a stylesheet could be talked into reading as more.
    """

    colour: str | None

    @field_validator("colour")
    @classmethod
    def _known_colour(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value in CATEGORY_PALETTE_KEYS:
            return value
        if _HEX_COLOUR.fullmatch(value):
            return value.lower()
        raise ValueError("Pick one of the swatches, or a #rrggbb colour")


class CreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"\S")
    description: str = Field(default="", max_length=500)


class MergeBody(BaseModel):
    into: int


class MoveBody(BaseModel):
    entry_ids: list[int] = Field(min_length=1, max_length=5000)
    category: str = Field(min_length=1, max_length=100)
    #: An undo's own: how the notes were filed before the move it reverses.
    user_filed: bool | None = None


class SplitBody(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"\S")
    entry_ids: list[int] = Field(min_length=1, max_length=5000)


def _existing_category(session: Session, category_id: int):  # noqa: ANN202
    category = categories_repo.find(session, category_id)
    if category is None:
        raise HTTPException(status_code=400, detail="That category no longer exists.")
    return category


def _same_space(source, target) -> None:  # noqa: ANN001
    """Refuse folding a category into one of another space.

    Only the "All spaces" view can even name both, and a merge there would
    point one space's notes at a category their own space cannot list: in
    that space they would read as Uncategorised (measured 2026-10-03). Moving
    notes between spaces is the space picker's job, not a category merge's.
    """
    if (source.workspace_id or "default") != (target.workspace_id or "default"):
        raise HTTPException(
            status_code=400,
            detail="Those categories are in different spaces, so they can't be merged.",
        )


def _ids_in(session: Session, category_id: int) -> list[int]:
    return list(session.scalars(select(Entry.id).where(Entry.category_id == category_id)))


def _move(session: Session, entries: list, name: str, user_filed: bool | None = None) -> list[dict]:
    """Move notes into a category by name (made if new); `entry/moving.py`."""
    return moving.to_category(session, entries, name, user_filed)


#: Same reasoning as the tag list: this feeds the sidebar and every filing
#: picker, so it is not a list anyone pages through. The cap exists so one
#: response cannot grow without limit, and `X-Total-Count` says when it bit.
CATEGORIES_PAGE_SIZE = 1000


@router.get("")
def list_categories(
    response: Response,
    limit: int = Query(default=CATEGORIES_PAGE_SIZE, ge=1, le=5000),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Every category with its live note count, biggest first."""
    rows = manager_categories.all_categories(session)
    response.headers["X-Total-Count"] = str(len(rows))
    return rows[:limit]


@router.post("", status_code=201)
def create_category(body: CreateBody, session: Session = Depends(get_session)) -> dict:
    """Make a category (the agent's `create_category`); an existing name is kept."""
    try:
        result = _create_category(session, {"name": body.name, "description": body.description})
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"name": result["name"], "created": result["created"]}


@router.post("/move")
def move_notes(body: MoveBody, session: Session = Depends(get_session)) -> dict:
    """Move chosen notes into a category, made if it does not exist yet."""
    entries = list(session.scalars(select(Entry).where(Entry.id.in_(body.entry_ids), Entry.is_deleted == False)))  # noqa: E712
    previous = _move(session, entries, body.category.strip(), body.user_filed)
    return {"category": body.category.strip(), "moved": len(previous), "previous": previous}


@router.post("/{category_id}/merge")
def merge_category(category_id: int, body: MergeBody, session: Session = Depends(get_session)) -> dict:
    """Fold this category into another (the agent's `merge_categories`)."""
    source = _existing_category(session, category_id)
    target = _existing_category(session, body.into)
    _same_space(source, target)
    moved_ids = _ids_in(session, source.id)
    try:
        result = _merge_categories(session, {"from": source.name, "into": target.name})
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"from": result["from"], "into": result["into"], "moved": result["notes_moved"], "moved_ids": moved_ids}


@router.post("/{category_id}/split")
def split_category(category_id: int, body: SplitBody, session: Session = Depends(get_session)) -> dict:
    """Move the chosen notes of this category into a new (or existing) one."""
    source = _existing_category(session, category_id)
    entries = list(
        session.scalars(select(Entry).where(Entry.id.in_(body.entry_ids), Entry.category_id == source.id))
    )
    previous = _move(session, entries, body.name.strip())
    return {"from": source.name, "name": body.name.strip(), "moved_ids": [p["id"] for p in previous]}


#: A proposed split never names a group smaller than this: two notes that
#: share a tag are a theme, one is a coincidence.
SPLIT_MIN_GROUP = 2


#: The AI proposal's prompt, and how much of each note it is shown: enough to
#: say what a note is about, little enough that a big category still fits a
#: small model's window.
SPLIT_PROMPT = (
    "You are grouping a person's notes. All of them are filed in the category "
    "\"{category}\". Propose how to split it into two to five smaller, clearly "
    "named categories. Only group notes that belong together; leave the rest out. "
    "Answer with JSON only, in this shape: "
    '{{"groups": [{{"name": "Short name", "notes": [1, 2]}}]}} '
    "using the note numbers given."
)
SPLIT_NOTE_CHARS = 160
SPLIT_MAX_NOTES = 60

logger = logging.getLogger("tessellate.categories")


def _ai_groups(source, entries: list) -> list[dict] | None:
    """The utility model's split, or None when it is off or answers nonsense.

    Only note ids that are really in the category survive, each note in one
    group, a group needs two notes, and a name is trimmed to what a category
    name may be. Anything else falls back to the tags, which never need the
    model.
    """
    ollama = deps.get_ollama()
    if not ollama.is_running() or not entries:
        return None
    shown = entries[:SPLIT_MAX_NOTES]
    lines = "\n".join(
        f"{e.id}: {' '.join((manager_text.readable_content(e) or '').split())[:SPLIT_NOTE_CHARS]}" for e in shown
    )
    try:
        reply = ollama.chat(
            deps.get_model_manager().utility_model(),
            [
                {"role": "system", "content": SPLIT_PROMPT.format(category=source.name)},
                {"role": "user", "content": lines},
            ],
        )
    except Exception:  # noqa: BLE001  # any model failure falls back to tags
        logger.warning("the AI split proposal failed", exc_info=True)
        return None
    text = reply.get("content", "") if isinstance(reply, dict) else ""
    found = re.search(r"\{.*\}", text or "", re.S)
    try:
        raw = json.loads(found.group(0)) if found else None
    except ValueError:
        raw = None
    if not isinstance(raw, dict) or not isinstance(raw.get("groups"), list):
        return None
    valid = {e.id for e in shown}
    used: set[int] = set()
    groups = []
    for group in raw["groups"]:
        if not isinstance(group, dict):
            continue
        name = " ".join(str(group.get("name") or "").split())[:100]
        ids = [int(i) for i in group.get("notes") or [] if isinstance(i, (int, str)) and str(i).isdigit()]
        ids = [i for i in dict.fromkeys(ids) if i in valid and i not in used]
        if name and len(ids) >= SPLIT_MIN_GROUP:
            used.update(ids)
            groups.append({"name": name, "entry_ids": ids})
    return groups or None


@router.post("/{category_id}/split/propose")
def propose_split(
    category_id: int,
    ai: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> dict:
    """Suggest how this category could split, for the person to review.

    With `ai`, the utility model reads the notes and proposes named groups
    (`basis: "ai"`). Otherwise, or when the model is off or answers nonsense,
    grouped by the notes' own tags (which the filing AI wrote or the person
    did): each note goes to its most shared tag, a tag is a group when two or
    more notes share it and not every note has it (`basis: "tags"`). Nothing
    is moved; the panel shows the groups as a split the person can edit and
    apply.
    """
    source = _existing_category(session, category_id)
    entries = list(
        session.scalars(select(Entry).where(Entry.category_id == source.id, Entry.is_deleted == False))  # noqa: E712
    )
    if ai:
        proposed = _ai_groups(source, entries)
        if proposed:
            grouped = {i for g in proposed for i in g["entry_ids"]}
            return {"from": source.name, "groups": proposed, "rest": len(entries) - len(grouped), "basis": "ai"}
    tags_of = {e.id: [t.lower() for t in manager.entry_tags(e)] for e in entries}
    shared = Counter(t for tags in tags_of.values() for t in set(tags))
    useful = {t for t, n in shared.items() if SPLIT_MIN_GROUP <= n < len(entries)}
    groups: dict[str, list[int]] = {}
    for entry in entries:
        mine = [t for t in tags_of[entry.id] if t in useful]
        if mine:
            best = max(mine, key=lambda t: (shared[t], t))
            groups.setdefault(best, []).append(entry.id)
    kept = [{"name": name, "entry_ids": ids} for name, ids in groups.items() if len(ids) >= SPLIT_MIN_GROUP]
    kept.sort(key=lambda g: (-len(g["entry_ids"]), g["name"]))
    grouped = {i for g in kept for i in g["entry_ids"]}
    return {
        "from": source.name,
        "groups": kept,
        "rest": len(entries) - len(grouped),
        "basis": "tags",
        #: Said when the AI was asked and could not help, so the panel can
        #: say why the groups are the tags' instead.
        "ai_unavailable": ai,
    }


@router.put("/{category_id}/colour")
def set_category_colour(
    category_id: int, body: ColourBody, session: Session = Depends(get_session)
) -> dict:
    """Choose a category's colour, or send null to go back to automatic."""
    category = _existing_category(session, category_id)
    category.colour = body.colour
    session.commit()
    return {"id": category.id, "name": category.name, "colour": category.colour}


@router.put("/{category_id}")
def rename_category(
    category_id: int, body: RenameBody, session: Session = Depends(get_session)
) -> dict:
    """Rename a category. Renaming onto an existing one merges them."""
    try:
        return manager_categories.rename_category(session, category_id, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    into: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    """Remove a category; its notes move to `into`, or survive as Uncategorised."""
    category = _existing_category(session, category_id)
    name = category.name
    moved_ids = _ids_in(session, category.id)
    if into is not None:
        target = _existing_category(session, into)
        if target.id == category.id:
            raise HTTPException(status_code=400, detail="A category cannot be moved into itself.")
        _same_space(category, target)
        try:
            manager_categories.rename_category(session, category.id, target.name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"deleted": True, "name": name, "into": target.name, "moved": len(moved_ids), "moved_ids": moved_ids}
    try:
        result = manager_categories.delete_category(session, category_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "name": name, "into": None, "moved_ids": moved_ids}
