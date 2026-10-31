"""A stamp vote can be taken back (INBOX 1493, the owner: "no wqay tp remove a
stamp vote"). Pressing a stamp on a topic is a toggle per person: the first
press adds yours, the second takes yours back. The chip also has a menu
(`kebabMenu`): Remove one and Clear all, so a count that predates the toggle
(the owner's "star 8") can be brought down. Every change is one Undo step
(`wbMapSetExtra`, `wbRecordGesture`). The browser half is
`scratchpad/ui-sweeps/mapdepth2.js mapstamps`."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP = (ROOT / "frontend" / "js" / "whiteboard-map.js").read_text(encoding="utf-8")
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "library-lazy.css").read_text(encoding="utf-8")

node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not available")


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def _made(ai_client):
    made = ai_client.post("/whiteboard/boards/import", json={"format": "markdown", "content": "# M\n- Root\n  - Picnic", "name": "Votes"}).json()
    objs = ai_client.get("/whiteboard/", params={"board_id": made["id"]}).json()["objects"]
    picnic = next(o for o in objs if o["data"].get("content") == "Picnic")
    body = {k: picnic[k] for k in ("kind", "x", "y", "width", "height", "parent_id", "board_id")}
    return made, picnic, body


def test_which_stamps_are_yours_is_stored_bounded_and_kept_out_of_the_exports(ai_client):
    made, picnic, body = _made(ai_client)
    put = lambda data: ai_client.put(f"/whiteboard/objects/{picnic['id']}", json={**body, "data": {**picnic['data'], **data}})  # noqa: E731
    ok = put({"stamps": {"star": 8, "up": 1}, "stamped": ["star"]})
    assert ok.status_code == 200 and ok.json()["data"]["stamped"] == ["star"]
    # A stamp that has no count cannot be yours.
    dropped = put({"stamps": {"star": 2}, "stamped": ["star", "up"]})
    assert dropped.json()["data"]["stamped"] == ["star"]
    for bad in (["smile"], ["up"] * 7):
        assert put({"stamps": {"up": 1}, "stamped": bad}).status_code == 422, bad
    put({"stamps": {"star": 8, "up": 1}, "stamped": ["star"]})
    for fmt in ("opml", "freemind"):
        text = ai_client.get(f"/whiteboard/boards/{made['id']}/export", params={"format": fmt}).text
        assert "_stamps=" in text and "_stamped" not in text, fmt


HARNESS = r"""
const vm = require("node:vm");
const fs = require("node:fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const grab = (start) => { const i = src.indexOf(start); return src.slice(i, src.indexOf("\n}\n", i) + 3); };
const consts = src.slice(src.indexOf("const WB_MAP_STAMPS"), src.indexOf("]);", src.indexOf("const WB_MAP_STAMPS")) + 3);
const ctx = { Object, Array, Math };
vm.createContext(ctx);
vm.runInContext(consts + grab("function wbMapStampPatch(") + ";globalThis.f = wbMapStampPatch;", ctx);
const f = ctx.f;
const j = (v) => JSON.parse(JSON.stringify(v));
const out = {
  first: j(f({}, "star", "toggle")),
  second: j(f({ stamps: { star: 1 }, stamped: ["star"] }, "star", "toggle")),
  legacy: j(f({ stamps: { star: 8 } }, "star", "toggle")),
  legacyBack: j(f({ stamps: { star: 9 }, stamped: ["star"] }, "star", "toggle")),
  keepsOthers: j(f({ stamps: { star: 1, up: 2 }, stamped: ["star", "up"] }, "star", "toggle")),
  one: j(f({ stamps: { star: 8 } }, "star", "one")),
  oneMine: j(f({ stamps: { star: 1 }, stamped: ["star"] }, "star", "one")),
  oneKeepsMine: j(f({ stamps: { star: 3 }, stamped: ["star"] }, "star", "one")),
  all: j(f({ stamps: { star: 8, up: 1 }, stamped: ["star"] }, "star", "all")),
  allLast: j(f({ stamps: { star: 8 }, stamped: ["star"] }, "star", "all")),
  none: f({}, "star", "one"),
  unknown: f({}, "smile", "toggle"),
  cap: f({ stamps: { star: 999 } }, "star", "toggle"),
};
console.log(JSON.stringify(out));
"""


@node
def test_a_stamp_toggles_per_person_and_a_count_comes_down_one_or_all():
    run = subprocess.run(["node", "-e", HARNESS, str(ROOT / "frontend" / "js" / "whiteboard-map.js")], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    got = json.loads(run.stdout)
    pick = lambda r: (r["stamps"], r["stamped"])  # noqa: E731
    assert pick(got["first"]) == ({"star": 1}, ["star"])
    assert pick(got["second"]) == (None, None), "the second press takes yours back, and the last stamp clears the field"
    assert pick(got["legacy"]) == ({"star": 9}, ["star"]), "a count from before the toggle gains yours"
    assert pick(got["legacyBack"]) == ({"star": 8}, None)
    assert pick(got["keepsOthers"]) == ({"up": 2}, ["up"])
    assert pick(got["one"]) == ({"star": 7}, None)
    assert pick(got["oneMine"]) == (None, None), "the last one removed is yours too"
    assert pick(got["oneKeepsMine"]) == ({"star": 2}, ["star"])
    assert pick(got["all"]) == ({"up": 1}, None)
    assert pick(got["allLast"]) == (None, None)
    assert got["none"] is None and got["unknown"] is None and got["cap"] is None


def test_the_chip_is_a_toggle_with_a_menu_and_every_change_is_one_undo_step():
    toggle = _body(MAP, "async function wbMapStampSet(")
    assert "wbMapSetExtra(node, { stamps: patch.stamps, stamped: patch.stamped }, patch.said)" in toggle
    assert "wbMapAddStamp" not in MAP and "wbMapAddStamp" not in WB, "the add-only path is replaced, not layered"
    paint = _body(MAP, "function wbMapPaintExtras(")
    assert "kebabMenu(" in paint and '"Remove one"' in paint and '"Clear all"' in paint
    assert 'wrap.className = "wb-map-stamp-wrap"' in paint
    tags = MAP[MAP.index('el.append("div").attr("class", "wb-map-tags")') :][:700]
    assert '.closest(".wb-map-stamp-wrap")' in tags and 'wbMapStampSet(wbMapLiveDatum(d), stamp.dataset.stamp, "toggle")' in tags
    assert '"stamped"' in MAP[MAP.index("const WB_MAP_CONTENT_KEYS") :][:400], "yours is content: a look reset keeps it"
    assert 'wbMapStampSet(mapNode, name, "toggle")' in WB and "{ stamps: null, stamped: null }" in WB
    assert ".wb-map-stamp-wrap" in CSS and ".wb-map-stamp-wrap .kebab-opener" in CSS


def test_the_guide_says_a_stamp_is_a_toggle_with_a_menu():
    from tessellate.ai.help_topics_more import MORE_TOPICS  # noqa: PLC0415

    topic = next(t for t in MORE_TOPICS if t["id"] == "mind-map-callouts")
    body = topic["body"]
    assert "again takes yours back" in body and "Remove one" in body and "Clear all" in body
    assert "add one more" not in body, "the old add-only wording"
