"""The companion's band sits under `<html>`, not `<body>` (INBOX 1726, 1716).

A browser cannot run in pytest, so these are static. Every node the companion adds or removes under `<body>`
(a swapped figure, a speech bubble, an emote) re-asks each `:has()` subject of the page; on the Library Images
tab (240 tiles, about 30,000 nodes, 4x CPU) one inserted span cost 124 to 213ms with the page's 422 `:has()`
rules and 1 to 9ms without them. Under `<html>` the same insertion costs nothing, so the poke's forced reads
(`nameMarkBuddyBlend`: 130 to 700ms each after the figure swap) fell to 13 to 35ms.

The band was body's child only for what it inherited from body (text and colour) and for being hidden when a
document is printed (`body.printing-doc > *`), so those two are written down where it now stands.
"""

from __future__ import annotations

import re

from pathlib import Path
from tests._js_scope import unwrapped
from tests._css_paths import FORMER_08, sheets

ROOT = Path(__file__).resolve().parents[1]
AV = unwrapped((ROOT / "frontend" / "js" / "avatars.js").read_text(encoding="utf-8"))
CSS08 = sheets(*FORMER_08)
CSS05 = (ROOT / "frontend" / "css" / "05-sidebars-themes.css").read_text(encoding="utf-8")
CSS00 = (ROOT / "frontend" / "css" / "00-tokens-shell.css").read_text(encoding="utf-8")


def _build() -> str:
    start = AV.index("function nameMarkBuddyBuild(")
    return AV[start : AV.index("\n}\n", start) + 2]


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_the_band_is_appended_under_html() -> None:
    build = _build()
    assert "document.documentElement.appendChild(band)" in build
    assert "document.body.appendChild(band)" not in build


def test_the_band_states_what_it_no_longer_inherits_from_body() -> None:
    body = _rule(CSS00, "body")
    band = _rule(CSS08, "#nm-buddy-band")
    for prop in ("font-family", "color", "font-size", "line-height"):
        assert f"{prop}:" in body and f"{prop}:" in band, f"{prop} is body's, so the band says it"
    assert re.search(r"font-size: var\(--text-lg\)", band) and re.search(r"line-height: 1\.5", band)


def test_a_printed_document_still_hides_the_band() -> None:
    assert "body.printing-doc ~ #nm-buddy-band" in CSS05
