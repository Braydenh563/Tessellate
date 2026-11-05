"""INBOX 1621 R9a: a diagram is an object kind, so its Library card carries into a note
or document as `![[Title]]` and the tray holds and pastes it."""

from __future__ import annotations

from tests._objmove_node import needs_node, run

FILES = ["obj-ref.js", "obj-clip.js", "obj-drag.js", "obj-reorder.js", "obj-carry.js", "obj-tray.js"]
STUBS = """
const store = {};
globalThis.sessionStorage = { getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; } };
globalThis.toast = () => {};
"""


@needs_node
def test_a_diagram_reference_is_built_and_written_as_an_embed_link() -> None:
    out = run(FILES, STUBS + """
    const ref = objRef("diagram", 7, "Order flow");
    __out([ref, objLinkText(ref), objLinkText(objRef("diagram", 8, "A [b] | c")), objDefaultTitle("diagram", 3), OBJ_ICON.diagram])
    """)
    assert out[0] == {"kind": "diagram", "id": 7, "title": "Order flow", "url": ""}
    assert out[1] == "![[Order flow]]"
    assert out[2] == "![[A b c]]"
    assert out[3] == "Diagram 3"
    assert out[4] == "ph-flow-arrow"


@needs_node
def test_a_library_diagram_card_gives_a_reference_and_the_tray_holds_it() -> None:
    out = run(FILES, STUBS + """
    const card = { dataset: { stopKey: "diagram:5" }, getAttribute: () => null, matches: (s) => s === "[data-stop-key]",
      querySelector: () => ({ textContent: "Flow" }) };
    card.closest = (s) => (s.split(",").includes("[data-stop-key]") ? card : null);
    const ref = objRefFromCard(card);
    objTrayAdd(ref);
    __out({ ref, held: objTray.map(objKey), stage: typeof OBJ_STAGE.diagram, staged: typeof OBJ_STAGED.diagram, label: OBJ_ICON_LABEL.diagram });
    """)
    assert out["ref"]["kind"] == "diagram" and out["ref"]["title"] == "Flow"
    assert out["held"] == ["diagram:5"]
    assert out["stage"] == "function" and out["staged"] == "function"
    assert out["label"] == "ph:flow-arrow"

