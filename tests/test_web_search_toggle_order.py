"""The chat's Web toggle is drawn by a function the boot can reach before
wiring.js loads (the companion session, 2026-11-12, driven in a browser:
`ReferenceError: renderWebSearchToggle is not defined` on every load).

`onSurface("chat", ...)` in status.js runs `syncModelGatedControls`, which
calls `renderChatModeSeg` and then `renderWebSearchToggle`. A classic script
calls only upwards at load (CLAUDE.md section 7), so the function lives in
status.js, above its first caller, not in a later file.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

STATUS = (JS_DIR / "status.js").read_text(encoding="utf-8")


def test_the_toggle_is_defined_where_the_boot_first_calls_it():
    defined = [p.name for p in JS_DIR.glob("*.js") if re.search(r"^function renderWebSearchToggle\(", p.read_text(encoding="utf-8"), re.M)]
    assert defined == ["status.js"], defined


def test_it_is_defined_above_the_chat_mode_strip_that_calls_it():
    assert STATUS.index("function renderWebSearchToggle(") < STATUS.index("function renderChatModeSeg(")
