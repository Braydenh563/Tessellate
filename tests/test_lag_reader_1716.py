"""The web reader's Open and Copy link do not wait for the web bundle (INBOX 1716, `wiring.js BUTTON#web-reader-open.onclick 324ms`).

Measured at 4x CPU on a fresh page: the press waited for `web-clip.js` and `web-results.js` to arrive and parse, 151 to
206 ms from the press to the new tab, to run `window.open` and one clipboard write; with both in the main bundle, 1 to 8 ms.
A browser cannot run in pytest, so these are static.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"


def _handler(wiring: str, button_id: str) -> str:
    start = wiring.index(f'$("{button_id}").addEventListener("click"')
    return wiring[start : wiring.index("\n  });", start)]


def test_the_readers_open_and_copy_handlers_load_no_bundle() -> None:
    wiring = (JS / "wiring.js").read_text(encoding="utf-8")
    for button in ("web-reader-open", "web-reader-copy"):
        body = _handler(wiring, button)
        assert "ensureModule" not in body, button
        assert "await" not in body, button


def test_the_two_one_liners_live_in_the_main_bundle_only() -> None:
    wiring = (JS / "wiring.js").read_text(encoding="utf-8")
    results = (JS / "web-results.js").read_text(encoding="utf-8")
    assert re.search(r"^function openWebPageExternally\(url\) \{\n  window\.open\(safeHref\(url\), \"_blank\", \"noopener,noreferrer\"\);\n\}", wiring, re.M)
    assert re.search(r"^async function copyWebLink\(url, button\) \{", wiring, re.M)
    assert "function openWebPageExternally" not in results
    assert "function copyWebLink" not in results
    assert "openWebPageExternally, " not in results.split("Object.assign(window, {")[-1], "no second export of the moved function"
    # The bundle's result rows still call both, by name, from the shared global scope.
    assert "openWebPageExternally(result.url)" in results
    assert "copyWebLink(result.url)" in results
