"""CSS class names nothing uses may not grow (WORLD_CLASS_PLAN 5.4; UI_MODERNISATION_PLAN 13b).

A class in a selector that appears as a whole token nowhere in index.html,
frontend/js or src/ is dead weight, and a pile of them is how a stylesheet
reaches 73,000 lines. The count may only fall: delete the dead rules, then
lower `CAP`. Names built by concatenation ("tint-" + name) are found by their
literal stem, so a built family counts as used while any literal use of the
stem exists.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parent.parent
CSS = sorted((ROOT / "frontend" / "css").glob("*.css"))

#: Unused class names on 2026-10-26. Lower it; never raise it.
CAP = 196

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CLASS = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
_BLOCK = re.compile(r"([^{};]+)\{")
_URL = re.compile(r"url\([^)]*\)")


def _selector_classes() -> set[str]:
    names: set[str] = set()
    for path in CSS:
        text = _URL.sub("", _COMMENT.sub("", path.read_text(encoding="utf-8")))
        for prelude in _BLOCK.findall(text):
            if prelude.lstrip().startswith("@") or ":" in prelude and prelude.strip().endswith(";"):
                continue
            names.update(_CLASS.findall(re.sub(r"\[[^\]]*\]", "", prelude)))
    return {n for n in names if not re.fullmatch(r"\d.*", n)}


def _corpus() -> str:
    parts = [(ROOT / "frontend" / "index.html").read_text(encoding="utf-8")]
    for folder, suffix in (("frontend/js", ".js"), ("frontend", ".html"), ("frontend", ".svg"), ("src", ".py")):
        for path in repo_files(ROOT / folder, suffixes=(suffix,)):
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def unused() -> list[str]:
    corpus = _corpus()
    tokens = set(re.findall(r"[\w-]+", corpus))
    stems = set(re.findall(r"""["'`]([\w-]+-)(?:["'`]|\$\{)""", corpus))
    out = []
    for name in sorted(_selector_classes()):
        if name in tokens:
            continue
        stem = name.rsplit("-", 1)[0] + "-" if "-" in name else ""
        if len(stem) > 3 and stem in stems:
            continue
        out.append(name)
    return out


def test_unused_css_names_do_not_grow():
    found = unused()
    assert len(found) <= CAP, f"{len(found)} class names used nowhere (cap {CAP}); first: {found[:20]}"
