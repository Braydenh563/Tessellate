"""Relative links in the archived and live agent files resolve.

Thirty-three agent files moved from `docs/roadmap/agent-remaining/` to
`docs/roadmap/archive/agent-remaining/` (2026-10-04) one directory deeper and
kept their `../` links, so 57 of them pointed at files that are not there
(`../INBOX.md` from the archive is `archive/INBOX.md`). A file that moves
again has the same failure, so this checks every Markdown link whose target is
a relative path, in both directories.

Both directories were retired on 2026-11-12 (INBOX 1784: their open items are
LEDGER rows); the same failure now threatens the roadmap files that replaced
them, so the check walks `docs/roadmap/` itself.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

ROADMAP = Path(__file__).resolve().parents[1] / "docs" / "roadmap"
DIRS = (ROADMAP,)

_FENCE = re.compile(r"```.*?```", re.S)
_CODE_SPAN = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"\]\(([^)\s#]+)(?:#[^)]*)?\)")


def _broken(path: Path) -> list[str]:
    text = _CODE_SPAN.sub("", _FENCE.sub("", path.read_text(encoding="utf-8")))
    out = []
    for match in _LINK.finditer(text):
        target = match.group(1)
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("/"):
            continue
        if not (path.parent / target).resolve().exists():
            out.append(target)
    return out


def test_every_relative_link_in_the_agent_files_resolves():
    broken = {
        str(path.relative_to(ROADMAP)): bad
        for directory in DIRS
        for path in repo_files(directory, suffixes=(".md",))
        if (bad := _broken(path))
    }
    assert not broken, f"links that point at nothing: {broken}"
