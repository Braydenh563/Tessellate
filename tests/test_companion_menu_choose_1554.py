"""The companion menu's choices work before Settings has opened (INBOX 1554).

The owner: "I cant change atlas to feminine". The menu's Atlas look,
Companion and the rest set their Appearance control and fire its change; the
Settings body is built on demand and its listeners load with the first open,
so before that the choice found no select (or one nothing listened to) and
did nothing. `scratchpad/ui-sweeps/atlaslook1554.js` measured it: pref "auto"
before the fix, "feminine" after.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def _choose() -> str:
    js = app_js_text()
    at = js.index("const choose = async (id, value) =>")
    return js[at : js.index("};", at)]


def test_choose_builds_the_body_and_waits_for_the_listeners():
    body = _choose()
    assert re.search(r"const select = \$\(id\);", body), "`$` builds the Settings body; getElementById does not"
    assert body.index('await ensureModule("settingsControls")') < body.index("dispatchEvent")
