"""A skill run's own Undo (AGENT_SKILLS_REFORM, "Placed from INBOX, 2026-10-05").

`POST /events/undo` and the Recent activity widget's "Undo what Atlas did" were
built for one actor. A skill run is several: each tool call files its writes
under `ai:<tool>@<model>`. So the run's result carries `undo_span` (its AI
actors and the event ids its writes fall between, `skill_runner._undo_span`),
the route takes `actors` and `until`, and Chat's "What changed" head offers
"Undo the run" (note-history.js `undoSkillRun`, the widget's dry-run-then-
confirm grammar). What must hold:

- the actors are one for "changed since": a run's second tool touching a
  note its first tool wrote is the run's own change, not somebody else's;
- nothing before the span or after it is undone, even by the same tool;
- the person is never an actor to undo, in a list or alone;
- a run that wrote nothing carries no span.
"""

from __future__ import annotations

from sqlalchemy import select

from tessellate.ai import skill_runner
from tessellate.core import events
from tessellate.core.database import AuditLog, Entry
from tessellate.entry import manager
from tests._app_js import app_js_text

TAG = "ai:tag_note@qwen"
FILE = "ai:move_note@qwen"


def _last(session) -> int:
    return session.scalar(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)) or 0


def _as(session, actor, entry, **changes):
    with events.acting_as(actor):
        manager.update_entry(session, entry, **changes)
    session.commit()


def _note(session, text="Seed the tomatoes indoors") -> Entry:
    entry = manager.create_entry(session, text, category_name="Garden", tags=["garden"])
    session.commit()
    return entry


def test_a_run_is_its_actors_over_its_span(session):
    first, second, outside = _note(session), _note(session, "Prune the apple tree"), _note(session, "Order seeds")
    _as(session, TAG, outside, tags=["before-the-run"])
    mark = skill_runner._event_mark(session)
    assert mark == _last(session)
    # The run: one tool tags, a second refiles the same note and another.
    _as(session, TAG, first, tags=["seedlings"])
    _as(session, FILE, first, category_name="Indoors")
    _as(session, FILE, second, category_name="Orchard")
    span = skill_runner._undo_span(session, mark)
    assert span["since"] == mark and span["actors"] == sorted([FILE, TAG])
    until = span["until"]
    # After the run, the same tool again: outside the span.
    _as(session, TAG, outside, tags=["after-the-run"])

    plan = events.undo(session, span["actors"], mark, until_id=until)
    statuses = {item["entity_id"]: item["status"] for item in plan["items"]}
    # The second tool's change to the first note is the run's own, so the
    # note goes back rather than reading "changed since".
    assert statuses == {first.id: "undo", second.id: "undo"}

    events.undo(session, span["actors"], mark, until_id=until, apply=True)
    session.commit()
    for entry in (first, second, outside):
        session.refresh(entry)
    assert manager.category_name_for(session, first) == "Garden"
    assert manager.category_name_for(session, second) == "Garden"
    assert "seedlings" not in first.tags
    assert "after-the-run" in outside.tags  # outside the span, kept


def test_a_run_that_wrote_nothing_has_no_span(session):
    _note(session)
    mark = skill_runner._event_mark(session)
    assert skill_runner._undo_span(session, mark) is None


def test_the_route_takes_a_list_and_a_bound(client, session):
    entry = _note(session)
    mark = _last(session)
    _as(session, TAG, entry, tags=["seedlings"])
    until = _last(session)
    _as(session, FILE, entry, category_name="Indoors")
    body = {"actors": [TAG], "since": mark, "until": until}
    plan = client.post("/events/undo", json=body).json()
    # Within the bound the tag is the run's; the later refile is someone
    # else's (not in the list), so the person is told rather than overruled.
    assert [item["status"] for item in plan["items"]] == ["changed since"]
    both = client.post("/events/undo", json={**body, "actors": [TAG, FILE], "until": 0}).json()
    assert [item["status"] for item in both["items"]] == ["undo"]


def test_the_person_is_never_an_actor_in_a_list(client):
    response = client.post("/events/undo", json={"actors": [TAG, "user"]})
    assert response.status_code == 400
    response = client.post("/events/undo", json={})
    assert response.status_code == 422


def test_chat_offers_the_runs_undo_and_keeps_it_on_reopen():
    js = app_js_text()
    assert 'smallButton("ph:arrow-counter-clockwise Undo the run"' in js
    assert "box.dataset.undoSpan = JSON.stringify(span)" in js
    assert 'undo_span: JSON.parse(node.dataset.undoSpan || "null")' in js
    assert '"openEntryHistory", "undoSkillRun"' in js
    from pathlib import Path

    lazy = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "note-history.js").read_text(encoding="utf-8")
    assert "async function undoSkillRun(span, button, onDone)" in lazy
    assert "activityUndoPlanText(plan, byId, \"this run\")" in lazy
    assert "dry_run: false" in lazy
