"""Settings, Appearance, Themes: the preview on hover waits, and an eye previews at once.

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


def test_hover_waits_long_enough_to_cross_the_grid():
    ms = int(re.search(r"const THEME_HOVER_PREVIEW_MS = (\d+);", CONTROLS).group(1))
    assert ms >= 400
    # The old literal must not be the timer any more.
    assert "name ? 120 : 0" not in CONTROLS


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
