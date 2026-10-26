"""The owner, 2026-10-10: "the edge arrows are still not moving and you cant
even see the top one", and "when I move the new connected sticky note, the
point at which the link line connects to it changes vertically" (INBOX 740,
746). Measured by `scratchpad/ui-sweeps/wbedgegrips.js`: 21/51 before (three
arrows, each left where the box was after a drag, a resize or a turn, and
two links off a resized box's outline by 14.7 and 48 units), 58/58 after."""

from pathlib import Path

WB = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = WB.index(f"function {name}(")
    return WB[start:WB.index("\n}\n", start)]


def test_four_arrows_one_per_side():
    assert 'const WB_CLONE_GRIP_DIRS = ["up", "right", "down", "left"];' in WB


def test_the_arrows_are_laid_out_from_the_turned_live_box_every_frame():
    body = _fn("wbLayoutCloneGrips")
    assert "wbItemRotation(source.kind, item)" in body
    assert "wbRotatePoint(" in body
    assert "d3.zoomTransform(container).k" in body
    # The selection bar's frame is the one every move, resize and turn asks for.
    frame = _fn("wbQueueSelectionBar")
    assert "wbLayoutCloneGrips();" in frame
    assert "wbLayoutCloneGrips();" in _fn("wbPublishInvZoom")


def test_a_resize_carries_links_and_arrows():
    start = WB.index("function resizeDrag(handle)")
    body = WB[start:WB.index("function objectRotateDrag()", start)]
    assert 'd._linkedSketches = wbLinkedSketchesFor(d.id, "object")' in body
    assert "wbMapNodeSizeCache?.delete(d.id)" in body
    assert "wbUpdateLinkedSketches(d.id, d._linkedSketches)" in body
    assert "wbQueueSelectionBar();" in body
    assert "delete d._linkedSketches" in body


def test_a_shape_stretched_or_turned_carries_its_links():
    body = _fn("wbFollowLiveShape")
    assert "sketch._dragLiveD = liveD" in body
    assert "delete sketch._dragLiveD" in body
    assert WB.count("wbFollowLiveShape(sketch, newD)") == 2
    assert WB.count("wbFollowLiveShape(sketch, null)") == 2


def test_clone_and_connect_joins_fixed_ports():
    body = _fn("wbCloneConnect")
    assert "sourceAnchor: { x: 0.5 + dir.x / 2, y: 0.5 + dir.y / 2 }" in body
    assert "targetAnchor: { x: 0.5 - dir.x / 2, y: 0.5 - dir.y / 2 }" in body


def test_the_bar_stands_clear_of_the_top_arrow():
    assert 'document.getElementById("wb-clone-grips") ? 72 : 44' in WB


def test_the_top_arrow_stands_clear_of_the_rotation_grip():
    # INBOX 1354: the grip is 28px up; at 42 the arrow took presses 10px
    # from its centre, so a turn started as a copy
    assert "const WB_CLONE_GRIP_OUT = { up: 56," in WB


def test_a_note_card_gets_the_arrows_and_they_make_a_new_note():
    """WHITEBOARD_PLAN decision E1 (INBOX 826, the owner: "what happened to
    those edge triangle arrows??" over a selected note card). A card's arrow
    makes a new note joined to it, never a copy of the note, and says so."""
    source = _fn("wbCloneSource")
    assert 'kind === "node") return null' not in source and "wbIsMap()" in source
    connect = _fn("wbCloneConnect")
    assert 'source.kind === "node"' in connect and "wbCloneNoteCard(source, dirName)" in connect
    made = _fn("wbCloneNoteCard")
    assert '"/entries"' in made and '"noteMade"' in made and "wbRecordGesture" in made
    assert "sourceAnchor" in made and 'endCap: "arrow"' in made and "wbEditNodeText(made.id)" in made
    assert "New note ${dir.words}, joined (Alt+Shift+Arrow)" in WB
    from tessellate.ai import help_chat

    assert any("a note card's arrows make a new note" in t["body"] for t in help_chat.HELP_TOPICS)
