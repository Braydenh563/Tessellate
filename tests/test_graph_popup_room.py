"""The graph's note popup and New note stay above the status bar.

The owner, 2026-10-11: "the graph popups get cut off now at the bottom" (the
dock under the status bar at about 1,000px tall). Measured by
`scratchpad/ui-sweeps/graphpopupclip.js` at 1440x900, 1280x720 and 390x844,
light and dark: the dock's bottom at or above the status bar's top. The
cause: each was placed once, from its height at that moment, and grew after
(its fields settling, 30 to 60px), so its foot went past the map. These pin
the wiring those numbers rest on.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "04-chat-dock-appearance.css").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = GRAPH.index(f"function {name}(")
    return GRAPH[start : GRAPH.index("\n}\n", start) + 2]


def test_the_room_ends_at_the_status_bar():
    room = _fn("graphPanelRoom")
    assert 'document.getElementById("status-bar")' in room
    assert "Math.min(box.bottom, barTop, innerHeight)" in room


def test_both_are_placed_again_when_they_change_size():
    watch = _fn("watchGraphPopupSize")
    assert "new ResizeObserver(" in watch and "requestAnimationFrame(" in watch
    assert "watchGraphPopupSize(popup, placeGraphPopup);" in _fn("placeGraphPopup")
    assert "watchGraphPopupSize(popup, placeGraphNewNote);" in _fn("openGraphNewNote")
    for name in ("placeGraphPopup", "placeGraphNewNote"):
        body = _fn(name)
        assert "graphPanelRoom()" in body, name
        assert "room - size.height - 8" in body, name


def test_the_dock_is_pinned_at_the_foot_of_a_scrolling_popup():
    #: INBOX 1630: pinned by structure now, not by `sticky` inside one scroller.
    #: The panel is a column whose body scrolls, so the dock is always whole.
    lazy = (ROOT / "frontend" / "css" / "graph-lazy.css").read_text(encoding="utf-8")
    rule = lazy[lazy.index("#graph-popup {") :]
    rule = rule[: rule.index("}")]
    assert "flex-direction: column;" in rule and "overflow: hidden;" in rule
    assert "overflow-y: auto;" in lazy[lazy.index(".graph-popup-body {") :].split("}")[0]
