"""Which build is running, since when, and whether its data folder is writable.

`/health` and Settings, About show these so a report can say "build 1a2b3c4,
folder not writable" instead of "it does not work". The commit is a stamp,
not a measurement: the environment variable (set by the Docker build or the
packaging step), then a `SOURCE_COMMIT` file beside the package, then `git`
for a source checkout. None of those is the person's data.
"""

from __future__ import annotations

import functools
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tessellate.core.subproc import NO_WINDOW

#: When this process started, to the second. Module-level so every call agrees.
STARTED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

_PACKAGE = Path(__file__).resolve().parent.parent
_STAMP_FILES = (_PACKAGE / "SOURCE_COMMIT", _PACKAGE.parent.parent / "SOURCE_COMMIT")


def _git_head() -> str:
    try:
        done = subprocess.run(  # noqa: S603  # fixed argv, no shell
            ["git", "rev-parse", "HEAD"], cwd=_PACKAGE, capture_output=True, text=True, timeout=2, check=False,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


@functools.lru_cache(maxsize=1)
def source_commit() -> str:
    """The first 12 characters of the commit this build came from, or ""."""
    found = os.getenv("TESSELLATE_SOURCE_COMMIT", "").strip()
    for stamp in () if found else _STAMP_FILES:
        try:
            found = stamp.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if found:
            break
    return (found or _git_head())[:12]


def data_dir_writable(path: Path) -> bool:
    """Whether the folder exists and this process may create files in it."""
    return path.is_dir() and os.access(path, os.W_OK | os.X_OK)
