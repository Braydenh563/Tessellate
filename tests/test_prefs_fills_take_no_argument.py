"""Every Settings fill reads the saved preferences from `prefsCache`.

`renderPrefs` calls each reader with no argument (`read()`). Two readers kept
an older `(p) => p.new_notes_private` shape from before the fills were split
per pane (L675), so opening Settings, Account threw "Cannot read properties of
undefined" and the private-by-default and mute switches never showed what was
saved (found by the shell measurement sweep, L-world-class-106)."""

from __future__ import annotations

import re

from tests._app_js import JS_DIR


def test_no_fill_reader_takes_a_parameter():
    source = (JS_DIR / "settings-prefs.js").read_text(encoding="utf-8")
    fills = source[source.index("const PREFS_FILLS = [") :]
    fills = fills[: fills.index("\n];")]
    rows = re.findall(r'^\s*\["([\w-]+)", "\w+", (\([^)]*\)) =>', fills, flags=re.M)
    assert len(rows) > 20, rows
    assert [name for name, params in rows if params != "()"] == []
