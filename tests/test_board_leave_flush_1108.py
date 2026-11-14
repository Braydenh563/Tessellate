"""A box still being typed in is saved when the page goes (boardfix-1108).

The board saves a sticky, text box or topic on blur. A reload or a closed tab
does not blur, so words typed and left in an open editor never reached the
server (measured in Chromium: type, reload at once or after 1.5 s, the server
kept the old text and no write was sent). `pagehide` finishes the open edit and
the save goes out with `keepalive`, which lets the request outlive the page.
It is not `visibilitychange`: switching tabs must not end an edit in progress.
"""

from __future__ import annotations

import re

from tests._app_js import frontend_text

SRC = frontend_text("whiteboard.js")


def test_pagehide_finishes_the_open_edit() -> None:
    match = re.search(r'addEventListener\("pagehide",\s*\(\)\s*=>\s*\{(.*?)\n\}\);', SRC, re.S)
    assert match, "whiteboard.js has no pagehide listener"
    body = match.group(1)
    assert "wbCommitOpenEdit.leaving = true" in body
    assert "wbCommitOpenEdit()" in body


def test_the_leaving_save_is_keepalive() -> None:
    start = SRC.index("async function wbSaveObject(d)")
    block = SRC[start : start + 1200]
    assert "keepalive: wbCommitOpenEdit.leaving === true" in block


def test_tab_switch_does_not_end_an_edit() -> None:
    assert not re.search(r'visibilitychange[^\n]*\n[^\n]*wbCommitOpenEdit', SRC)
