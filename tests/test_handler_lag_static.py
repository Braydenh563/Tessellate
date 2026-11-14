"""Static shapes behind the boot long-task and handler-lag fixes (L-world-class-354, 355).

Measured in headless Chromium at 4x CPU by scratchpad/ui-sweeps/bootlongtasks.js and
handlerlag.js; these checks hold the shape so a later edit cannot quietly bring the cost back.
"""
import re
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def read(name):
    return (JS / name).read_text(encoding="utf-8")


def test_usage_ledger_wires_inside_onsurface():
    # A top-level $("id") for an id in an unbuilt surface builds the whole surface at boot (151-186 ms at 4x).
    src = read("usage-ledger.js")
    head = src.split('onSurface("settings"', 1)[0]
    assert not re.search(r"^\s*\$\(", head, re.M), "top-level $() before onSurface(settings)"


def test_meaning_text_is_memoized():
    src = read("meaning.js")
    assert re.search(r"meaningTexts\s*=\s*new Map\(\)", src)
    assert "meaningTexts.get(" in src and "meaningTexts.set(" in src


def test_settings_find_caches_row_text_and_warms_idle():
    src = read("settings-find.js")
    assert "row.said ??=" in src
    assert "function settingRowsWarm" in src and '"focus"' in src


def test_filter_settings_defers_pane_build():
    # Building the matched pane on the key that changes the first match was 100-190 ms of that key.
    src = read("settings.js")
    body = src.split("function filterSettings", 1)[1].split("\nfunction ", 1)[0]
    assert "setTimeout(function showFirstSettingsMatch" in body
    tail = body.split("showFirstSettingsMatch", 1)[0]
    assert "showSettingsSection(first)" not in tail
