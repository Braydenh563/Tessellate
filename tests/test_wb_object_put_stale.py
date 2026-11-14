"""Source text: the route is exercised through the test client; the front-end half has no browser under pytest, so its script is read as text.

A late PUT for an item that was just deleted answers 404, never a 500 StaleDataError.

Undo of a just-added map topic deletes the row while a debounced PUT for it is still on its way. The
request reads the row, the delete lands, and the UPDATE at commit then matches nothing: SQLAlchemy raised
StaleDataError out of the commit. The server now rolls back and answers the same 404 an unknown id gets.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete

from tessellate.core.database import WhiteboardObject

ROOT = Path(__file__).resolve().parents[1]


def _make(client):
    board = client.post("/whiteboard/boards", json={"name": "Stale board", "type": "board"}).json()
    body = {"kind": "text", "data": {"content": "x"}, "board_id": board["id"], "x": 0, "y": 0, "width": 100, "height": 40}
    made = client.post("/whiteboard/objects", json=body)
    assert made.status_code in (200, 201), made.text
    return made.json(), body


def _lose_the_row(db, object_id):
    # The row goes without the session being told, as another request's delete would leave it.
    db.execute(delete(WhiteboardObject).where(WhiteboardObject.id == object_id).execution_options(synchronize_session=False))


def test_a_put_for_an_item_deleted_before_its_update_is_a_404(ai_client, monkeypatch):
    from tessellate.api import wb_items

    made, body = _make(ai_client)
    real = wb_items._save_object

    def lose_then_save(db, obj, payload):
        _lose_the_row(db, obj.id)
        real(db, obj, payload)

    monkeypatch.setattr(wb_items, "_save_object", lose_then_save)
    out = ai_client.put(f"/whiteboard/objects/{made['id']}", json={**body, "x": 40})
    assert out.status_code == 404, out.text
    assert "could not be found" in out.json()["detail"]


def test_a_put_for_an_item_deleted_after_its_update_is_a_404(ai_client, monkeypatch):
    from tessellate.api import wb_items

    made, body = _make(ai_client)
    real = wb_items._save_object

    def save_then_lose(db, obj, payload):
        real(db, obj, payload)
        _lose_the_row(db, obj.id)

    monkeypatch.setattr(wb_items, "_save_object", save_then_lose)
    out = ai_client.put(f"/whiteboard/objects/{made['id']}", json={**body, "x": 40})
    assert out.status_code == 404, out.text


def test_the_client_drops_a_put_for_an_object_it_is_undoing():
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    save = js[js.index("async function wbSaveObject(d)") :][:700]
    assert "if (d._undoing) return;" in save
    undo = js[js.index("This entry means \"remove what was created\"") :][:2400]
    assert undo.index("item._undoing = true;") < undo.index('method: "DELETE"')
    assert "delete item._undoing;" in undo
