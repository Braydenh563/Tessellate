"""Rule 1.8, one undo contract (WORLD_CLASS 1.8, decision 53, Brief 51 step 5).

A destructive act that reaches the server shows the undo bar through
`pushUndo` (status.js), with the toast's Undo being the same entry
(`offerUndo`); Ctrl+Z inside an editor or a board is that surface's own
history. Nothing else invents an undo. This fails on a function whose name
says undo, outside status.js, the stack's store, the editors' histories and
the board history module, unless it goes through the contract. `UNFOLDED` is
the ratchet: it may only shrink.
"""

from __future__ import annotations

import re
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

DECL = re.compile(r"^(?:async\s+)?function\s+([A-Za-z0-9_$]*[Uu]ndo[A-Za-z0-9_$]*)\s*\(", re.M)
NEXT = re.compile(r"^(?:async\s+)?function\s", re.M)
CONTRACT = re.compile(r"\b(pushUndo|offerUndo|settleUndoFromToast|performUndo)\(")

#: Whole files that are the contract or a surface's own history.
OWNERS = {
    "status.js",  # pushUndo, the bar, the history menu
    "undo-store.js",  # the stack's store across a reload
    "whiteboard.js",  # the board's own history (wbUndo and its stack)
    "whiteboard-history.js",
    "settings-data.js",  # Settings' own Recent changes list with Undo and Redo (Brief 86)
}
#: Names that are an editor's own history inside a larger file: a document's undo stack, and
#: autocorrect putting back the word just typed (the text box's own Ctrl+Z, not a notebook change).
EDITOR_HISTORY = re.compile(r"^(docUndo|autocorrectUndo)")

#: Starting list 2026-10-10 (Brief 51), each with why it is not folded yet.
#: Remove a name when it goes through the contract; never add one.
UNFOLDED: dict[str, str] = {
    "chat-agent.js:updateDraftUndoButton": "paints that button",
    "dashboard.js:activityUndoPlanText": "words for the activity undo's confirm",
    "dashboard.js:activityUndoStarts": "finds where that undo starts",
    "dashboard.js:activityUndoControl": "draws that undo's button",
}


def _undo_functions():
    for path in sorted(JS.glob("*.js")):
        if path.name in OWNERS:
            continue
        text = path.read_text(encoding="utf-8")
        for match in DECL.finditer(text):
            name = match.group(1)
            if EDITOR_HISTORY.match(name):
                continue
            rest = text[match.end():]
            following = NEXT.search(rest)
            body = rest[: following.start() if following else len(rest)]
            yield f"{path.name}:{name}", bool(CONTRACT.search(body))


def test_every_undo_goes_through_the_one_contract():
    outside = sorted(key for key, through in _undo_functions() if not through and key not in UNFOLDED)
    assert not outside, (
        "a function named for an undo that does not go through pushUndo or offerUndo "
        "(status.js, rule 1.8); fold it in, or if it is an editor's own history, say so here: "
        + ", ".join(outside)
    )


def test_the_ratchet_only_shrinks():
    seen = dict(_undo_functions())
    stale = sorted(key for key in UNFOLDED if key not in seen or seen[key])
    assert not stale, f"folded or gone, take it off UNFOLDED: {stale}"
    assert len(UNFOLDED) <= 7


def test_putting_a_version_back_is_one_undo_not_a_confirm():
    text = (JS / "note-history.js").read_text(encoding="utf-8")
    start = text.index("const restoreTo = async")
    block = text[start: text.index("\n  };\n", start)]
    assert "pushUndo(" in block and "confirmDialog" not in block
