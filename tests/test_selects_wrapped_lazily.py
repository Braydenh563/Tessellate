"""Settings' selects are wrapped as their pane is shown, not at boot
(WORLD_CLASS_PLAN 19: the boot pass wrapped 99 selects, about 50 ms, most in
panes nobody opened; L-world-class-14)."""
from __future__ import annotations

from pathlib import Path

from tests._app_js import app_js_text

SETTINGS = (Path(__file__).resolve().parents[1] / "frontend/js/settings.js").read_text(encoding="utf-8")


def _body(js: str, head: str) -> str:
    start = js.index(head)
    return js[start : js.index("\n}\n", start)]


def test_the_boot_pass_leaves_the_settings_window_alone():
    body = _body(app_js_text(), "function watchForSelects()")
    assert 'if (!select.closest("#settings-modal")) enhanceSelect(select);' in body
    assert "enhanceAllSelects(document);" not in body


def test_a_pane_wraps_its_selects_when_shown_and_the_window_its_own_on_open():
    js = SETTINGS
    assert "enhanceAllSelects($(`settings-${name}`));" in _body(js, "function showSettingsSection(")
    opening = _body(js, "async function openSettingsModal(")
    assert 'if (!select.closest(".settings-section")) enhanceSelect(select);' in opening
    assert opening.index('classList.remove("hidden")') < opening.index("showSettingsSection(section)")
