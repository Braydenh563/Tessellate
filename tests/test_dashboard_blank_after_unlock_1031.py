"""The Dashboard drew blank after unlock when the notebook's saved tab was not
the Dashboard (blind test 1031, friction 2, 5 of about 9 logins).

Every load opens on the Dashboard (`revealTab("dashboard")`, phone-shell.js),
and `looksReady` then restores the mirrored `activeTab` from the server, so the
stored tab said "notes" while the screen showed the Dashboard. The boot's data
load (`refreshActiveTab`) read the stored name and drew Notes under a Dashboard
that nothing drew: no statistics, no sample-notebook call, no cards.
Reproduced with a second browser context logging in after a session that ended
on Notes: 2 of 3 logins blank before, 0 of 10 after."""
import re

from tests._app_js import app_js_text


def _refresh_active_tab() -> str:
    js = app_js_text()
    start = js.index("async function refreshActiveTab()")
    return js[start : js.index("\n}\n", start)]


def test_the_boot_loads_the_tab_that_is_on_screen_not_the_stored_name():
    body = _refresh_active_tab()
    assert 'localStorage.getItem("activeTab")' not in body
    assert "document.body.dataset.tab" in body


def test_the_stored_tab_is_pinned_to_the_one_shown():
    # Other readers (`prefs.get("activeTab")`) must agree with the screen.
    body = _refresh_active_tab()
    assert re.search(r'prefs\.set\("activeTab", name\)', body)
