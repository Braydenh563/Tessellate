"""An XMind file comes in as a mind map (the features audit W5).

`.xmind` is a zip whose map is `content.json`; the client sends it base64.
The first sheet's central topic is the map's root and names it (FEAT-01:
a map's centre is never dropped on the way in), and a topic's plain notes
come in as its note. XMind 8's `content.xml`
is refused with how to get the newer file, and a zip that unpacks too large
is refused before it is read.
"""

from __future__ import annotations

import base64
import io
import json
import zipfile


def _xmind(files: dict[str, bytes]) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _sheet(root: dict) -> bytes:
    return json.dumps([{"id": "s1", "title": "Sheet 1", "rootTopic": root}]).encode("utf-8")


def test_an_xmind_map_imports(ai_client):
    root = {
        "id": "r", "title": "Trip",
        "children": {"attached": [
            {"id": "a", "title": "Packing", "notes": {"plain": {"content": "Do not forget the tent"}},
             "children": {"attached": [{"id": "a1", "title": "Tent"}]}},
            {"id": "b", "title": "Route"},
        ]},
    }
    out = ai_client.post("/whiteboard/boards/import", json={"format": "xmind", "content": _xmind({"content.json": _sheet(root)})})
    assert out.status_code == 201, out.text
    board = out.json()
    assert board["title"] == "Trip" and board["object_count"] == 4
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    by_text = {o["data"].get("content"): o for o in state["objects"]}
    assert set(by_text) == {"Trip", "Packing", "Tent", "Route"}
    assert by_text["Trip"]["parent_id"] is None
    assert by_text["Packing"]["parent_id"] == by_text["Trip"]["id"]
    assert by_text["Tent"]["parent_id"] == by_text["Packing"]["id"]
    assert by_text["Packing"]["data"].get("note") == "Do not forget the tent"


def test_xmind_8_and_not_a_zip_are_refused_with_a_reason(ai_client):
    old = ai_client.post("/whiteboard/boards/import", json={"format": "xmind", "content": _xmind({"content.xml": b"<xmap-content/>"})})
    assert old.status_code == 422 and "XMind 8" in old.text
    junk = ai_client.post("/whiteboard/boards/import", json={"format": "xmind", "content": base64.b64encode(b"not a zip").decode()})
    assert junk.status_code == 422 and "not an XMind file" in junk.text


def test_a_map_that_unpacks_too_large_is_refused(ai_client, monkeypatch):
    #: The limit lives with the parser, in wb_import.
    from tessellate.api import wb_import as service

    monkeypatch.setattr(service, "MAX_XMIND_JSON_BYTES", 100)
    root = {"id": "r", "title": "Big", "children": {"attached": [{"id": str(i), "title": f"Topic {i}"} for i in range(20)]}}
    out = ai_client.post("/whiteboard/boards/import", json={"format": "xmind", "content": _xmind({"content.json": _sheet(root)})})
    assert out.status_code == 422 and "too large" in out.text
