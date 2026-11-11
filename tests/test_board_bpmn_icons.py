"""BPMN and icon sets as board library sections (WHITEBOARD_PLAN section 1, gap rows 9 and 11)."""

import json
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "frontend" / "board-library"


def _set(key: str) -> dict:
    return json.loads((LIB / f"{key}.json").read_text(encoding="utf-8"))


def test_the_bpmn_set_has_events_tasks_gateways_and_pools() -> None:
    keys = {item["key"] for item in _set("bpmn")["items"]}
    assert {"start-event", "intermediate-event", "end-event", "task", "gateway-exclusive", "gateway-parallel", "pool", "pool-two-lanes"} <= keys
    end = next(i for i in _set("bpmn")["items"] if i["key"] == "end-event")
    start = next(i for i in _set("bpmn")["items"] if i["key"] == "start-event")
    # BPMN's own reading: an end event is the thick ring, a start event the thin one.
    assert end["payload"]["items"][0]["data"]["width"] > start["payload"]["items"][0]["data"]["width"]


def test_every_item_of_the_new_sets_is_a_drawable_element() -> None:
    for key in ("bpmn", "cloud-network", "devices-people"):
        data = _set(key)
        assert data["format"] == "memorymap-library-set" and data["items"], key
        for item in data["items"]:
            box = item["payload"]["box"]
            assert box["w"] > 0 and box["h"] > 0, (key, item["key"])
            assert item["payload"]["items"][0]["data"]["d"].startswith("M"), (key, item["key"])


def test_the_icon_sets_use_the_vendored_phosphor_paths_and_the_index_lists_all_three() -> None:
    glyphs = json.loads((LIB / "icons.json").read_text(encoding="utf-8"))["icons"]
    for key in ("cloud-network", "devices-people"):
        for item in _set(key)["items"]:
            data = item["payload"]["items"][0]["data"]
            assert data["d"] == glyphs[data["icon"]], (key, item["key"])
    index = {s["key"]: s for s in json.loads((LIB / "index.json").read_text(encoding="utf-8"))["sets"]}
    for key in ("bpmn", "cloud-network", "devices-people"):
        assert index[key]["count"] == len(_set(key)["items"]), key
