"""The lock field's own show-password button (the owner, 2026-10-06: the eye
"disappeard permanently" after clicking off the field, and the typed text sat
off centre). Edge's native `::-ms-reveal` is hidden; the app's toggle stays,
and the field is padded equally on both sides. Measured in Chromium: padding
38.4px each side, the button 9px from the field's top and bottom."""

from __future__ import annotations

from pathlib import Path
from tests._app_js import index_html_text

HTML = index_html_text()
CSS = Path("frontend/css/01-forms-settings.css").read_text(encoding="utf-8")
JS = Path("frontend/js/settings-wiring.js").read_text(encoding="utf-8")


def test_the_lock_field_has_its_own_reveal_and_hides_the_browsers() -> None:
    assert 'id="lock-password-show"' in HTML
    assert "input::-ms-reveal" in CSS and "display: none;" in CSS
    assert 'padding-inline: calc(var(--control-h) + var(--space-2));' in CSS
    assert '$("lock-password-show").addEventListener("click"' in JS
