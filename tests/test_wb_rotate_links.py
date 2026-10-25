"""INBOX 647, the owner: "when rotating objects on the whiteboard the
connections and links don't automatically update in their connection position
until I move the object I rotated". A move redrew the links touching the
dragged item each frame (`wbUpdateLinkedSketches`); the three turns (a card's
grip, a box's grip, a selection's grip) set `rotation` and saved without it,
so the link stayed on the unturned box until the next move. Measured by
`scratchpad/ui-sweeps/wbrotatelinks.js`: FAIL before, PASS after."""

import re
from pathlib import Path

WB = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _body(name: str) -> str:
    start = WB.index(f"function {name}()")
    return WB[start:WB.index("\n  }\n", start)]


def test_a_card_and_a_box_carry_their_links_round_as_they_turn():
    for name, kind in (("nodeRotateDrag", "node"), ("objectRotateDrag", "object")):
        body = _body(name)
        assert f'd._linkedSketches = wbLinkedSketchesFor(d.id, "{kind}")' in body, name
        assert "wbUpdateLinkedSketches(d.id, d._linkedSketches)" in body, name
        assert "delete d._linkedSketches" in body, name


def test_a_turned_selection_carries_its_links_too():
    # One list, each link once; resize and turn share it (wbMultiLiveLinks).
    assert "spinLinks = wbMultiLiveLinks(rows);" in WB
    assert re.search(r"return \[\.\.\.new Set\(rows\.flatMap", WB)
    assert "if (spinLinks.length) wbUpdateLinkedSketches(null, spinLinks);" in WB
