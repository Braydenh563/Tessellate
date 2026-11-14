"""A relinked map topic is laid out as its new parent's child, and one Undo
takes it back (INBOX 410: "when I relink or newly link two mindmap nodes,
they clump together??").

`scratchpad/ui-sweeps/maprelink.js` is the measurement: a branch dropped on a
topic, and a loose topic joined by a line, on a tidied map and a Free one.
Before: on a Free map the dropped branch stayed on top of the topic it was
dropped on (7220px2 of overlap), and none of the four cases could be undone.
After: no overlap, the branch beside its new parent with its own child
beside it, and one Undo restores the parent and every place.

The suite cannot open a board, so this holds the shape the sweep measured:
the history has an entry that writes `parent_id` (the only one that can,
through `/move`), the transplant pushes exactly one entry, and a Free map
places the branch rather than leaving it where it landed.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._app_js import unwrapped

ROOT = Path(__file__).resolve().parent.parent
#: Every script, not one file: whiteboard.js is being split, and a rule about
#: a function should not break because the function moved house.
JS = "\n".join(unwrapped(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "frontend" / "js").glob("*.js")))


def _body(name: str) -> str:
    match = re.search(rf"^(?:async )?function {re.escape(name)}\(", JS, re.MULTILINE)
    assert match, f"{name} is gone; this lint is about its body"
    rest = JS[match.end():]
    end = re.search(r"^(?:async )?function \w+\(", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def test_the_history_can_put_a_topic_back_under_its_old_parent() -> None:
    body = _body("wbApplyHistoryEntry")
    assert 'entry.action === "reparent"' in body
    assert "/move" in body, "only `/move` may write parent_id; a PUT of the row cannot"


def test_a_transplant_is_one_undo_step() -> None:
    body = _body("wbMapTransplant")
    assert body.count("wbPushUndo(") == 1
    assert '{ action: "batch", entries: history }' in body
    assert 'action: "reparent"' in body


def test_a_free_map_places_the_branch_as_a_child() -> None:
    body = _body("wbMapTransplant")
    assert 'wbMapLayout() === "free"' in body and "wbMapPlaceAsChild(" in body
    place = _body("wbMapPlaceAsChild")
    assert "wbSaveBulkMove(" in place, "the new place has to be saved, not only drawn"


def test_a_drop_hands_the_transplant_where_the_branch_was_picked_up() -> None:
    assert re.search(r"wbMapTransplant\(d, dropTarget\.id, alone, \{ before \}\)", JS)
