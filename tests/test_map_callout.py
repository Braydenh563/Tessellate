"""A callout on a topic, and labels under it (INBOX 797, canvasdepth2; MINDMAP_PLAN "canvasdepth,
ranked" row 2, XMind's). `data.callout`, a few words drawn in a bubble over
the topic's own as a row of its card, so a tidy measures it. The browser
half is `scratchpad/ui-sweeps/mapdepth2.js mapcallout`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def test_a_callout_is_stored_bounded_and_exported(ai_client):
    made = ai_client.post("/whiteboard/boards/import", json={"format": "markdown", "content": "# M\n- Root\n  - Hotel", "name": "Callouts"}).json()
    objs = ai_client.get("/whiteboard/", params={"board_id": made["id"]}).json()["objects"]
    hotel = next(o for o in objs if o["data"].get("content") == "Hotel")
    body = {k: hotel[k] for k in ("kind", "x", "y", "width", "height", "parent_id", "board_id")}
    ok = ai_client.put(f"/whiteboard/objects/{hotel['id']}", json={**body, "data": {**hotel["data"], "callout": "Near the station"}})
    assert ok.status_code == 200 and ok.json()["data"]["callout"] == "Near the station"
    long = ai_client.put(f"/whiteboard/objects/{hotel['id']}", json={**body, "data": {**hotel["data"], "callout": "x" * 201}})
    assert long.status_code == 422
    for fmt in ("opml", "freemind"):
        text = ai_client.get(f"/whiteboard/boards/{made['id']}/export", params={"format": fmt}).text
        assert '_callout="Near the station"' in text, fmt


def test_the_callout_is_a_row_of_the_card_painted_from_its_own_data():
    build = _body(MAP, "function wbBuildMapNode(")
    assert 'attr("class", "wb-map-callout")' in build
    assert "wbMapPaintExtras(node, d.data || {});" in _body(MAP, "function wbPaintMapNodeStyle(")
    assert ".wb-map-node[data-extras] {\n  flex-wrap: wrap;" in CSS
    assert ".wb-map-callout {\n  position: relative;\n  order: -1;\n  flex: 1 0 100%;" in CSS


def test_a_callout_change_and_its_tidy_are_one_undo_step():
    extra = _body(MAP, "async function wbMapSetExtra(")
    assert "wbRecordGesture(" in extra and "wbMapTidy(" in extra
    assert "wbMapSetExtra(node, { callout: next }" in _body(MAP, "async function wbMapEditCallout(")
    assert 'wbMapSetExtra(mapNode, { callout: null }' in WB
    assert '"callout"' in MAP[MAP.index("const WB_MAP_CONTENT_KEYS") :][:400]


def test_labels_are_trimmed_bounded_and_ride_the_exports_as_one_attribute(ai_client):
    made = ai_client.post("/whiteboard/boards/import", json={"format": "markdown", "content": "# M\n- Root\n  - Hotel", "name": "Labels"}).json()
    objs = ai_client.get("/whiteboard/", params={"board_id": made["id"]}).json()["objects"]
    hotel = next(o for o in objs if o["data"].get("content") == "Hotel")
    body = {k: hotel[k] for k in ("kind", "x", "y", "width", "height", "parent_id", "board_id")}
    ok = ai_client.put(f"/whiteboard/objects/{hotel['id']}", json={**body, "data": {**hotel["data"], "labels": [" booked ", "paid"]}})
    assert ok.status_code == 200 and ok.json()["data"]["labels"] == ["booked", "paid"]
    for bad in (["a,b"], ["x" * 31], [str(i) for i in range(9)]):
        refused = ai_client.put(f"/whiteboard/objects/{hotel['id']}", json={**body, "data": {**hotel["data"], "labels": bad}})
        assert refused.status_code == 422, bad
    for fmt in ("opml", "freemind"):
        text = ai_client.get(f"/whiteboard/boards/{made['id']}/export", params={"format": fmt}).text
        assert '_labels="booked,paid"' in text, fmt
        back = ai_client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": "Back"}).json()
        objs = ai_client.get("/whiteboard/", params={"board_id": back["id"]}).json()["objects"]
        assert any(o["data"].get("labels") == ["booked", "paid"] for o in objs), fmt


def test_labels_are_the_cards_last_row_painted_once_per_change():
    build = _body(MAP, "function wbBuildMapNode(")
    assert 'attr("class", "wb-map-tags")' in build
    paint = _body(MAP, "function wbMapPaintExtras(")
    #: Rebuilt only when the list changed: a repaint of the same labels writes nothing.
    assert "tags.dataset.key !== key" in paint and "replaceChildren(" in paint
    assert ".wb-map-tags {\n  display: flex;\n  flex: 1 0 100%;" in CSS
    assert "wbMapSetExtra(node, { labels: next }" in _body(MAP, "async function wbMapEditLabels(")
    assert '"labels"' in MAP[MAP.index("const WB_MAP_CONTENT_KEYS") :][:400]


def test_stamps_count_from_a_fixed_set_and_ride_the_exports(ai_client):
    made = ai_client.post("/whiteboard/boards/import", json={"format": "markdown", "content": "# M\n- Root\n  - Picnic", "name": "Votes"}).json()
    objs = ai_client.get("/whiteboard/", params={"board_id": made["id"]}).json()["objects"]
    picnic = next(o for o in objs if o["data"].get("content") == "Picnic")
    body = {k: picnic[k] for k in ("kind", "x", "y", "width", "height", "parent_id", "board_id")}
    ok = ai_client.put(f"/whiteboard/objects/{picnic['id']}", json={**body, "data": {**picnic["data"], "stamps": {"up": 3, "star": 1}}})
    assert ok.status_code == 200 and ok.json()["data"]["stamps"] == {"up": 3, "star": 1}
    for bad in ({"smile": 1}, {"up": 0}, {"up": 1000}):
        refused = ai_client.put(f"/whiteboard/objects/{picnic['id']}", json={**body, "data": {**picnic["data"], "stamps": bad}})
        assert refused.status_code == 422, bad
    for fmt in ("opml", "freemind"):
        text = ai_client.get(f"/whiteboard/boards/{made['id']}/export", params={"format": fmt}).text
        assert '_stamps="up:3,star:1"' in text, fmt
        back = ai_client.post("/whiteboard/boards/import", json={"format": fmt, "content": text, "name": "Back"}).json()
        objs = ai_client.get("/whiteboard/", params={"board_id": back["id"]}).json()["objects"]
        assert any(o["data"].get("stamps") == {"up": 3, "star": 1} for o in objs), fmt


def test_a_stamp_press_toggles_yours_and_never_starts_a_drag():
    """INBOX 1493 moved the intent from "adds one more" to a toggle per person
    (`tests/test_map_stamp_toggle.py` pins the toggle itself); the drag guard
    and the stamp set stay."""
    build = _body(MAP, "function wbBuildMapNode(")
    tags = build[build.index('attr("class", "wb-map-tags")') :]
    assert 'event.target.closest(".wb-map-stamp-wrap")) event.stopPropagation()' in tags
    assert 'wbMapStampSet(wbMapLiveDatum(d), stamp.dataset.stamp, "toggle")' in tags
    set_ = _body(MAP, "async function wbMapStampSet(")
    assert "wbMapSetExtra(node, { stamps: patch.stamps" in set_ and "count >= 999" in _body(MAP, "function wbMapStampPatch(")
    icons = MAP[MAP.index("const WB_MAP_STAMPS") :][:400]
    assert all(ord(ch) < 0x2000 for ch in icons), "an emoji in the stamp set"
    assert 'subItem("Stamps"' in WB and "wbMapSetExtra(mapNode, { stamps: null, stamped: null }" in WB
