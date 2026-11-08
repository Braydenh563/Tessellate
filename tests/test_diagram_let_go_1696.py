"""A press off the diagram's elements lets go of the pick, for every kind (INBOX 1696).

The owner, again: "I still cant clcik off diagram elements". Measured before
(dgmoff sweep, 1440, one block picked from the list or the picture, then a
press): a flowchart let go on empty picture space and Escape but not on a press
beside the picture; a sequence, mind map or timeline let go on none of the
three. After: all four kinds let go on all three. The rules that make it are
kept here; the clicks are the sweep's.
"""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"
BUILDER = (JS / "diagram-builder.js").read_text(encoding="utf-8")
CANVAS = (JS / "diagram-canvas.js").read_text(encoding="utf-8")
LETGO = (JS / "diagram-letgo.js").read_text(encoding="utf-8")
EMBED = (JS / "diagram-embed.js").read_text(encoding="utf-8")


def _let_go() -> str:
    return LETGO.split("  function wire(S, h) {", 1)[1].split("\n  }\n", 1)[0]


def test_every_kind_is_wired_after_its_own_handlers():
    show = BUILDER.split("async function show(", 1)[1]
    #: After the canvas (a flowchart's own `S.clear`, which also puts an armed handle back) and for every kind, not only `!S.k`.
    wired = '    if (S && (await ensureModule("diagramLetGo"))) diagramModel.letgo.wire(S, helpers);\n'
    assert show.index("diagramModel.canvas.wire(S, helpers)") < show.index(wired)
    assert 'diagramLetGo: ["/js/diagram-letgo.js"]' in (JS / "documents-mermaid.js").read_text(encoding="utf-8")


def test_a_kind_without_a_canvas_gets_the_same_clear_and_its_three_ways_out():
    body = _let_go()
    assert "if (!S.clear) {" in body
    assert "S.sel = null;" in body and "S.picked?.clear();" in body and "h.stops(S, S.tree.querySelector(\".dgm-block\"));" in body
    #: Empty picture, empty list, Escape: the canvas's own three, for a kind.
    assert 'S.fig.addEventListener("click"' in body
    assert 'S.pane.addEventListener("click"' in body
    assert 'event.key !== "Escape"' in body
    #: The flowchart keeps its own (diagram-canvas.js, INBOX 1661 h), and the embed's Escape still asks the pane first.
    assert "S.clear = () => {" in CANVAS
    assert "if (pane?.clear?.()) return event.preventDefault(), event.stopPropagation();" in EMBED


def test_a_press_beside_the_picture_lets_go_but_never_one_on_an_element():
    body = _let_go()
    assert 'document.addEventListener("click"' in body
    #: One document listener for every builder, whatever was opened.
    assert "if (on) return;" in body
    keep = LETGO.split("const KEEP = ", 1)[1].split(";\n", 1)[0]
    for sel in (".dgm-block", ".dgm-picture", ".dock", "button", "input", "[contenteditable]", ".action-menu", ".help-popover"):
        assert sel in keep, sel
    #: Only presses in the builder's own page, and a closed builder is dropped.
    assert '.closest(".doc-preview, .modal-card")' in body
    assert "if (!one.root.isConnected) live.delete(one);" in body
