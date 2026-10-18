"""The hand-drawn look (INBOX 797, canvasdepth2; WHITEBOARD_PLAN "canvasdepth,
ranked" row 7, Excalidraw's). A board option, `background.rough`, and an
item's own `rough` over it; each line is resampled with a wobble seeded by
the item's id and drawn twice. The browser half, the paths compared across
renders, is `scratchpad/ui-sweeps/wbdepth2.js wbrough`."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WB = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def test_the_board_look_stores_only_on_and_a_patch_turns_it_off(ai_client):
    board = ai_client.post("/whiteboard/boards", json={"name": "Rough", "type": "board"}).json()
    on = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"rough": True}})
    assert on.status_code == 200 and on.json()["background"] == {"rough": True}
    state = ai_client.get("/whiteboard/", params={"board_id": board["id"]}).json()
    assert state["background"]["rough"] is True
    off = ai_client.put(f"/whiteboard/boards/{board['id']}", json={"background": {"rough": False}})
    assert off.json()["background"] == {}


def test_only_the_drawn_line_is_roughened_and_seeded_by_the_item():
    render = WB[WB.index('d3.select(this).select(".sketch-hitbox").attr("d", hitboxData ?? pathData);') :][:1600]
    assert render.index(".sketch-hitbox") < render.index("wbRoughD(pathData, d.id)")
    rough = _body(FMT, "function wbRoughD(")
    assert "wbRoughRandom(" in rough and "WB_ROUGH_CACHE.set(key, out)" in rough
    assert "Math.random" not in rough, "the look must be the same on every render"
    draws = _body(FMT, "function wbDrawsRough(")
    for spared in ('"draw"', '"highlighter"', "wbIsMap()"):
        assert spared in draws


def test_the_two_switches_and_the_undo():
    assert 'id="wb-rough-toggle"' in HTML and 'data-fmt="rough"' in HTML and 'id="wb-fmt-rough"' in HTML
    assert '"rough"' in FMT[FMT.index("const WB_FMT_FIELDS") :][:400]
    assert "rough: was.rough ?? null" in WB
    assert '"rough" in patch' in WB
