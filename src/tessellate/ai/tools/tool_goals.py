"""`list_goals` and `edit_goals`: the goals and lists surface for the agent (Brief 98). Both go through
`repo/goals.py`, as the Goals tab does, so a tick said in Chat and a tick pressed there are one write; each
edit carries the Undo that puts the earlier state back."""

from __future__ import annotations

from sqlalchemy.orm import Session

from tessellate.ai.tools._common import ToolError, ToolSpec
from tessellate.repo import goals
from tessellate.repo.goals import Invalid

ACTIONS = ("make_goal", "make_list", "add", "tick", "untick", "remove", "finish", "reopen", "delete")


def _list_goals(session: Session, args: dict) -> dict:
    page = goals.page(session, None, "open")
    return {
        "goals": [
            {"id": g["id"], "title": g["title"], "kind": g["kind"], "target": g["target_date"], "progress": f"{g['progress']['done']}/{g['progress']['total']}",
             "items": [("x " if i["done"] else "- ") + i["text"] for i in g["items"]]}
            for g in page["goals"]
        ],
        "counts": page["counts"],
    }


def _undo(**arguments) -> dict:  # noqa: ANN003
    return {"tool": "edit_goals", "arguments": arguments}


def _item_by_words(session: Session, goal, ref) -> object:  # noqa: ANN001
    text = str(ref or "").strip().lower()
    if not text:
        raise ToolError("item is the words of the line")
    items = goals.items_of(session, goal.id)
    hits = [i for i in items if text == i.text.lower()] or [i for i in items if text in i.text.lower()]
    if len(hits) != 1:
        raise ToolError(f"No line of “{goal.title[:40]}” matches “{text}”" if not hits else f"{len(hits)} lines match “{text}”: " + "; ".join(i.text[:40] for i in hits[:5]))
    return hits[0]


def _create(session: Session, action: str, args: dict) -> dict:
    """`goal` is the new title; a goal may say its target day, a list's lines come as `items`."""
    kind = action.removeprefix("make_")
    made = goals.create(session, str(args.get("goal") or ""), kind, str(args.get("target_date") or ""), [{"text": t} for t in args.get("items") or []])
    session.commit()
    return {"id": made.id, "label": f"ph:target Made the {kind} “{made.title[:50]}”", "undo": _undo(action="delete", goal=str(made.id))}


def _item_change(session: Session, goal, action: str, args: dict) -> dict:
    if action == "add":
        text = str(args.get("item") or "").strip()
        added = goals.add_item(session, goal, text)
        session.commit()
        return {"id": goal.id, "label": f"ph:plus Added “{added.text[:50]}” to “{goal.title[:50]}”", "undo": _undo(action="remove", goal=str(goal.id), item=added.text)}
    item = _item_by_words(session, goal, args.get("item"))
    if action == "remove":
        goals.delete_item(session, goal.id, item.id)
        session.commit()
        return {"id": goal.id, "label": f"ph:minus Took “{item.text[:50]}” off “{goal.title[:50]}”", "undo": _undo(action="add", goal=str(goal.id), item=item.text)}
    ticked = action == "tick"
    goals.update_item(session, goal.id, item.id, done=ticked)
    session.commit()
    verb = "Ticked off" if ticked else "Unticked"
    return {"id": goal.id, "item": item.id, "done": ticked, "label": f"ph:check-square {verb} “{item.text[:50]}” on “{goal.title[:50]}”", "undo": _undo(action="untick" if ticked else "tick", goal=str(goal.id), item=item.text)}


def _edit_goals(session: Session, args: dict) -> dict:
    action = str(args.get("action") or "").strip().lower()
    if action not in ACTIONS:
        raise ToolError("action is one of: " + ", ".join(ACTIONS))
    try:
        if action.startswith("make_"):
            return _create(session, action, args)
        goal = goals.find_by_words(session, args.get("goal"))
        if action in ("finish", "reopen"):
            goals.update(session, goal.id, done=action == "finish")
            session.commit()
            return {"id": goal.id, "done": action == "finish", "label": f"ph:flag-checkered {'Finished' if action == 'finish' else 'Reopened'} “{goal.title[:50]}”", "undo": _undo(action="reopen" if action == "finish" else "finish", goal=str(goal.id))}
        if action == "delete":
            gone = goals.delete(session, goal.id)
            session.commit()
            return {"id": goal.id, "deleted": True, "label": f"ph:trash Deleted the {gone['kind']} “{gone['title'][:50]}”", "undo": _undo(action="make_" + gone["kind"], goal=gone["title"], target_date=gone["target_date"], items=[i["text"] for i in gone["items"]])}
        return _item_change(session, goal, action, args)
    except Invalid as exc:
        raise ToolError(str(exc.detail)) from exc


LIST_GOALS = ToolSpec(
    "list_goals",
    "Goals and lists with progress.",
    {"type": "object", "properties": {}},
    _list_goals,
)

EDIT_GOALS = ToolSpec(
    "edit_goals",
    "Make or change a goal or list and its items.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ACTIONS)},
            "goal": {"type": "string"},
            "item": {"type": "string"},
            "items": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action", "goal"],
    },
    _edit_goals,
)
