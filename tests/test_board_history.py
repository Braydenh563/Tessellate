"""A board's time machine (the features audit W2; WHITEBOARD_PLAN decision 33).

A board edited three times replays to each state; a restore makes, removes
and writes back rows to match, each with its own event, links re-pointed at
remade items; the selection alone can be put back; moments group a sitting's
edits; a library placement replays per item. The browser half is
`scratchpad/ui-sweeps/wbhistory.js`.
"""

from __future__ import annotations

import json

from tessellate.core.database import AuditLog


def _board(client, name="History board", kind="board"):
    return client.post("/whiteboard/boards", json={"name": name, "type": kind}).json()


def _rect(x, y, w=100, h=60):
    return f"M {x} {y} L {x + w} {y} L {x + w} {y + h} L {x} {y + h} Z"


def _sketch(client, board_id, data, z=1):
    out = client.post("/whiteboard/sketches", json={"data": json.dumps(data), "board_id": board_id, "x": 0, "y": 0, "z": z})
    assert out.status_code in (200, 201), out.text
    return out.json()


def _text(client, board_id, words, x=0, y=0):
    out = client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": words}, "board_id": board_id, "x": x, "y": y, "width": 120, "height": 40})
    assert out.status_code in (200, 201), out.text
    return out.json()


def _last_event(client):
    rows = client.get("/audit?limit=1").json()
    return rows[0]["id"]


def _history(client, board_id, **params):
    out = client.get("/whiteboard/history", params={"board_id": board_id, **params})
    assert out.status_code == 200, out.text
    return out.json()


def _at(client, board_id, event_id):
    out = client.get(f"/whiteboard/history/{event_id}", params={"board_id": board_id})
    assert out.status_code == 200, out.text
    return out.json()


def _labels(state):
    return sorted(json.loads(s["data"]).get("label", "") for s in state["sketches"])


def test_a_board_edited_three_times_replays_to_each_state(client):
    board = _board(client)
    bid = board["id"]
    a = _sketch(client, bid, {"d": _rect(0, 0), "shape": "rect", "label": "one"})
    first = _last_event(client)
    b = _sketch(client, bid, {"d": _rect(200, 0), "shape": "rect", "label": "two"})
    second = _last_event(client)
    client.put(f"/whiteboard/sketches/{a['id']}", json={"data": json.dumps({"d": _rect(0, 0), "shape": "rect", "label": "one, renamed"}), "board_id": bid, "x": 0, "y": 0, "z": 1})
    third = _last_event(client)
    client.delete(f"/whiteboard/sketches/{b['id']}")
    fourth = _last_event(client)

    assert _labels(_at(client, bid, first)) == ["one"]
    assert _labels(_at(client, bid, second)) == ["one", "two"]
    assert _labels(_at(client, bid, third)) == ["one, renamed", "two"]
    assert _labels(_at(client, bid, fourth)) == ["one, renamed"]
    # Each item keeps its own id in the past, so a restore can match it.
    assert {s["id"] for s in _at(client, bid, second)["sketches"]} == {a["id"], b["id"]}


def test_moments_group_a_sitting_and_count_what_it_did(client):
    board = _board(client)
    bid = board["id"]
    a = _sketch(client, bid, {"d": _rect(0, 0), "label": "a"})
    _sketch(client, bid, {"d": _rect(0, 100), "label": "b"})
    client.delete(f"/whiteboard/sketches/{a['id']}")
    out = _history(client, bid)
    assert out["session_seconds"] == 120
    [moment] = out["moments"]
    assert (moment["added"], moment["changed"], moment["removed"], moment["count"]) == (2, 0, 1, 3)
    assert moment["kept"] is True and moment["actors"] == ["user"]
    assert moment["id"] > moment["first_id"]


def test_moments_split_after_two_minutes_and_page(client, app_state):
    from datetime import timedelta

    from tessellate.core.deps import get_db

    board = _board(client)
    bid = board["id"]
    _sketch(client, bid, {"d": _rect(0, 0), "label": "old"})
    _sketch(client, bid, {"d": _rect(0, 100), "label": "new"})
    session = get_db().session()
    try:
        rows = session.query(AuditLog).filter(AuditLog.entity_type == "whiteboard_sketch").order_by(AuditLog.id.desc()).limit(2).all()
        rows[1].created_at = rows[0].created_at - timedelta(minutes=10)
        session.commit()
    finally:
        session.close()
    out = _history(client, bid)
    assert [m["added"] for m in out["moments"]] == [1, 1]
    page = _history(client, bid, limit=1)
    assert len(page["moments"]) == 1 and page["more"] is True
    rest = _history(client, bid, before=page["moments"][0]["first_id"])
    assert len(rest["moments"]) == 1 and rest["more"] is False


def test_restore_makes_removes_and_writes_back_to_match(client):
    board = _board(client)
    bid = board["id"]
    a = _sketch(client, bid, {"d": _rect(0, 0), "shape": "rect", "label": "A"})
    b = _sketch(client, bid, {"d": _rect(300, 0), "shape": "rect", "label": "B"})
    _sketch(client, bid, {"type": "link-straight", "sourceId": a["id"], "sourceKind": "sketch", "targetId": b["id"], "targetKind": "sketch", "label": "go"})
    t = _text(client, bid, "keep me")
    moment = _last_event(client)
    # Then: B deleted (its link goes with it), A renamed, a new shape added,
    # the text box rewritten.
    client.delete(f"/whiteboard/sketches/{b['id']}")
    client.put(f"/whiteboard/sketches/{a['id']}", json={"data": json.dumps({"d": _rect(0, 0), "shape": "rect", "label": "A2"}), "board_id": bid, "x": 0, "y": 0, "z": 1})
    _sketch(client, bid, {"d": _rect(0, 300), "shape": "rect", "label": "later"})
    client.put(f"/whiteboard/objects/{t['id']}", json={"kind": "text", "data": {"content": "rewritten"}, "board_id": bid, "x": 5, "y": 5, "width": 120, "height": 40})

    out = client.post(f"/whiteboard/history/{moment}/restore", params={"board_id": bid}, json={})
    assert out.status_code == 200, out.text
    counts = out.json()
    # SQLite gives a deleted row's id to the next one made (no AUTOINCREMENT),
    # so "later" may hold B's old id and be written back as B in place rather
    # than removed and B made again; either way the board ends the same.
    assert counts["made"] + counts["changed"] + counts["removed"] >= 4, counts

    now = client.get("/whiteboard/", params={"board_id": bid}).json()
    shapes = {json.loads(s["data"]).get("label"): s for s in now["sketches"]}
    assert set(shapes) == {"A", "B", "go"}
    assert shapes["A"]["id"] == a["id"]  # written back in place
    rejoined = json.loads(shapes["go"]["data"])
    assert rejoined["sourceId"] == a["id"] and rejoined["targetId"] == shapes["B"]["id"]
    [text] = now["objects"]
    assert text["data"]["content"] == "keep me" and text["x"] == 0
    # The restore is in the history too, each row with its own event.
    assert _labels(_at(client, bid, _last_event(client))) == ["A", "B", "go"]


def test_restore_only_the_selection(client):
    board = _board(client)
    bid = board["id"]
    a = _sketch(client, bid, {"d": _rect(0, 0), "label": "A"})
    b = _sketch(client, bid, {"d": _rect(200, 0), "label": "B"})
    moment = _last_event(client)
    for item, word in ((a, "A2"), (b, "B2")):
        client.put(f"/whiteboard/sketches/{item['id']}", json={"data": json.dumps({"d": _rect(0, 0), "label": word}), "board_id": bid, "x": 0, "y": 0, "z": 1})
    out = client.post(f"/whiteboard/history/{moment}/restore", params={"board_id": bid}, json={"keys": [f"sketch:{a['id']}"]})
    assert out.json()["changed"] == 1
    now = client.get("/whiteboard/", params={"board_id": bid}).json()
    assert sorted(json.loads(s["data"])["label"] for s in now["sketches"]) == ["A", "B2"]


def test_a_map_topic_made_again_keeps_its_parent(client):
    board = _board(client, kind="map")
    bid = board["id"]
    root = client.post(f"/whiteboard/boards/{bid}/nodes", json={"kind": "topic", "text": "Root"}).json()
    child = client.post(f"/whiteboard/boards/{bid}/nodes", json={"kind": "topic", "text": "Child", "parent_id": root["id"]}).json()
    moment = _last_event(client)
    client.delete(f"/whiteboard/objects/{child['id']}")
    client.delete(f"/whiteboard/objects/{root['id']}")
    out = client.post(f"/whiteboard/history/{moment}/restore", params={"board_id": bid}, json={})
    assert out.json()["made"] == 2
    objs = {o["data"]["content"]: o for o in client.get("/whiteboard/", params={"board_id": bid}).json()["objects"]}
    assert objs["Child"]["parent_id"] == objs["Root"]["id"]


def test_an_item_with_no_log_counts_as_there_from_the_start(client):
    """A duplicated board's copies have no events of their own."""
    board = _board(client)
    _text(client, board["id"], "original")
    copy = client.post(f"/whiteboard/boards/{board['id']}/duplicate").json()
    _text(client, copy["id"], "added later", y=200)
    moment = _history(client, copy["id"])["moments"][-1]["first_id"]
    state = _at(client, copy["id"], moment)
    assert sorted(o["data"]["content"] for o in state["objects"]) == ["added later", "original"]
    # Before the one logged event, only the copy was there.
    assert [o["data"]["content"] for o in _at(client, copy["id"], moment - 1)["objects"]] == ["original"]


def test_a_compacted_moment_is_listed_but_not_shown(client):
    board = _board(client)
    bid = board["id"]
    a = _sketch(client, bid, {"d": _rect(0, 0), "label": "x"})
    first = _last_event(client)
    client.put(f"/whiteboard/sketches/{a['id']}", json={"data": json.dumps({"d": _rect(0, 0), "label": "y"}), "board_id": bid, "x": 0, "y": 0, "z": 1})
    from tessellate.core.deps import get_db

    session = get_db().session()
    try:
        row = session.get(AuditLog, first)
        row.payload = {"compacted": True}
        latest = session.query(AuditLog).filter(AuditLog.entity_type == "whiteboard_sketch").order_by(AuditLog.id.desc()).first()
        latest.payload = {"compacted": True, "snapshot": 2, "after": dict(latest.payload["after"])}
        session.commit()
    finally:
        session.close()
    assert client.get(f"/whiteboard/history/{first}", params={"board_id": bid}).status_code == 410
    assert any(m["kept"] is False for m in _history(client, bid)["moments"])
    assert client.post(f"/whiteboard/history/{first}/restore", params={"board_id": bid}, json={}).status_code == 410


def test_the_scratch_board_has_a_history_too(client):
    a = _sketch(client, None, {"d": _rect(0, 0), "label": "scratch"})
    moment = _last_event(client)
    client.delete(f"/whiteboard/sketches/{a['id']}")
    assert "scratch" in _labels(_at(client, 0, moment))
    assert _history(client, 0)["moments"]


def test_history_is_the_presenting_mode_with_its_own_bar() -> None:
    """DESIGN.md's recipe row: the bar is the present bar's shape, the mode
    hides the chrome and takes the pointer off both layers, the keys are
    taken in the capture phase, writes are refused, and the Board menu's row
    names the command."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (root / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8")
    js = (root / "frontend" / "js" / "whiteboard-history.js").read_text(encoding="utf-8")
    bar = re.search(r'<div id="wb-history-bar"[^>]*>', html).group(0)
    assert "whiteboard-floating-panel" in bar and "wb-present-bar" in bar and 'role="toolbar"' in bar
    assert 'data-wb-cmd="history"' in html and 'type="range" id="wb-history-slider"' in html
    assert ".wb-presenting .whiteboard-floating-panel:not(.wb-present-bar)" in css
    assert re.search(r"\.wb-presenting #wb-svg-layer \{\s*pointer-events: none;", css)
    assert 'classList.add("wb-presenting")' in js
    assert '}, true);' in js and "stopImmediatePropagation" in js
    assert "function wbHistGuard(on)" in js and "/^\\/whiteboard\\//" in js
    #: Registered in the `boards` bundle (lazy-entries.js) since D22, 2026-11-11; it was `library`'s in app.js.
    assert '"/js/whiteboard-history.js"' in (root / "frontend" / "js" / "lazy-entries.js").read_text(encoding="utf-8")


def test_a_reused_id_brings_no_other_boards_history(client):
    """SQLite gives a deleted row's id to the next row made, so one id's log
    can hold an item from another board first (measured in a sweep: a new
    board's first moment counted "4 added, 2 removed" for 2 shapes)."""
    other = _board(client, "Elsewhere")["id"]
    gone = _sketch(client, other, {"d": _rect(0, 0), "label": "old"})
    client.delete(f"/whiteboard/sketches/{gone['id']}")
    bid = _board(client)["id"]
    fresh = _sketch(client, bid, {"d": _rect(0, 0), "label": "new"})
    [moment] = _history(client, bid)["moments"]
    assert (moment["added"], moment["removed"], moment["count"]) == (1, 0, 1)
    assert _labels(_at(client, bid, moment["id"])) == ["new"]
    assert fresh["id"] > 0


# --- Named snapshots (Brief 77, WHITEBOARD_PLAN "Deepened 2026-10-10" row 4) --


def test_a_snapshot_names_the_board_as_it_is_and_restores_to_it(client):
    board = _board(client, "Snapshot board")
    one = _text(client, board["id"], "One")
    made = client.post("/whiteboard/history/snapshots", json={"board_id": board["id"], "name": "Before the move"})
    assert made.status_code == 201, made.text
    snap = made.json()
    assert snap["name"] == "Before the move" and snap["event_id"] > 0
    _text(client, board["id"], "Two")
    listed = client.get("/whiteboard/history/snapshots", params={"board_id": board["id"]}).json()["snapshots"]
    assert [s["name"] for s in listed] == ["Before the move"]
    shown = _at(client, board["id"], snap["event_id"])
    assert [o["data"]["content"] for o in shown["objects"]] == ["One"]
    restored = client.post(f"/whiteboard/history/{snap['event_id']}/restore", params={"board_id": board["id"]}, json={})
    assert restored.status_code == 200, restored.text
    now = client.get("/whiteboard/", params={"board_id": board["id"]}).json()
    assert [o["id"] for o in now["objects"]] == [one["id"]]


def test_a_snapshot_with_no_name_is_called_snapshot_and_can_be_deleted(client):
    board = _board(client, "Unnamed snapshot")
    _text(client, board["id"], "Only")
    snap = client.post("/whiteboard/history/snapshots", json={"board_id": board["id"]}).json()
    assert snap["name"].startswith("Snapshot ")
    gone = client.delete(f"/whiteboard/history/snapshots/{snap['id']}", params={"board_id": board["id"]})
    assert gone.status_code == 204
    assert client.get("/whiteboard/history/snapshots", params={"board_id": board["id"]}).json()["snapshots"] == []


def test_an_empty_board_has_nothing_to_snapshot(client):
    board = _board(client, "Empty snapshot")
    out = client.post("/whiteboard/history/snapshots", json={"board_id": board["id"]})
    assert out.status_code == 409


def test_a_change_from_elsewhere_drops_only_the_steps_on_the_same_items():
    """L274: Undo must not clobber the agent's or another tab's work (decision 17); steps on other items stay."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard-history.js").read_text()
    assert "function wbEntryKeys(" in js and "function wbDropStaleSteps(" in js
    take = js[js.index("async function wbTakeChangeFromElsewhere") :]
    assert "const rowsBefore = wbBoardRows();" in take
    assert "wbDropStaleSteps(rowsBefore, wbBoardRows(), entry)" in take
    assert "left the history" in take
    drop = js[js.index("function wbDropStaleSteps(") : js.index("async function wbTakeChangeFromElsewhere")]
    assert "if (stack[i] === keep) continue;" in drop  # the external step itself stays
    assert "![...keys].some((key) => touched.has(key))" in drop  # only a step on a touched item goes
