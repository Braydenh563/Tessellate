"""Which build is running, since when, and on which data folder (L-general-6).

`/health` carries these so a person (or a sweep) can tell the server they are
looking at from a stale one still holding the port: the commit it was started
from, when it started, and an id for its data folder. The id is a short hash,
never the path, because `/health` answers before sign-in.

The commit is read from `.git` as files (a branch ref, `packed-refs`, a
detached HEAD, or a worktree's `gitdir`), never by running git: a packaged
build has neither git nor a repository and reports "".
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from tessellate.core import clock

ROOT = Path(__file__).resolve().parents[3]
STARTED_AT = clock.utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_commit(root: Path = ROOT) -> str:
    """The commit `root`'s checkout is at, or "" when there is none to read."""
    git = root / ".git"
    if git.is_file():  # a worktree: `.git` names its own folder
        line = _read(git)
        if not line.startswith("gitdir:"):
            return ""
        git = Path(line.split(":", 1)[1].strip())
    head = _read(git / "HEAD")
    if not head.startswith("ref:"):
        return head if len(head) == 40 else ""
    ref = head.split(":", 1)[1].strip()
    common = git / _read(git / "commondir") if (git / "commondir").is_file() else git
    for base in (git, common):
        sha = _read(base / ref)
        if len(sha) == 40:
            return sha
    for line in _read(common / "packed-refs").splitlines():
        sha, _, name = line.partition(" ")
        if name == ref and len(sha) == 40:
            return sha
    return ""


SOURCE_COMMIT = read_commit()


def data_dir_id(data_dir: str | Path) -> str:
    """Twelve hex digits of the folder's resolved path: the same folder gives
    the same id, and the path itself never leaves the machine."""
    return hashlib.sha256(str(Path(data_dir).resolve()).encode("utf-8")).hexdigest()[:12]


def writable(data_dir: str | Path) -> bool:
    return os.access(data_dir, os.W_OK)
