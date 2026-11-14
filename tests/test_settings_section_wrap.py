"""settings-controls.js replaces `showSettingsSection` with a wrapper; the
helpers settings.js hangs on the original (`.loadCurrencyRates`) must be
copied over, or opening Search and index throws "is not a function" (touch.js
at 390, L606)."""

from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "frontend" / "js"


def test_wrapper_keeps_helpers_hung_on_the_original() -> None:
    controls = (JS / "settings-controls.js").read_text()
    assert "Object.assign(showSettingsSection, show);" in controls
    assert "showSettingsSection.loadCurrencyRates = loadCurrencyRates;" in (JS / "settings.js").read_text()
