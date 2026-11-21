"""Goals and lists (Brief 98): titled sets of items that are ticked off, with their progress.

Plain verbs over `Goal` and `GoalItem`, as `repo/bookmarks.py`: flush, never commit (the route owns the
transaction), `NotFound` and `Invalid` for what cannot be. The listing, the routes and the agent tool
(`ai/tools/tool_goals.py`) all read and write through here, so a tick means the same everywhere.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate.core.database import Goal, GoalItem, utcnow
from tessellate.repo import Invalid, NotFound

KINDS = ("goal", "list")
MISSING = "That goal or list could not be found."
MISSING_ITEM = "That item could not be found."
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: One goal or list holds at most this many items, and the notebook this many goals, so a page stays one light request.
MAX_ITEMS = 200
MAX_GOALS = 500


def _title(value: str) -> str:
    title = " ".join(str(value or "").split())[:200]
    if not title:
        raise Invalid("Give it a title.")
    return title


def _kind(value: str) -> str:
    kind = str(value or "goal").strip().lower()
    if kind not in KINDS:
        raise Invalid("A goal or a list.")
    return kind


def _valid_date(text: str) -> bool:
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _target(value: str) -> str:
    text = str(value or "").strip()
    if text and not (_DATE.match(text) and _valid_date(text)):
        raise Invalid("Give the target date as year-month-day.")
    return text


def _text(value: str) -> str:
    text = " ".join(str(value or "").split())[:300]
    if not text:
        raise Invalid("Say what the item is.")
    return text


def find(session: Session, goal_id: int) -> Goal | None:
    return session.get(Goal, goal_id)


def get(session: Session, goal_id: int) -> Goal:
    goal = find(session, goal_id)
    if goal is None:
        raise NotFound(MISSING)
    return goal


def items_of(session: Session, goal_id: int) -> list[GoalItem]:
    return list(session.scalars(select(GoalItem).where(GoalItem.goal_id == goal_id).order_by(GoalItem.id)))


def get_item(session: Session, goal_id: int, item_id: int) -> GoalItem:
    item = session.get(GoalItem, item_id)
    if item is None or item.goal_id != goal_id:
        raise NotFound(MISSING_ITEM)
    return item


def progress(items: list[GoalItem]) -> dict:
    """`{total, done, percent}`: a goal with no items is 0 percent, not undefined."""
    total = len(items)
    done = sum(1 for item in items if item.done_at is not None)
    return {"total": total, "done": done, "percent": round(100 * done / total) if total else 0}


def shape(goal: Goal, items: list[GoalItem]) -> dict:
    return {
        "id": goal.id,
        "title": goal.title,
        "kind": goal.kind,
        "target_date": goal.target_date,
        "done_at": goal.done_at.isoformat() if goal.done_at else None,
        "created_at": goal.created_at.isoformat(),
        "items": [{"id": i.id, "text": i.text, "done": i.done_at is not None} for i in items],
        "progress": progress(items),
    }


def page(session: Session, kind: str | None = None, state: str = "open", limit: int = MAX_GOALS) -> dict:
    """`{goals, counts}`: every goal or list of a `kind` (both when None), `open`, `done` (achieved) or
    `all`, newest first, each with its items and progress. `counts` is per kind over the open ones."""
    query = select(Goal).order_by(Goal.id.desc()).limit(min(limit, MAX_GOALS))
    if kind:
        query = query.where(Goal.kind == _kind(kind))
    if state == "open":
        query = query.where(Goal.done_at.is_(None))
    elif state == "done":
        query = query.where(Goal.done_at.is_not(None))
    rows = list(session.scalars(query))
    by_goal: dict[int, list[GoalItem]] = {row.id: [] for row in rows}
    if rows:
        for item in session.scalars(select(GoalItem).where(GoalItem.goal_id.in_(by_goal)).order_by(GoalItem.id)):
            by_goal[item.goal_id].append(item)
    counts = dict.fromkeys(KINDS, 0)
    for k, n in session.execute(select(Goal.kind, func.count(Goal.id)).where(Goal.done_at.is_(None)).group_by(Goal.kind)):
        counts[k] = n
    return {"goals": [shape(row, by_goal[row.id]) for row in rows], "counts": counts}


def create(session: Session, title: str, kind: str = "goal", target_date: str = "", items: list[dict] | None = None) -> Goal:
    """A goal or list with its items. `items` is `[{text, done}]`, so an Undo of a delete puts it back as it was."""
    if (session.scalar(select(func.count(Goal.id))) or 0) >= MAX_GOALS:
        raise Invalid("There are too many goals and lists; delete some first.")
    goal = Goal(title=_title(title), kind=_kind(kind), target_date=_target(target_date))
    session.add(goal)
    session.flush()
    for row in (items or [])[:MAX_ITEMS]:
        add_item(session, goal, row.get("text", ""), bool(row.get("done")))
    return goal


def update(session: Session, goal_id: int, title: str | None = None, kind: str | None = None, target_date: str | None = None, done: bool | None = None) -> Goal:
    goal = get(session, goal_id)
    if title is not None:
        goal.title = _title(title)
    if kind is not None:
        goal.kind = _kind(kind)
    if target_date is not None:
        goal.target_date = _target(target_date)
    if done is not None:
        goal.done_at = (goal.done_at or utcnow()) if done else None
    session.flush()
    return goal


def delete(session: Session, goal_id: int) -> dict:
    """Delete it and its items; the answer is the whole thing as it was, so Undo can create it again."""
    goal = get(session, goal_id)
    items = items_of(session, goal_id)
    before = shape(goal, items)
    session.execute(sa_delete(GoalItem).where(GoalItem.goal_id == goal_id))
    session.delete(goal)
    session.flush()
    return before


def add_item(session: Session, goal: Goal, text: str, done: bool = False) -> GoalItem:
    if (session.scalar(select(func.count(GoalItem.id)).where(GoalItem.goal_id == goal.id)) or 0) >= MAX_ITEMS:
        raise Invalid(f"A goal or list holds at most {MAX_ITEMS} items.")
    item = GoalItem(goal_id=goal.id, text=_text(text), done_at=utcnow() if done else None)
    session.add(item)
    session.flush()
    return item


def update_item(session: Session, goal_id: int, item_id: int, text: str | None = None, done: bool | None = None) -> GoalItem:
    item = get_item(session, goal_id, item_id)
    if text is not None:
        item.text = _text(text)
    if done is not None:
        item.done_at = (item.done_at or utcnow()) if done else None
    session.flush()
    return item


def delete_item(session: Session, goal_id: int, item_id: int) -> dict:
    item = get_item(session, goal_id, item_id)
    gone = {"id": item.id, "text": item.text, "done": item.done_at is not None}
    session.delete(item)
    session.flush()
    return gone


def find_by_words(session: Session, ref) -> Goal:  # noqa: ANN001
    """A goal or list by id, or by the words of its title (the one it names, never a guess between two)."""
    text = str(ref or "").strip()
    if not text:
        raise Invalid("Say which goal or list: its id, or words from its title.")
    if text.isdigit() and (row := find(session, int(text))) is not None:
        return row
    rows = [g for g in session.scalars(select(Goal).order_by(Goal.id.desc())) if text.lower() in g.title.lower()]
    rows = [g for g in rows if g.title.lower() == text.lower()] or rows
    if len(rows) != 1:
        raise Invalid(f"No goal or list matches “{text}”." if not rows else f"{len(rows)} match “{text}”: " + "; ".join(f"{g.id} {g.title[:40]}" for g in rows[:5]))
    return rows[0]
