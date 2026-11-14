"""L304, its second part: the Source view's Wrap toggle is reachable in the Source view.

The dock and its ... menu are hidden in Source (`.dgm-dialog[data-view="source"] .dgm-dock`), so the
menu's Wrap row could not be reached where it matters. A Wrap toggle sits beside the view buttons, shown
only in Source, pressed while lines fold, sharing `setWrap` with the menu row.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMBED = (ROOT / "frontend" / "js" / "diagram-embed.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "diagram-lazy.css").read_text(encoding="utf-8")


def test_a_wrap_toggle_shares_set_wrap_and_says_pressed():
    assert 'wrapBtn.classList.add("dgm-wrapbtn")' in EMBED
    assert 'setWrap(field.getAttribute("wrap") === "off"));' in EMBED
    assert 'wrapBtn?.setAttribute("aria-pressed", String(on))' in EMBED
    assert "note.after(wrapBtn)" in EMBED


def test_the_toggle_shows_only_in_source():
    hidden = re.search(r"\.dgm-wrapbtn \{([^}]*)\}", CSS)
    shown = re.search(r'\.dgm-dialog\[data-view="source"\] \.dgm-wrapbtn \{([^}]*)\}', CSS)
    assert hidden and "display: none" in hidden.group(1)
    assert shown and "display: inline-flex" in shown.group(1)


def test_the_guide_names_the_button():
    from tessellate.ai.help_chat import HELP_TOPICS

    body = str(next(t["body"] for t in HELP_TOPICS if t["id"] == "diagram-lines"))
    assert "Wrap button beside Source" in body
