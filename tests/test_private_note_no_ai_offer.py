"""A private note is never offered to Atlas (OPEN.md, sweep 1004 item 7).

`POST /entries/{id}/reevaluate` refuses a private note with a 400
(`test_reevaluate_private.py`), so the offers that reach it must not be drawn
for one: the note menu's "AI actions" group already carries that guard, and
the card's "Tag with Atlas" chip, which calls the same `reevaluateEntry`,
did not. It was a button whose only answer was a refusal toast.
"""

from __future__ import annotations

import re
from pathlib import Path

CARDS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "note-cards.js"
MENUS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "entry-menu.js"


def test_the_tag_with_atlas_chip_is_not_drawn_for_a_private_note() -> None:
    text = CARDS.read_text()
    at = text.index('chip("ph:sparkle Tag with Atlas"')
    # The `if (...)` that gates the chip is the statement just above it.
    gate = text[text.rindex("if (", 0, at) : at]
    assert "is_private" in gate, "a private note must not be offered to Atlas"


def test_every_caller_of_reevaluate_entry_is_gated_on_privacy() -> None:
    """The menu group and the chip are the only two ways in; a third must say so too."""
    callers = []
    for path in (Path(__file__).resolve().parents[1] / "frontend" / "js").glob("*.js"):
        if re.search(r"\breevaluateEntry\(entry\)", path.read_text()) and path.name not in ("lightbox.js", "lightbox-actions.js"):
            callers.append(path.name)
    assert sorted(callers) == ["entry-menu.js", "note-cards.js"], callers
    assert 'if (!entry.is_private) menu.appendChild(buildMenuGroupButton("ph:sparkle AI actions"' in MENUS.read_text()
