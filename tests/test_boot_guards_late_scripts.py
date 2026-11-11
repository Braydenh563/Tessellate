"""A name defined by a later classic script can be read before that script
runs: `startApp()` resumes when `/auth/status` answers, which can land between
two scripts (app.js `whenScriptsLoaded`). These guards are load-bearing, not
byte waste (a gzip trim removed them and boot threw; see commit 88bfe5341)."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"

GUARDS = {
    "shell-reminders.js": 'typeof sizeDashWidgets === "function"',  # a resize before dashboard.js ran (a real log)
    "markdown.js": 'typeof calloutKindOf === "function"',  # cards render callouts before editor.js ran
    "navigation.js": 'typeof settingsScroller !== "function"',  # settings.js is the last script
    "status.js": 'typeof GUIDE_NAME === "string"',
    "settings-panes.js": 'typeof TAB_JUMP_KEYS !== "undefined"',
}


def test_late_script_names_stay_guarded():
    missing = [f"{f}: {g}" for f, g in GUARDS.items() if g not in (JS / f).read_text(encoding="utf-8")]
    assert not missing, missing


def test_callout_kinds_const_is_guarded_against_its_dead_zone():
    assert 'typeof CALLOUT_KINDS !== "undefined"' in (JS / "markdown.js").read_text(encoding="utf-8")
