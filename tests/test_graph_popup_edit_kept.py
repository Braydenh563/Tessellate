"""The node popup keeps an unsaved edit through every way out (audit G2).

Escape, the X, a click on the map and a click on another note used to drop the
typing. One guard (`keepGraphPopupEdit`) now runs first in `closeGraphPopup`
(Escape, the X, the map click and the new-note path all end there) and in
`openGraphPopup` when another note is picked. Behaviour is measured in the app
by the sweep named in the commit; these pin the wiring.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = GRAPH.index(f"function {name}(")
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


def test_close_and_switch_both_pass_through_the_one_guard():
    assert _fn("closeGraphPopup").lstrip().split("\n")[1].strip() == "keepGraphPopupEdit();"
    assert "keepGraphPopupEdit();" in _fn("openGraphPopup")


def test_the_guard_saves_only_a_loaded_dirty_popup():
    assert "Loading…" in _fn("graphPopupIsDirty")
    assert "saveGraphPopup({ leaving: true })" in _fn("keepGraphPopupEdit")


def test_a_late_save_does_not_close_or_overwrite_the_next_popup():
    body = _fn("saveGraphPopup")
    assert "graphPopupId === id" in body
    assert body.count("graphPopupId === id") >= 2
