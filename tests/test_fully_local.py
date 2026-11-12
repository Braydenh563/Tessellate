"""The app asks no other host for anything (the owner, 2026-10-05: "make
sure it is fully local and doesnt use any external libraries that arent
vendored").

No CDN, no remote font, no analytics, no remote image: every script,
stylesheet and font is under `frontend/`, and the CSP (`core/security.py`)
names no host at all. This reads what is served (comments stripped, as
`api/asset_strip.py` serves it) for every `http(s)://` address and fails on
one that points anywhere but this machine, unless it is one of the kinds
below, which are text rather than requests:

- XML namespaces (`http://www.w3.org/2000/svg` and friends): an identifier,
  never fetched;
- a link the person follows on purpose (`<a href=... target="_blank">` in
  the page: the "Get it from ollama.com" link);
- an example in a field's placeholder, and the address a person types being
  normalised (`https://${raw}`).

The vendored libraries are read for a request built into them
(`fetch("http...`, `importScripts("http...`, a `src`/`loadPath` set to an
address). The one there is listed with why it never fires.

`scratchpad/ui-sweeps/fe1005-offline.js` is the browser half: it visits
every tab in a French locale and lists any request to another origin (none,
2026-10-05).
"""

from __future__ import annotations

import re
from pathlib import Path

from tessellate.api.asset_strip import strip_css, strip_html, strip_js
from tests._repo_files import repo_files

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
URL = re.compile(r"""https?://([^\s"'`)<>/:]+)[^\s"'`)<>]*""")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "[::1]"}
NAMESPACES = re.compile(r"https?://www\.w3\.org/(2000/svg|1999/xlink|1998/Math/MathML|1999/xhtml|XML/1998/namespace)")

#: (file, the address as written): text, not a request, and why.
ALLOWED = {
    # The link a person clicks to install Ollama; opens in their browser.
    ("index.html", "https://ollama.com"),
    # A bookmark's URL field: the example in its placeholder.
    ("library.js", "https://example.com"),
    # A typed address with no scheme, normalised before `new URL`.
    ("library.js", "https://${raw}"),
    # The same normalisation in `bookmarkKind`, moved to selection.js (572).
    ("selection.js", "https://${raw}"),
    # The same, for the duplicate finder's comparison key (library-links.js sameKey).
    ("library-links.js", "https://${raw}"),
}

#: Requests built into a vendored library, and why each never fires.
VENDOR_ALLOWED = {
    # p5's translations loader (i18next), used only by the Friendly Error
    # System, which the minified build leaves out; the CSP's connect-src
    # 'self' would refuse it anyway. fe1005-offline.js saw no request.
    # 1.11 writes the same loader with the minor version in the path
    # (`npm/p5@<major.minor>/translations/...`), so the address as matched
    # ends at the `@`; same loader, same reason, re-checked in Chromium on
    # 1.11.13 (no request left the page, scratchpad notes in pack-1011.md).
    ("p5.min.js", "https://cdn.jsdelivr.net/npm/p5@"),
}
VENDOR_REQUEST = re.compile(
    r"""(?:fetch\(|importScripts\(|\.src\s*=\s*|loadPath:\s*|url\(\s*)["'`](https?://[^"'`]+)"""
)


def _served(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".html":
        return strip_html(text)
    if path.suffix == ".css":
        return strip_css(text)
    return strip_js(text)


def _anchor_or_placeholder(line: str, start: int) -> bool:
    before = line[:start]
    return bool(re.search(r'(placeholder=|<a\s[^>]*href=)"$', before)) or 'target="_blank"' in line


def test_the_app_names_no_other_host():
    files = [FRONTEND / "index.html", FRONTEND / "sw.js"]
    files += sorted((FRONTEND / "css").glob("*.css")) + sorted((FRONTEND / "js").glob("*.js"))
    found = []
    for path in files:
        for number, line in enumerate(_served(path).split("\n"), 1):
            for match in URL.finditer(line):
                address = match.group(0)
                if match.group(1) in LOCAL_HOSTS or NAMESPACES.match(address):
                    continue
                if (path.name, address) in ALLOWED:
                    continue
                if path.suffix == ".html" and _anchor_or_placeholder(line, match.start()):
                    continue
                found.append(f"{path.name}:{number}: {address}")
    assert not found, (
        "an address on another host in what the app serves; vendor the thing it "
        f"names under frontend/vendor/ (with its licence), or link it for the person to open: {found}"
    )


def test_no_vendored_library_reaches_out():
    found = []
    for path in repo_files(FRONTEND / "vendor", suffixes=(".js",)) + repo_files(FRONTEND / "vendor", suffixes=(".mjs",)):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in VENDOR_REQUEST.finditer(text):
            address = match.group(1)
            host = re.match(r"https?://([^/:]+)", address).group(1)
            if host in LOCAL_HOSTS or (path.name, address) in VENDOR_ALLOWED:
                continue
            found.append(f"{path.relative_to(FRONTEND)}: {address}")
    assert not found, f"a vendored library fetches from another host: {found}"


def test_every_stylesheet_font_and_script_tag_is_local():
    html = strip_html((FRONTEND / "index.html").read_text(encoding="utf-8"))
    for tag in re.findall(r"<(?:script|link|img|iframe|source|video|audio)\b[^>]*>", html, re.I):
        for attr in re.findall(r'\s(?:src|href)="([^"]+)"', tag):
            assert not re.match(r"(https?:)?//", attr), f"not local: {tag}"
    for css in sorted((FRONTEND / "css").glob("*.css")):
        code = strip_css(css.read_text(encoding="utf-8"))
        for ref in re.findall(r"""url\(\s*["']?((?:https?:)?//[^"')]+)""", code):
            assert False, f"{css.name}: url({ref}) is not local"
        assert not re.search(r"@import\s+(url\()?\s*[\"']?(https?:)?//", code), css.name
