"""INBOX 1661 (g), (h), (i): the overlay in the picture's scrolled coordinates, no selection, and the view names.

The measured side (zero box intersections over 20 adds on four sides, ring and input error against the drawing, a press on
empty canvas and Escape) is the sweep named in `docs/roadmap/agent-remaining/diagram-1108.md`; this file holds what a diff can break.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def _js(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    start = CSS.index("\n" + selector + " {") + 1
    return CSS[start : CSS.index("}", start)]


def test_the_overlay_is_a_child_of_the_figure_and_a_zero_size_origin_in_its_scrolled_content():
    overlay = _js("diagram-overlay.js")
    assert "fig.append(layer)" in overlay and "stage.append(layer)" not in overlay
    # No script positions the layer from the pane's padding box, and no redraw waits on a scroll event.
    assert "fig.offsetLeft" not in overlay and 'fig.addEventListener("scroll"' not in overlay
    rule = _rule(".dgm-overlay")
    assert "position: absolute" in rule and "inline-size: 0" in rule and "block-size: 0" in rule and "overflow" not in rule
    assert "position: relative" in _rule(".dgm .dgm-picture")
    # A new picture keeps the layer; the other modules find it inside the figure.
    assert '...figure.querySelectorAll(":scope > .dgm-overlay")' in _js("mermaid-draw.js")
    for name in ("diagram-edges.js", "diagram-canvas.js", "diagram-edge-pick.js"):
        assert 'fig?.querySelector(":scope > .dgm-overlay")' in _js(name), name


def test_a_press_on_what_the_overlay_holds_is_not_a_press_on_the_picture():
    # The handles, an arrow's ends and the name field are in the figure now: the figure's own listeners skip them.
    assert 'event.target.closest?.(".dgm-overlay > *")' in _js("diagram-view.js")
    assert '".dock, .dgm-overlay > *"' in _js("diagram-edge-pick.js")
    assert '".dock, .dgm-overlay > *"' in _js("diagram-edges.js")
    assert ".dgm-overlay > *" in _js("diagram-canvas.js")


def test_the_drop_target_on_empty_space_is_the_figure_not_the_zero_size_layer():
    assert "card: S.fig, word: g.tile" in _js("diagram-canvas.js")
    assert ".dgm-picture.dgm-target" in CSS and ".dgm-overlay.dgm-target" not in CSS


def test_a_redraw_gives_the_pane_its_scroll_back():
    view = _js("diagram-view.js")
    assert "if (img !== shown) fig.scrollTo(...(shown ? seen : [0, 0]))" in view
    assert 'fig.addEventListener("scroll", () => (seen = [fig.scrollLeft, fig.scrollTop])' in view


def test_a_press_on_empty_canvas_and_escape_clear_the_selection():
    canvas = _js("diagram-canvas.js")
    assert "S.clear = () => {" in canvas and "S.pick ? S.pick([], null)" in canvas
    assert "h.stops(S, S.tree.querySelector" in canvas
    # A press that is a node, an arrow, a modified press or the end of a marquee is not a press on empty space.
    assert "math.nodeAt(S.hit, at," in canvas and "edges?.math.edgeAt(" in canvas
    assert "event.timeStamp - sweptAt < 400" in canvas
    assert 'event.key !== "Escape"' in canvas
    # The dialog's own Escape (diagram-embed.js) lets go of the pick before it closes the window; an armed handle goes first.
    assert "if (pane?.clear?.()) return event.preventDefault(), event.stopPropagation();" in _js("diagram-embed.js")
    assert "S.cancelArm = () => Boolean(armed) && (disarm(), true);" in _js("diagram-edges.js")


def test_the_views_are_named_for_what_they_are_with_a_hint_and_a_guide_line():
    docs = _js("documents.js")
    embed = _js("diagram-embed.js")
    for words in ('"Picture", "Picture first:', '"List", "List first:'):
        assert words in docs, words
    assert '["canvas", "Picture"], ["blocks", "List"]' in embed
    # The ids stay: stored views and the layout rules read them.
    assert 'dataset.docView = mode' in docs and '[data-dgm-layout="canvas"]' in CSS
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "Picture gives the drawing the room, List gives the blocks list the room, and Source is the text." in html
    assert "Picture gives the drawing the room, List gives the blocks list the room, and Source is the text." in embed
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-blocks"))
    assert "Picture opens first" in body and "List gives the blocks list the room" in body and "Escape lets go of the pick" in body
