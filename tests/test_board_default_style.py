"""A board's default style (draw.io's "Set as default style", Ctrl+Alt+D;
WHITEBOARD_PLAN "The draw.io programme" section 1): `background.defaults`
holds `{shape, link, text}`, each a small dict of style values the tools start
a new item with. It rides in the background family, so the state route and the
board list already carry it, and null clears it."""

from __future__ import annotations

from tests._app_js import frontend_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = frontend_text("whiteboard.js")
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")


def _board(client):
    return client.post("/whiteboard/boards", json={"name": "Defaults board", "type": "board"}).json()


def test_defaults_are_stored_read_back_and_cleared(ai_client):
    board = _board(ai_client)
    url = f"/whiteboard/boards/{board['id']}"
    defaults = {"shape": {"color": "#112233", "fill": "#ddeeff", "round": 12, "gradient": {"to": "#ffffff", "dir": "south"}}, "link": {"color": "#445566", "flow": True}}
    out = ai_client.put(url, json={"background": {"defaults": defaults}})
    assert out.status_code == 200, out.text
    assert out.json()["background"]["defaults"] == defaults
    state = ai_client.get(f"/whiteboard/?board_id={board['id']}").json()
    assert state["background"]["defaults"] == defaults
    # A colour sent later leaves the defaults alone; null takes them off.
    kept = ai_client.put(url, json={"background": {"color": "#abcdef"}}).json()["background"]
    assert kept["defaults"] == defaults and kept["color"] == "#abcdef"
    cleared = ai_client.put(url, json={"background": {"defaults": None}}).json()["background"]
    assert "defaults" not in cleared and cleared["color"] == "#abcdef"


def test_defaults_that_are_not_style_are_refused_or_dropped(ai_client):
    board = _board(ai_client)
    url = f"/whiteboard/boards/{board['id']}"
    for bad in ("red", ["shape"], {"shape": "red"}, {"shape": {"x" * 40: 1}}, {"shape": {"color": "x" * 200}}, {"shape": {"a b": 1}}):
        refused = ai_client.put(url, json={"background": {"defaults": bad}})
        assert refused.status_code == 422, bad
    # An unknown group is dropped, not stored; an empty one stores nothing.
    out = ai_client.put(url, json={"background": {"defaults": {"other": {"color": "#000000"}, "text": {}}}}).json()["background"]
    assert "defaults" not in out


def test_the_page_sets_reads_and_clears_them():
    assert "setDefault" in FMT and "withDefaults" in FMT
    # New sketches and objects start from them; the undo step restores them.
    assert 'wbFmtState.board?.withDefaults("link"' in JS and 'wbFmtState.board?.withDefaults(group, blob' in JS
    assert 'wbFmtState.board?.withDefaults("text"' in JS
    assert "defaults: was.defaults ?? null" in JS
    assert 'id: "set-default-style"' in CMD and 'keys: "Ctrl+Alt+D"' in CMD
    assert 'id: "clear-default-style"' in CMD


def test_pen_and_highlighter_strokes_and_cross_links_take_a_default(ai_client):
    board = _board(ai_client)
    url = f"/whiteboard/boards/{board['id']}"
    defaults = {"pen": {"color": "#112233", "width": 6}, "highlighter": {"color": "#ffee00", "width": 24, "opacity": 0.4}}
    out = ai_client.put(url, json={"background": {"defaults": defaults}}).json()["background"]
    assert out["defaults"] == defaults
    # The page picks the group from the stroke's own shape and applies it to each tool.
    assert '{ draw: "pen", highlighter: "highlighter" }[data.shape]' in FMT
    assert 'isHighlighter ? "highlighter" : "pen"' in JS
    # A map's cross-link goes through the same call as a board link.
    assert 'JSON.stringify(wbFmtState.board?.withDefaults("link", linkBase) ?? linkBase)' in JS
