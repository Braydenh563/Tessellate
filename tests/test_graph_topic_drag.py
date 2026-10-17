"""A topic is moved by its name and renamed where its name is.

The owner, 2026-10-10: "I want to be able to drag whole topics around on the
graph" and "I cant rename a topic??". A topic's name plate is its handle:
the zoom lets a press on it through to the drag, the drag holds the topic's
most linked note and carries every other drawn member at its offset, pinned
as a group with one write. Measured in the app by
scratchpad/ui-sweeps/graphtopicdrag.js (12 of 12 moved by the same delta,
12 pinned, one PUT /graph/pins).
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CANVAS = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = re.search(rf"\nfunction {name}\(", CANVAS).start() + 1
    return CANVAS[start : CANVAS.index("\n}\n", start) + 2]


SCRIPT = "\n".join(
    [
        _function("gcPlateAtWorld"),
        _function("gcTopicMembers"),
        _function("gcTopicCore"),
        """
const gcVisibleAtTime = (node) => !node.hidden;
const graphStructure = { topics: [{ id: 0, ids: [1, 2, 3], core_id: 2 }, { id: 1, ids: [4, 5, 6], core_id: 9 }] };
const nodes = [1, 2, 3, 4, 5, 6].map((id) => ({ id, x: id * 10, y: 0 }));
nodes[4].hidden = true;
const s = { size: "full", transform: { k: 1 }, nodes, topicPlates: [{ left: 0, right: 40, top: -30, bottom: -13, topic: 1 }] };
console.log(JSON.stringify({
  hit: gcPlateAtWorld(20, -20, s)?.id ?? null,
  miss: gcPlateAtWorld(20, 5, s),
  pane: gcPlateAtWorld(20, -20, { ...s, size: "pane" }),
  members: gcTopicMembers(graphStructure.topics[1], s).map((n) => n.id),
  core: gcTopicCore(graphStructure.topics[0], s).id,
  fallback: gcTopicCore(graphStructure.topics[1], s).id,
}));
""",
    ]
)


@pytest.fixture(scope="module")
def run():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    out = subprocess.run([node, "-e", SCRIPT], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_a_plate_is_found_under_the_pointer_on_the_tab_only(run):
    assert run["hit"] == 1
    assert run["miss"] is None and run["pane"] is None


def test_the_drag_carries_the_drawn_members_held_by_the_core(run):
    assert run["members"] == [4, 6], "a filtered-out member is not carried"
    assert run["core"] == 2
    assert run["fallback"] == 4, "with the core off the map, the first drawn member holds it"


def test_the_gesture_is_wired_end_to_end():
    zoom_filter = CANVAS[CANVAS.index(".filter((event) => {") : CANVAS.index('.on("start", () => {')]
    assert 'gcPlateAtWorld(x, y, s)' in zoom_filter, "the zoom must let a press on a plate through"
    assert "const topic = node ? null : gcPlateAtWorld(x, y, s);" in CANVAS
    assert "if (s.dragTopic) node._dragShift = true;" in CANVAS, "a topic is pinned as a group"
    assert "? gcTopicMembers(s.dragTopic, s)" in CANVAS
    assert 'apiJson("/graph/pins", { method: "PUT", body: JSON.stringify({ pins }) })' in CANVAS
    assert "!s.dragTopic ? graphNodeUnder(" in CANVAS, "dropping a topic never links"


def test_a_plate_double_click_renames_in_place():
    dbl = CANVAS[CANVAS.index('s.canvas.addEventListener("dblclick"') :]
    dbl = dbl[: dbl.index("gcTogglePin(node, s);")]
    assert "gcRenameTopicInline(plate);" in dbl
    body = _function("gcRenameTopicInline")
    assert 'event.key === "Enter"' in body and 'event.key === "Escape"' in body
    assert 'addEventListener("blur", () => finish(true))' in body


def test_a_topic_drag_is_one_pin_write_with_its_core_note():
    """Ledger 931: the core note's pin went out as its own PUT /graph/pin
    beside the group's PUT /graph/pins. It now joins the group's write."""
    end = CANVAS[CANVAS.index("function gcDragEnd(event)") : CANVAS.index('s.canvas.addEventListener("pointermove"')]
    assert "if (pins.length) pins.push({ id: node.id, x: node.fx, y: node.fy });" in end
    assert "else graphPinSave(node.id, node.graph_pin_x, node.graph_pin_y)" in end, "the lone note goes through the one pin door"
    assert end.index("pins.push({ id: node.id") < end.rindex("if (pins.length) savePins();")


def test_a_topic_card_files_its_notes_as_a_category_only_when_asked():
    """Ledger 945 ("How are they different from categories??"): the card
    offers File as a category; one move with one Undo, named for the topic."""
    card = CANVAS[CANVAS.index("function gcShowTopic(") : CANVAS.index("async function gcSaveTopicName(")]
    assert "ph:folder-simple-plus File as a category" in card
    assert "await moveNotesToCategory(topic.ids, wanted)" in card
    assert 'topic.name.replace(/^#/, "")' in card, "a tag-named topic files under the word, not the hash"
    guide = (ROOT / "src" / "tessellate" / "ai" / "help_chat.py").read_text(encoding="utf-8")
    assert "File as a category files its notes under one category" in guide


# The floating rename field matches the plate (OPEN row 795).


def _css(name: str) -> str:
    return (ROOT / "frontend" / "css" / name).read_text(encoding="utf-8")


def test_the_floating_topic_rename_is_the_plate_s_height():
    """OPEN row 795: the field floated 42px tall over a 17px topic plate."""
    graph = (ROOT / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    start = graph.index("function gcRenameTopicInline(")
    body = graph[start : graph.index("\n}\n", start)]
    assert "const plateH = (plate.bottom - plate.top) * t.k;" in body
    assert "field.style.height = `${height}px`;" in body and "Math.round(plateH + 6)" in body
    rule = re.search(r"\.graph-topic-rename\.is-floating\s*\{([^}]*)\}", _css("graph-lazy.css")).group(1)
    assert "min-height: 0" in rule and "padding: 0 var(--space-2)" in rule
