"""Q34, WORLD_CLASS rows 35 to 37: the studio, the natural voice and the folder sync are reachable and honest in the page.

Source-level: what drives them in a browser is `scratchpad/ui-sweeps` (real Piper and Playwright were run once, see the plan's Decisions line).
"""

from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"


def _js(name: str) -> str:
    return (FRONTEND / "js" / name).read_text(encoding="utf-8")


def test_read_aloud_takes_the_natural_voice_before_the_browsers_check():
    media = _js("media.js")
    natural = media.index('prefs.get("read-aloud-voice", "browser") === "natural"')
    assert natural < media.index('"speechSynthesis" in window'), "a browser with no voices can still hear the natural one"
    assert "speakNatural(text, button, handle)" in media and "return handle;" in media


def test_both_sheets_are_lazy_with_stand_ins_and_a_way_in():
    entries = _js("lazy-entries.js")
    assert 'studio: ["/js/studio.js"]' in entries and 'syncFolder: ["/js/sync-folder.js"]' in entries
    assert 'studio: ["openStudio", "speakNatural"]' in entries and 'syncFolder: ["openFolderSync"]' in entries
    features = _js("app-features.js")
    # The folder's sheet is one of two ways in under Settings' Sync between computers (WORLD_CLASS_PLAN B6
    # decision 14): the palette and feature rows open that group, and its button opens the sheet.
    assert 'reveal: "studio"' in features and 'reveal: "sync-group"' in features
    targets = _js("reveal-targets.js")
    assert "openStudio()" in targets and '"sync-group": { settings: "data", el: "sync-group" }' in targets
    assert '$("sync-folder-open")?.addEventListener("click", () => openFolderSync());' in _js("settings-rows.js")
    text = app_js_text()
    assert "function openStudio()" in text and "async function openFolderSync()" in text


def test_the_settings_voice_choice_names_the_way_to_the_package_when_it_is_missing():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-read-aloud-voice"' in html and 'value="natural"' in html
    controls = _js("settings-controls.js")
    assert "speak?.available" in controls and "Open Packages" in controls


def test_the_studio_sheet_can_be_stopped_and_the_sync_sheet_never_keeps_the_passphrase():
    studio = _js("studio.js")
    assert "/studio/runs/${id}/stop" in studio and "Nothing was kept." in studio
    sync = _js("sync-folder.js")
    #: The field is a password field declared in index.html (a script may not build one, test_lock_boundary.py).
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert '"sync-folder-passphrase"' in sync and '<template id="sync-folder-passphrase">' in html
    assert "localStorage" not in sync and "prefs.set" not in sync
    assert "style." not in studio and "style." not in sync
