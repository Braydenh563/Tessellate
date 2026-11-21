"""First run asks once where to keep a second copy of the backups (WORLD_CLASS_PLAN 22.1 item 8, LEDGER L-world-class-101).

Backups existed and so did the second-folder setting (`backup_copy_dir`, Settings,
Data), but nothing told a new person either was there. The desktop app now asks
once, in the first-run queue after the welcome and the console-view question,
and saves the answer through the same preference the Settings row writes.
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text, frontend_text

ROOT = Path(__file__).resolve().parents[1]


def _function(source: str, name: str) -> str:
    start = source.index(f"async function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_the_question_takes_its_turn_after_the_console_one_and_before_updates() -> None:
    onboarding = frontend_text("onboarding.js")
    order = onboarding[onboarding.index("const FIRST_RUN_ORDER") :].split("\n")[0]
    assert '"console", "backup", "updates"' in order


def test_it_asks_once_on_the_desktop_and_only_when_no_folder_is_set() -> None:
    body = _function(frontend_text("onboarding.js"), "maybeShowConsoleViewIntro")
    assert "desktopShell()" in body
    assert "prefsCache.backup_copy_dir" in body
    assert 'prefs.get("backupFolderAsked"' in body and 'prefs.set("backupFolderAsked"' in body
    assert 'firstRunTurn(' in body and '"backup"' in body


def test_the_answer_goes_through_the_setting_the_settings_row_writes() -> None:
    body = _function(frontend_text("onboarding.js"), "maybeShowConsoleViewIntro")
    assert "/preferences" in body and "backup_copy_dir" in body
    assert "promptDialog(" in body and "confirmDialog(" in body
    # A refusal says why and where else to set it.
    assert "error.message" in body and "Settings" in body


def test_it_rides_the_console_question_start_so_it_adds_no_global_name() -> None:
    """The global-names ratchet is at its cap, so the question lives in the
    console intro's function and that function's start line also asks when no folder is set."""
    body = _function(frontend_text("onboarding.js"), "maybeShowConsoleViewIntro")
    assert body.index('"console"') < body.index('"backup"')
    assert "maybeShowConsoleViewIntro()" in app_js_text()


def test_help_says_so_where_it_describes_the_setting() -> None:
    page = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    topics = (ROOT / "src" / "tessellate" / "ai" / "help_topics_more.py").read_text(encoding="utf-8")
    assert "asks once" in page[page.index('"Also copy each backup to" sends') :][:900]
    assert "asks once" in topics[topics.index("Also copy each backup to sends") :][:500]
