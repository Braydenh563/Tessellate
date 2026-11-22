"""The Recent activity widget's Undo row goes once the actor's changes are undone.

The row stayed after an undo (a second press said "Already undone"). The feed
now names, on a `restored` event, the events it reversed (`undid`), and the
widget's `activityUndoStarts` leaves an actor out once everything it did in
the list is named there.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tessellate.core import events
from tessellate.core.database import AuditLog
from tessellate.entry import manager
from tests._app_js import JS_DIR

AI = "system:librarian"


def _starts(items: list[dict]) -> dict:
    source = (JS_DIR / "dashboard.js").read_text(encoding="utf-8")
    match = re.search(r"^function activityUndoStarts\(items\) \{.*?^\}", source, re.S | re.M)
    assert match, "activityUndoStarts is gone from the dashboard script"
    script = (
        match.group(0)
        + f"\nprocess.stdout.write(JSON.stringify([...activityUndoStarts({json.dumps(items)})]));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return dict(json.loads(out))


def _item(id_, actor, action="updated", **extra):
    return {"id": id_, "actor": actor, "action": action, "entity_type": "entry", "entity_id": 1, **extra}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_actor_with_changes_left_gets_a_row():
    assert _starts([_item(3, AI), _item(4, AI)]) == {AI: 3}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_actor_whose_changes_were_all_undone_gets_no_row():
    items = [_item(3, AI), _item(4, AI), _item(5, "user", "restored", undid=[3, 4])]
    assert _starts(items) == {}


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_change_made_after_the_undo_brings_the_row_back():
    items = [_item(3, AI), _item(5, "user", "restored", undid=[3]), _item(6, AI)]
    assert _starts(items) == {AI: 6}


def test_the_feed_names_the_events_a_restore_reversed(client, session):
    entry = manager.create_entry(session, "The pond needs a pump", tags=["garden"])
    mark = session.query(AuditLog).order_by(AuditLog.id.desc()).first().id
    with events.acting_as(AI):
        manager.update_entry(session, entry, content="The pond has a pump")
    session.commit()
    applied = client.post(
        "/events/undo", json={"actor": AI, "since": mark, "dry_run": False}
    ).json()
    assert applied["undone"] == 1
    feed = client.get(f"/events?since={mark}").json()["items"]
    restored = [item for item in feed if item["action"] == "restored"]
    assert len(restored) == 1
    changed = [item["id"] for item in feed if item["actor"] == AI]
    assert restored[0]["undid"] == changed
    assert all("undid" not in item for item in feed if item["action"] != "restored")


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_redo_brings_the_row_back_l805():
    items = [
        _item(3, AI),
        _item(5, "user", "restored", undid=[3]),
        _item(6, "user", "redone", redid=[5]),
    ]
    assert _starts(items) == {AI: 3}


def test_both_ai_undos_join_the_stack_with_a_redo_l805():
    for name, marker in (("dashboard.js", "Undid what ${name} changed"), ("note-history.js", "Undid this run")):
        source = (JS_DIR / name).read_text(encoding="utf-8")
        assert marker in source and '"/events/redo"' in source, name
