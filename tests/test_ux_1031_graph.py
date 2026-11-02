"""Audit 1031 class 33 (GR4, GR7, GR8): the map's legibility.

GR4: a dot is never under 2.5 screen pixels on a coarse pointer (a lower
label gate for a big map was measured on 1,200 notes and named none more: the
collision rule leaves no free place, so it only cost placement work). GR7: the open card is named "Note: title",
not "Edit note". GR8: Hide unlinked says how many notes it takes off."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _js(name: str) -> str:
    return (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")


def test_a_dot_has_a_floor_on_a_coarse_pointer():
    text = _js("graph-canvas.js")
    assert '"(pointer: coarse)")?.matches ? 2.5 : 0;' in text
    assert "Math.max(node.r + node._grow, GC_MIN_DOT_PX / k)" in text


def test_the_open_card_is_named_note_and_its_title():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    popup = html.split('id="graph-popup"', 1)[1].split(">", 1)[0]
    assert 'aria-label="Note"' in popup and "Edit note" not in popup
    graph = _js("graph.js")
    assert graph.count('setAttribute("aria-label", `Note: ${') == 2


def test_hide_unlinked_says_how_many_it_takes_off():
    text = _js("graph-canvas.js")
    label = text.split("function gcOrphansLabel(box, count)", 1)[1].split("\n}\n", 1)[0]
    assert 'nounCount(count, "unlinked note")' in label and '"Hide unlinked"' in label
    # Counted whether or not the switch is on, notes only (a group is no note).
    assert "loose.filter((n) => !n.isGroup).length" in text
