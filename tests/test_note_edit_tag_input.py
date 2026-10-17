"""INBOX 904 B06: the edit form's add-tag input sits on its own line.

The owner: "the tag textbox just keeps getting shorter and shorter until it
eventually goes to a new line, I feel like it should just permanently be on the
line below with the tags being placed above". The input used to share the chip
row (`flex: 1 0 6rem`), so it took whatever the chips left. A full-width basis
makes it wrap onto a line of its own at every tag count; the browser check is
`scratchpad/ui-sweeps/notetaginput.js`.
"""

from __future__ import annotations

import re

from tests._css_paths import css_text


def _rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css_text())
    assert match, f"no rule for {selector}"
    return match.group(1)


def test_tag_input_takes_a_whole_line():
    body = _rule(".note-edit-meta .note-edit-tag-input")
    assert re.search(r"flex:\s*1 0 100%", body), "the input must wrap onto its own line"
    assert re.search(r"width:\s*100%", body)
