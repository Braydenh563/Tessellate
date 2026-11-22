"""Every relative link and anchor in the user-facing documents resolves.

The README, the root guides and the documents under `docs/` link to each
other and to the screenshots. Nothing checked those links: a renamed file or
heading left a link that read as plausible and went nowhere, and the one place
a first-time reader clicks (the README's table of documents) was the likeliest
to rot. `test_docs_layout.py` covers the roadmap's own cross-links and
`test_readme_freshness.py` the screenshots; this covers the rest.

What it checks, for each file below:

- a Markdown link or an HTML `src`/`href` that is not an address on the web
  points at a file or folder that exists, resolved from the file that holds it;
- a `#anchor` on a Markdown target names a heading that file really has,
  spelled the way GitHub spells its ids (lower case, punctuation dropped,
  spaces to hyphens, a repeated heading numbered);
- a `#anchor` on its own names a heading in the same file.

Code fences and inline code are skipped: a link shown as an example is not a
link. The mirrored copies under `docs/` (`CONTRIBUTING.md`, `SECURITY.md`,
`CHANGELOG.md`) are byte-identical to the root files, which
`test_docs_site.py` enforces, so only the originals are read here: their links
are written for the repository root.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "IDEAS.md",
    "docs/INSTALL.md",
    "docs/MODELS.md",
    "docs/PRIVACY.md",
    "docs/TROUBLESHOOTING.md",
    "docs/RELEASING.md",
    "docs/ARCHITECTURE.md",
    "docs/DESIGN.md",
    "docs/ROADMAP.md",
]

_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_MD_LINK = re.compile(r"(?<!\!)\[[^\]\n]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_MD_IMAGE = re.compile(r"!\[[^\]\n]*\]\(([^)\s]+)\)")
_HTML_REF = re.compile(r"""\b(?:src|href)=["']([^"']+)["']""")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)


def _prose_lines(text: str):
    """The lines outside code fences, with inline code blanked out."""
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield number, _INLINE_CODE.sub("", line)


def _slug(heading: str) -> str:
    """GitHub's heading id: markup stripped, lower case, punctuation dropped."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "").replace("*", "").strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


@lru_cache(maxsize=None)
def _anchors(path: Path) -> frozenset[str]:
    seen: dict[str, int] = {}
    found: set[str] = set()
    for _, line in _prose_lines(path.read_text(encoding="utf-8")):
        match = _HEADING.match(line)
        if not match:
            continue
        slug = _slug(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        found.add(slug if count == 0 else f"{slug}-{count}")
    return frozenset(found)


def _refs(path: Path):
    text = path.read_text(encoding="utf-8")
    for number, line in _prose_lines(text):
        for pattern in (_MD_LINK, _MD_IMAGE, _HTML_REF):
            for match in pattern.finditer(line):
                yield number, match.group(1)


@pytest.mark.parametrize("name", DOCS)
def test_every_relative_link_and_anchor_resolves(name: str) -> None:
    source = ROOT / name
    broken: list[str] = []
    for number, target in _refs(source):
        if _EXTERNAL.match(target):
            continue
        raw_path, _, anchor = target.partition("#")
        destination = (source.parent / raw_path).resolve() if raw_path else source
        if not destination.exists():
            broken.append(f"{name}:{number}: {target} (no such file or folder)")
            continue
        if anchor and destination.suffix == ".md":
            if anchor.lower() not in _anchors(destination):
                broken.append(f"{name}:{number}: {target} (no heading with that anchor)")
    assert not broken, "broken links:\n  " + "\n  ".join(broken)


def test_the_link_checker_sees_links() -> None:
    """A parser that finds nothing would pass every file above."""
    total = sum(1 for name in DOCS for _ in _refs(ROOT / name))
    assert total > 60, total
    assert _slug("Launcher script (Windows / macOS / Linux)") == "launcher-script-windows--macos--linux"
