"""A board action on a selection is one request, never one per item (audit 1031, BD2).

Ctrl+A on 362 items and two arrow presses sent 167 `PUT`s; a turn of 360
items sent 361; lock, hide, align, distribute, z-order, group, vote, restyle
and replace all did the same, each its own transaction and a half-saved
selection for as long as they took. `wbSaveMany` (`PUT /whiteboard/items/
save-many`) takes the whole set. The rule this holds: in the board's scripts,
no loop calls a per-item save (`wbSaveNode`, `wbSaveObject`,
`wbSaveSketchProps`, `wbSaveSketchD`, `wbSaveRow`, or a `PUT` through
`apiJson`). A loop mutates the items and collects `{ kind, item }` rows; one
`wbSaveMany(rows)` after it saves them. `wbMapSetNodeStyle` takes `{ rows }`
for the same reason, and a loop that calls it without `rows` is a per-item
write too.

A loop that must write one at a time (a create that needs the id the last one
returned, a chunked batch, a handler wired inside a loop whose write runs on
a later event) is named in `ALLOWED` with the reason. An entry that no longer
trips the rule fails too, so the list cannot go stale.
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api.asset_strip import strip_js

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

WRITE = re.compile(
    r"\bwb(?:SaveNode|SaveObject|SaveSketchProps|SaveSketchD|SaveRow)\s*\("
    r"|\bapiJson\([^;]*?method:\s*[\"'](?:PUT|PATCH)[\"']"
    r"|\bwbMapSetNodeStyle\((?![^;]*\brows\b)"
)
#: A loop's opening: its head is read by balance, not by `[^)]*`, so a head
#: holding a call (`of es.entries()`) still reaches the body (review 1101).
LOOP = re.compile(r"\b(?:for|while)\s*\(|\.(?:forEach|map|reduce)\(")

#: function name -> why a loop in it may write one item at a time.
ALLOWED = {
    "wbGrowShapeToLabel": "up to four rounds on one shape, each measured after the last",
    "wbMapRestoreRows": "creates topics; a child needs the id its parent was just given",
    "wbMapCopyBranch": "creates topics; a child needs the id its parent was just given",
    "wbMapRemoveKeepingBranchNow": "fallback for a server without move-many; one move per child",
    "wbSaveMapBulkMove": "the chunked move-many batch itself, and its per-object fallback",
    "wbSaveMany": "the batch itself; a topic still being created is saved the old way",
    "initWhiteboard": "wires one click handler per button; the write runs on the click",
    "wbRenderLinkEndpointHandles": "draws two handles; the write runs on the drag's end",
    "wbDrawSketchHandles": "draws the grips; the write runs on the drag's end",
    "drawLibraryBoardsGallery": "draws one card per board; the write runs on a menu choice",
}


def _braced(text: str, at: int) -> str:
    depth, end = 0, at
    while end < len(text):
        depth += {"{": 1, "}": -1}.get(text[end], 0)
        if depth == 0:
            break
        end += 1
    return text[at:end]


def _close(text: str, start: int) -> int:
    """The index just past the `)` that closes a `(` opened before `start`."""
    depth, end = 1, start
    while end < len(text) and depth:
        depth += {"(": 1, ")": -1}.get(text[end], 0)
        end += 1
    return end


def _body(text: str, start: int, is_for: bool) -> str:
    """The loop's body: its braces, its one statement, or `.map(`'s parentheses."""
    if is_for:
        start = _close(text, start)
        rest = text[start:].lstrip()
        at = len(text) - len(rest)
        return _braced(text, at) if rest.startswith("{") else text[at:text.find(";", at) + 1]
    depth, end = 1, start
    while end < len(text) and depth:
        depth += {"(": 1, ")": -1}.get(text[end], 0)
        end += 1
    return text[start:end]


def loops_that_write(text: str) -> set[str]:
    """Names of the functions holding a loop that calls a per-item write."""
    text = strip_js(text)
    names = [(m.start(), m.group(1)) for m in re.finditer(r"^(?:async\s+)?function\s+(\w+)", text, re.M)]
    found: set[str] = set()
    for m in LOOP.finditer(text):
        if WRITE.search(_body(text, m.end(), not m.group(0).startswith("."))):
            found.add(next((n for p, n in reversed(names) if p <= m.start()), "?"))
    return found


def board_loops() -> set[str]:
    found: set[str] = set()
    #: The Boards & maps gallery moved out of whiteboard.js to boards-gallery.js (INBOX 1772).
    for path in sorted([*JS.glob("whiteboard*.js"), JS / "boards-gallery.js"]):
        found |= loops_that_write(path.read_text(encoding="utf-8"))
    return found


def test_no_selection_loop_writes_one_item_at_a_time():
    stray = sorted(board_loops() - set(ALLOWED))
    assert not stray, (
        f"{stray}: a loop calls a per-item save. Mutate the items in the loop, push `{{ kind, item }}` "
        "rows, and save them once with `wbSaveMany(rows)` (or `wbCommitMoves(rows, undoEntries)`)."
    )


def test_allowed_loops_still_need_their_entry():
    stale = sorted(set(ALLOWED) - board_loops())
    assert not stale, f"{stale}: no longer write in a loop; take them out of ALLOWED."


def test_the_rule_sees_what_it_is_meant_to():
    bad = "async function wbX(items) {\n  for (const item of items) {\n    await wbSaveObject(item);\n  }\n}\n"
    assert loops_that_write(bad) == {"wbX"}
    mapped = "async function wbY(k) {\n  await Promise.all(k.map((o) => wbSaveObject(o)));\n}\n"
    assert loops_that_write(mapped) == {"wbY"}
    put = "async function wbZ(ids) {\n  for (const id of ids) await apiJson(`/a/${id}`, { method: \"PUT\" });\n}\n"
    assert loops_that_write(put) == {"wbZ"}
    style = "async function wbS(ns) {\n  for (const n of ns) {\n    await wbMapSetNodeStyle(n, { a: 1 });\n  }\n}\n"
    assert loops_that_write(style) == {"wbS"}
    good = (
        "async function wbG(items) {\n  const rows = [];\n  for (const item of items) {\n"
        "    await wbMapSetNodeStyle(item, { a: 1 }, { rows });\n    rows.push(item);\n  }\n  await wbSaveMany(rows);\n}\n"
    )
    assert loops_that_write(good) == set()
    headed = (
        "async function wbH(es) {\n  for (const [i, e] of es.entries()) {\n    e.item.x = i;\n"
        "    await wbSaveObject(e.item);\n  }\n}\n"
    )
    assert loops_that_write(headed) == {"wbH"}
    looped = "async function wbW(q) {\n  while (q.length) {\n    await wbSaveNode(q.pop());\n  }\n}\n"
    assert loops_that_write(looped) == {"wbW"}
    once = "async function wbO(item) {\n  await wbSaveObject(item);\n}\n"
    assert loops_that_write(once) == set()
