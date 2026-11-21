"""Goals and lists (Brief 98): `GET /goals`, create, change, delete, and their items. The shape is
`repo/goals.py`'s; nothing here needs the AI. The Goals sub-tab of Notes (`goals-view.js`) and the
`edit_goals` agent tool read and write the same rows."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tessellate.core.deps import get_session
from tessellate.repo import goals

router = APIRouter(prefix="/goals", tags=["goals"])


class ItemIn(BaseModel):
    text: str = Field(max_length=300)
    done: bool = False


class GoalCreate(BaseModel):
    title: str = Field(max_length=200)
    kind: Literal["goal", "list"] = "goal"
    target_date: str = Field(default="", max_length=10)
    items: list[ItemIn] = Field(default_factory=list, max_length=goals.MAX_ITEMS)


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    kind: Literal["goal", "list"] | None = None
    target_date: str | None = Field(default=None, max_length=10)
    done: bool | None = None


class ItemUpdate(BaseModel):
    text: str | None = Field(default=None, max_length=300)
    done: bool | None = None


def _out(session: Session, goal) -> dict:
    return goals.shape(goal, goals.items_of(session, goal.id))


@router.get("")
def list_goals(
    kind: Literal["goal", "list"] | None = None,
    state: Literal["open", "done", "all"] = Query(default="open"),
    session: Session = Depends(get_session),
) -> dict:
    """`{goals, counts}`: each with its items and `progress` (`total`, `done`, `percent`)."""
    return goals.page(session, kind, state)


@router.post("", status_code=201)
def create_goal(body: GoalCreate, session: Session = Depends(get_session)) -> dict:
    goal = goals.create(session, body.title, body.kind, body.target_date, [i.model_dump() for i in body.items])
    session.commit()
    return _out(session, goal)


@router.patch("/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdate, session: Session = Depends(get_session)) -> dict:
    goal = goals.update(session, goal_id, **body.model_dump())
    session.commit()
    return _out(session, goal)


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, session: Session = Depends(get_session)) -> dict:
    """The goal as it was, so the app's Undo can create it again."""
    gone = goals.delete(session, goal_id)
    session.commit()
    return gone


@router.post("/{goal_id}/items", status_code=201)
def add_item(goal_id: int, body: ItemIn, session: Session = Depends(get_session)) -> dict:
    goal = goals.get(session, goal_id)
    goals.add_item(session, goal, body.text, body.done)
    session.commit()
    return _out(session, goal)


@router.patch("/{goal_id}/items/{item_id}")
def update_item(goal_id: int, item_id: int, body: ItemUpdate, session: Session = Depends(get_session)) -> dict:
    goals.update_item(session, goal_id, item_id, **body.model_dump())
    session.commit()
    return _out(session, goals.get(session, goal_id))


@router.delete("/{goal_id}/items/{item_id}")
def delete_item(goal_id: int, item_id: int, session: Session = Depends(get_session)) -> dict:
    gone = goals.delete_item(session, goal_id, item_id)
    session.commit()
    return gone
