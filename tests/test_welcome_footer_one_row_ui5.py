"""Source text: L-ui-modernisation-5, "Keep the welcome footer buttons on one
row at 390 px" (scratchpad/first-run-472.md row 13: "Skip the tour, Back and
Start the tour wrap to two rows, Skip alone on the first"). The CSS and the
load are read here; what was measured in the app is in the ledger row."""
import re
from pathlib import Path

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]


def test_phone_welcome_overlay_has_narrow_sides():
    css = (ROOT / "frontend/css/first-run-lazy.css").read_text(encoding="utf-8")
    block = re.search(r"@media \(max-width: 599\.98px\) \{\s*#onboarding-overlay \{([^}]*)\}", css)
    assert block and "padding-inline: var(--space-2)" in block.group(1)


def test_welcome_fetches_that_stylesheet():
    body = frontend_text("onboarding.js").split("function showOnboarding() {", 1)[1].split("\n}\n", 1)[0]
    assert 'lazyScript("/css/first-run-lazy.css")' in body
