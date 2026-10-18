"""Settings, Appearance, Themes: an eye previews a theme, held under Apply and Cancel.

Owner, 2026-10-17 (INBOX 904 B58): "I want the hover time to preview themes to
be slightly longer or add like a small eye icon button in the corner to
preview." Both are done. The delay is a named constant so the structural cause
(a 120 ms timer repainting the whole app while the pointer crossed the grid)
cannot creep back; the eye lives in the lazy Settings bundle, because boot JS
and CSS are at their caps (`tests/test_boot_budget.py`).
"""

from __future__ import annotations

import re

from tests._css_paths import CSS_DIR
from tests._app_js import APP_JS, JS_DIR

CONTROLS = (JS_DIR / "settings-controls.js").read_text(encoding="utf-8")


def test_no_hover_preview_where_eyes_exist():
    # INBOX 1300 C21: the eye replaced the hover preview (B58's 450 ms timer).
    assert "THEME_HOVER_PREVIEW_MS" not in CONTROLS
    body = CONTROLS.split("function themeEyeButton", 1)[1].split("\nfunction ", 1)[0]
    assert "pointerenter" not in body and '"focus"' not in body
    assert "pointerover" not in CONTROLS.split("function previewTheme", 1)[1].split('$("theme-surprise")', 1)[0]


def test_a_held_preview_has_apply_and_cancel_and_ends_on_the_ways_out():
    tail = CONTROLS.split("function previewTheme", 1)[1].split('$("theme-surprise")', 1)[0]
    assert "Previewing the ${label} theme." in tail
    assert 'textContent = "Apply"' in tail and 'textContent = "Cancel"' in tail
    # Never stamped, so the toast stack does not fold it away.
    assert "toastMark" not in tail
    for way_out in ("closeSettingsModal = function", "showSettingsSection = function", '"visibilitychange"'):
        assert way_out in tail, way_out
    assert "name !== currentSettingsSection" in tail


def test_each_card_gets_an_eye_that_previews_at_once():
    assert 'className = "theme-eye' in CONTROLS
    assert "ph-eye" in CONTROLS
    assert "Preview the " in CONTROLS
    # A held preview is a toggle, so it says so with aria-pressed (never the icon alone).
    assert "aria-pressed" in CONTROLS.split("function themeEyeButton", 1)[1]


def test_the_eye_styles_ship_with_the_settings_bundle():
    sheet = (CSS_DIR / "settings-controls-lazy.css").read_text(encoding="utf-8")
    assert ".theme-eye" in sheet and ".theme-card-cell" in sheet
    app = APP_JS.read_text(encoding="utf-8")
    assert re.search(r"settingsControls: \[[^\]]*settings-controls-lazy\.css", app)
