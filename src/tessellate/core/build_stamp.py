"""Which build is running, read once (L-general-6): a report from a copy
that turned out to be an old checkout, or a notebook folder that went
read-only, is answered from `/health` and Settings > About instead of
guessed at."""

from __future__ import annotations

import os
import re
from functools import cache
from pathlib import Path

from tessellate.core import clock

#: When this process started serving, UTC, to the second.
STARTED_AT = clock.utc().isoformat(timespec="seconds")
_ROOT = Path(__file__).resolve().parents[3]
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _git_dir(root: Path) -> Path | None:
    dot = root / ".git"
    if dot.is_dir():
        return dot
    # A worktree's `.git` is a file naming its real folder.
    if dot.is_file():
        text = dot.read_text(encoding="utf-8", errors="replace").strip()
        if text.startswith("gitdir:"):
            return (root / text.split(":", 1)[1].strip()).resolve()
    return None


def _head_commit(git: Path) -> str:
    head = (git / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
    if not head.startswith("ref:"):
        return head
    ref = head.split(":", 1)[1].strip()
    # A worktree keeps its HEAD here and its refs in the main repository.
    common = git / "commondir"
    shared = (git / common.read_text(encoding="utf-8").strip()).resolve() if common.is_file() else git
    for base in (git, shared):
        loose = base / ref
        if loose.is_file():
            return loose.read_text(encoding="utf-8", errors="replace").strip()
    packed = shared / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.endswith(" " + ref):
                return line.split(" ", 1)[0]
    return ""


@cache
def source_commit(root: Path = _ROOT) -> str:
    """The commit this code came from: `TESSELLATE_SOURCE_COMMIT` (a build
    sets it), else the checkout's HEAD read from `.git` (no `git` process),
    else "" (an installed build that carries no history)."""
    stamped = os.getenv("TESSELLATE_SOURCE_COMMIT", "").strip().lower()
    if _SHA.match(stamped):
        return stamped
    try:
        git = _git_dir(root)
        found = _head_commit(git) if git else ""
    except OSError:
        return ""
    return found if _SHA.match(found) else ""


def data_dir_writable(path: str | os.PathLike[str]) -> bool:
    """Whether the notebook folder takes writes (a full disk or a read-only
    mount reads as False)."""
    return os.access(path, os.W_OK)
