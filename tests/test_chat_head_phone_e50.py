"""Audit 1028 E50: on a phone the chat title gets the header row.

Four icons beside the title left it 94px and clipped to "what do I know ab...".
Fork and Compress already have rows in the header's menu (they click the
visible buttons, so the disabled state and handlers stay in one place), so
below the phone breakpoint the two buttons leave the row and the menu is the
way to them. The rest of the audit row was done before this: the no-model line
is a two-row grid with a close (94px, was about 190) and the sources are one
collapsed line that opens a sheet of one-line rows (measured 55px each, was
115px cards)."""

from __future__ import annotations

import re

from tests._app_js import FRONTEND_DIR, frontend_text


def _phone_block(css: str) -> str:
    start = css.index(".chat-tool-group-end {\n  margin-left: auto;\n}")
    block = css[start:]
    return block[block.index("@media (max-width: 599.98px)") :][:1200]


def test_fork_and_compress_leave_the_row_on_a_phone():
    css = (FRONTEND_DIR / "css" / "06-timeline-dialogs.css").read_text(encoding="utf-8")
    block = _phone_block(css)
    rule = re.search(r"#chat-fork,\s*#chat-compress \{([^}]*)\}", block)
    assert rule, block
    assert "display: none" in rule.group(1)


def test_the_menu_still_reaches_both_actions():
    js = frontend_text("chat.js")
    assert 'run: click("chat-fork")' in js
    assert 'run: click("chat-compress")' in js
