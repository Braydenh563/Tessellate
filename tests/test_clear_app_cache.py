"""Settings, Data, Clear app cache (INBOX 487): the wiring the suite cannot see.

The server half is in tests/test_static_precompressed.py. This holds the
frontend half: one button in Settings, Data, one handler that forgets the
service worker, Cache Storage and the server's copies, and the two things the
Playwright check found (the emblem waits for the page's scripts, and the
existing Reload button clears the same things).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
#: The helpers stay in phone-shell.js; the button's own listener moved to
#: settings-controls.js with every other listener inside the Settings window
#: (2026-10-05, the boot gzip budget), so the two are read as one text.
SHELL = (ROOT / "frontend" / "js" / "phone-shell.js").read_text(encoding="utf-8") + "\n" + (
    ROOT / "frontend" / "js" / "settings-controls.js"
).read_text(encoding="utf-8")
JS = ROOT / "frontend" / "js"
DATA = (JS / "settings-data.js").read_text(encoding="utf-8")
SETTINGS = (JS / "settings.js").read_text(encoding="utf-8")


def _function(name: str) -> str:
    start = SHELL.index(f"async function {name}(")
    return SHELL[start : SHELL.index("\n}\n", start)]


def test_the_button_is_in_settings_data_and_has_one_handler():
    data = INDEX[INDEX.index('id="settings-data"') : INDEX.index('id="settings-account"')]
    assert data.count('id="clear-app-cache"') == 1
    assert INDEX.count('id="clear-app-cache"') == 1
    assert SHELL.count('$("clear-app-cache")') == 1
    assert 'data-help-for="app-cache-help"' in data and 'id="app-cache-help"' in data


def test_clearing_forgets_all_three_and_the_reload_button_shares_it():
    body = _function("clearAppCache")
    assert "getRegistrations" in body and "unregister" in body
    assert "caches.keys" in body or "caches?.keys" in body
    assert 'apiJson("/system/clear-static-cache", { method: "POST" })' in body
    assert "clearAppCache()" in _function("forceReloadApp")


def test_the_click_says_so_then_reloads():
    handler = SHELL[SHELL.index('$("clear-app-cache")') :]
    handler = handler[: handler.index("});")]
    assert "App cache cleared. Reloading." in handler
    assert re.search(r"setTimeout\(\(\) => location\.reload\(\), \d+\)", handler)


def test_the_emblem_does_not_load_p5_before_the_scripts_have_run():
    #: p5's loader moved to dash-art.js with its one use (INBOX 1530 d).
    art = (ROOT / "frontend" / "js" / "dash-art.js").read_text(encoding="utf-8")
    start = art.index("function ensureP5()")
    body = art[start : art.index("\n  }\n", start)]
    assert 'document.readyState === "complete"' in body
    assert '"load"' in body


# Settings, Data, "Clear and forget" (Brief 86 b): four rows, each saying what
# it removes and how much, each undoable from its toast. The counts and clears
# are driven in a real page by scratchpad/ui-sweeps/settingsclear86.js; the
# server half is tests/test_suggestions_inbox_kg9.py.
ROWS = {
    "clear-recents": "clear-recents-what",
    "clear-previews": "clear-previews-what",
    "clear-guide": "clear-guide-what",
    "clear-dismissed": "clear-dismissed-what",
}


def test_each_clear_names_its_button_and_the_line_that_says_how_much() -> None:
    for button, line in ROWS.items():
        assert f'id="{button}"' in INDEX and f'id="{line}"' in INDEX, button
        assert f'$("{button}")' in DATA and f'"{line}"' in DATA, f"{button} is not wired or painted"
    assert 'id="clear-help"' in INDEX and 'data-help-for="clear-help"' in INDEX, "help is data-help-for"


def test_the_counts_are_painted_when_the_data_pane_opens() -> None:
    assert re.search(r'name === "data"[\s\S]{0,500}ensureModule\("settingsData"\)\.then\(\(\) => \{\s*renderSettingsClear\(\);', SETTINGS)


def test_a_clear_that_removes_something_offers_the_way_back_for_ten_seconds() -> None:
    assert "offerUndo(" in DATA and "ms: 10000" in DATA
    assert "settingsHistoryAdd(change)" in DATA, "a clear is kept in Recent changes too"
    assert DATA.count("settingsClearDone(") >= 4, "recents, guide and dismissed go through the one shape (previews say why not)"
    # The previews are not a stored thing: the row says there is nothing to undo.
    assert "there is nothing to undo" in DATA


def test_no_row_is_a_button_that_does_nothing_when_nothing_is_there() -> None:
    assert "button.disabled = count === 0" in DATA
