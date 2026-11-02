"""Paths and names that come from a request or a stored row (audit 1031 AR8).

`contained` was written four times (`routes_files._within_exports`, `_within_dir`,
`backup.backup_path` and a copy in `docreader`), one of them without the
separator that stops `uploads2` passing for `uploads`; `slug` was three.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


class OutsideFolder(ValueError):
    """The name reaches outside the folder it was joined to."""


def contained(base_dir: Path | str, name: str) -> Path:
    """`base_dir / name`, resolved with links followed, or `OutsideFolder`.

    The separator is part of `base` and the guard is a bare `startswith` on a
    plain variable: the shape CodeQL's `Path::SafeAccessCheck` recognises (a
    stored name reaches here through a database round trip, which that
    analysis tracks as tainted), and the one a sibling folder cannot pass.
    """
    base = os.path.join(os.path.realpath(str(base_dir)), "")
    candidate = os.path.realpath(os.path.join(base, name))
    if not candidate.startswith(base):
        raise OutsideFolder(name)
    return Path(candidate)


def slug(text: str, length: int = 40, *, ascii_only: bool = False, fallback: str = "note") -> str:
    """A file or id slice of some words: the first line, `#` stripped.

    `ascii_only` is the id form (lower case, a-z and 0-9, dashes: a space's id);
    the default keeps letters of any script, for a file name a person reads.
    """
    first = (text or "").strip().split("\n", 1)[0].lstrip("#").strip()
    if ascii_only:
        return re.sub(r"[^a-z0-9]+", "-", first.lower()).strip("-")[:length] or fallback
    cleaned = re.sub(r"[^\w\s-]", "", first)[:length].strip()
    return re.sub(r"\s+", "-", cleaned) or fallback
