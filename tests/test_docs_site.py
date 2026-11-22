"""The GitHub Pages landing site is static, self-contained and cannot go stale.

History. The site used to fetch the repository's Markdown documents at run
time and render them in tabs. That failed in several shapes over its life
(no `.nojekyll`, so Pages converted the `.md` sources rather than publishing
them; cross-origin hosts that adblockers and rate limits refused), and the
owner's verdict was INBOX 645: "it for some reason struggles to load the
documents from the repo so I think we should remove them and just have a
solid landing site which doesn't really have a problem with having to be kept
up to date". So `docs/index.html` is now one static page: no fetch of any
kind, nothing loaded from another host, screenshots by relative path only,
and every document reached by an absolute GitHub link, which always shows the
current text. These tests hold each of those rules, plus the one that keeps
it from going stale: the copy names no version, no date and no count.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SITE = DOCS / "index.html"
REPO = "https://github.com/Braydenh563/Tessellate"

#: Root files once copied into /docs. The site links to the root ones on GitHub,
#: so the copies were retired (owner decision 2026-11-12, L787): a stale public
#: copy of SECURITY.md is worse than none.
RETIRED_COPIES = ("CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md")


class _Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.ids: set[str] = set()
        self.text: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self.tags.append((tag, a))
        if "id" in a:
            self.ids.add(a["id"])
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


def _parsed() -> _Collect:
    p = _Collect()
    p.feed(SITE.read_text(encoding="utf-8"))
    return p


def _scripts_and_styles() -> str:
    source = SITE.read_text(encoding="utf-8")
    # Case-insensitive and lenient about the closing tag (`</SCRIPT >`, even
    # `</script foo>`, which a browser also closes on), so an
    # upper-case or spaced tag cannot hide code from these checks (CodeQL).
    return "\n".join(re.findall(r"<(?:script|style)\b[^>]*>(.*?)</(?:script|style)\b[^>]*>", source, re.S | re.I))


def test_the_page_fetches_nothing():
    """The whole point of the rebuild: no request the page makes at run time
    can fail, because it makes none beyond its own screenshots."""
    code = _scripts_and_styles()
    for needle in ("fetch(", "XMLHttpRequest", "import(", "EventSource", "WebSocket", "sendBeacon"):
        assert needle not in code, f"docs/index.html calls {needle}; the landing page must not load anything at run time"


def test_nothing_is_loaded_from_another_host():
    """No CDN, no web font, no badge image: each was a request that could fail
    or track, and none is needed to read the page."""
    for tag, a in _parsed().tags:
        if tag == "script":
            assert "src" not in a, f"external script on the landing page: {a.get('src')}"
        if tag == "link" and a.get("rel") in ("stylesheet", "preconnect", "preload", "dns-prefetch"):
            raise AssertionError(f"<link rel={a['rel']}> on the landing page loads from elsewhere: {a.get('href')}")
        for attr in ("src", "srcset", "poster"):
            value = a.get(attr, "")
            assert not re.match(r"(https?:)?//", value), f"<{tag} {attr}> loads from another host: {value}"
    code = _scripts_and_styles()
    assert "@import" not in code
    assert not re.search(r"url\(\s*['\"]?(https?:)?//", code), "a CSS url() reaches another host"


def test_every_image_is_a_screenshot_that_exists_and_says_what_it_shows():
    images = [a for tag, a in _parsed().tags if tag == "img" and a.get("src")]
    assert len(images) >= 12, "the feature tour should show the screenshots"
    for a in images:
        src = a["src"]
        assert src.startswith("screenshots/"), f"image outside docs/screenshots/: {src}"
        assert (DOCS / src).is_file(), f"docs/index.html shows {src}, which does not exist"
        assert len(a.get("alt", "")) >= 20, f"{src} needs alt text that describes what it shows"


def test_every_link_is_absolute_or_on_this_page():
    """Relative links to repo files 404 on Pages (only /docs is published);
    an absolute GitHub link always shows the current file."""
    p = _parsed()
    hrefs = [a["href"] for tag, a in p.tags if tag == "a" and "href" in a]
    assert hrefs
    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in p.ids, f"in-page link {href} has no target"
        elif href.startswith("screenshots/"):
            assert (DOCS / href).is_file(), f"link to a missing screenshot: {href}"
        else:
            assert href.startswith("https://github.com/Braydenh563"), f"unexpected link: {href}"


@pytest.mark.parametrize(
    "target",
    [
        "/releases/latest", "/releases", "/issues", "/blob/main/CHANGELOG.md",
        "/blob/main/docs/PRIVACY.md", "/blob/main/SECURITY.md", "/blob/main/CONTRIBUTING.md",
        "/blob/main/LICENSE", "/blob/main/docs/INSTALL.md", "/blob/main/docs/MODELS.md",
    ],
)
def test_the_key_links_are_there(target):
    assert f'href="{REPO}{target}' in SITE.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ["SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE",
                                  "docs/PRIVACY.md", "docs/INSTALL.md", "docs/MODELS.md",
                                  "docs/TROUBLESHOOTING.md", "docs/ARCHITECTURE.md"])
def test_every_linked_repo_file_exists(path):
    """A file renamed in the repo would turn its link on the site into a 404."""
    source = SITE.read_text(encoding="utf-8")
    if f"/blob/main/{path}" in source:
        assert (ROOT / path).is_file(), f"the site links to {path}, which is gone"


def test_the_copy_names_no_version_date_or_count():
    """A version, a date or a count in the copy is a line someone must
    remember to update; the owner asked for a page that does not need it."""
    text = " ".join(_parsed().text)
    text = text.replace("AGPL-3.0", "")
    assert not re.search(r"\bv?\d+\.\d+(\.\d+)?\b", text), "a version number in the landing page copy"
    assert not re.search(r"\b(19|20)\d\d\b", text), "a year in the landing page copy"
    hit = re.search(r"\b\d[\d,]*\+?\s+(tools|skills|themes|icons|tests|features|languages)\b", text, re.I)
    assert not hit, f"a count in the landing page copy: {hit.group(0) if hit else ''}"


def test_landmarks_and_skip_link():
    p = _parsed()
    tags = [t for t, _ in p.tags]
    for landmark in ("header", "main", "footer", "nav"):
        assert landmark in tags, f"missing <{landmark}>"
    skip = [a for t, a in p.tags if t == "a" and "skip" in a.get("class", "")]
    assert skip and skip[0]["href"] == "#main" and "main" in p.ids


def test_light_and_dark_follow_the_system():
    css = _scripts_and_styles()
    assert "prefers-color-scheme: dark" in css
    assert ':root[data-theme="dark"]' in css and ':root:not([data-theme="light"])' in css


def test_jekyll_is_switched_off():
    """Kept: without it Pages runs Jekyll over /docs, which would read any
    `{{ }}` in these files as Liquid and convert their Markdown."""
    assert (DOCS / ".nojekyll").exists()


@pytest.mark.parametrize("name", RETIRED_COPIES)
def test_the_root_docs_have_no_copy_under_docs(name):
    assert (ROOT / name).is_file(), name
    assert not (DOCS / name).exists(), f"docs/{name} is back; the site links to the root {name}"
