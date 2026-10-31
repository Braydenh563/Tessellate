"""INBOX 1471: a second click on the note whose panel is open closes it.

The owner: "if I click on a graph node and it shows the popup, if I click on
the same one again the popup should close". A click on another note still
switches the panel (`openGraphPopup` re-targets it), Escape and a click on
empty canvas still close it, and Enter or Space on the focused note toggles it
the same way. Measured with a real mouse by a Playwright sweep at 1440 by 900:
click 1 shown, click 2 hidden, click 3 shown, another note switched, Escape and
an outside click hid it, Enter and Space each toggled.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = (ROOT / "frontend" / "js" / "graph.js").read_text(encoding="utf-8")
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _function(source: str, name: str, kind: str = "function") -> str:
    start = source.index(f"{kind} {name}(")
    return source[start : source.index("\n}\n", start)]


def test_the_open_check_needs_the_same_note_and_a_visible_panel() -> None:
    body = _function(GRAPH, "graphPopupShows")
    assert "graphPopupId === node.id" in body
    assert 'classList.contains("hidden")' in body


def test_a_click_on_the_open_note_closes_before_it_would_reopen() -> None:
    body = _function(CANVAS, "gcClickNode")
    assert body.index("graphPopupShows(node)") < body.index("openGraphPopup(")
    assert "closeGraphPopup();" in body[body.index("graphPopupShows(node)") :]


def test_enter_and_space_toggle_the_same_way() -> None:
    start = GRAPH.index('event.key === "Enter" || event.key === " "')
    block = GRAPH[start : start + 400]
    assert "graphPopupShows(current)" in block and "closeGraphPopup(true)" in block
    assert "openGraphPopup(" in block
