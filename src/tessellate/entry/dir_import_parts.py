"""A folder import's parts: which folders it may read, what is already in, the walk's Stop and its activity line.

Moved out of api/routes_settings_transfer.py (the 800-line bar, L624), which imports them under the same names.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from tessellate.core import deps, jobs
from tessellate.repo import notes as notes_repo


def _import_roots() -> list[str]:
    """The folders a directory import may read from, as real paths."""
    roots = []
    for candidate in (Path.home(), deps.get_config().data_dir):
        try:
            roots.append(os.path.realpath(candidate))
        except OSError:
            continue
    return roots


def _under_root(real: str, root: str) -> bool:
    """Is the real path `real` the folder `root` or somewhere inside it?"""
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def _import_root_for(real: str) -> str:
    """The import root `real` lies in (separator-aware), or "" for none."""
    for root in _import_roots():
        if _under_root(real, root):
            return root
    return ""


def _inside(root: Path, f: Path) -> bool:
    """Does `f`, symlinks followed, still lie inside `root`?

    The walk below reads every `.md` under the chosen folder, and a symlink
    inside it can point anywhere: `innocent.md -> ~/.ssh/config.md`, or a
    linked folder. The folder was checked; what it links to was not, so
    each file is checked by where it resolves.
    """
    real = os.path.realpath(f)
    return _under_root(real, os.path.realpath(root)) and os.path.isfile(real)


#: Stands for "this path is a private note": matched without its text.
_PRIVATE = object()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _already_imported(session) -> dict:  # noqa: ANN001
    """Every live note that came from a vault file: its path in the vault ->
    the hashes of its text, or `_PRIVATE` when its text is encrypted."""
    known: dict = {}
    for path, content, private in notes_repo.source_texts(session):
        if private:
            known[path] = _PRIVATE
        elif known.get(path) is not _PRIVATE:
            known.setdefault(path, set()).add(_text_hash((content or "").strip()))
    return known


def _directory_import_detail(imported: int, already: int, skipped: int, skipped_oversize: int, limit: int) -> str:
    """The activity line a folder import leaves: what came in, what was
    already in, and what was skipped and why."""
    detail = f"markdown dir x{imported}"
    if already:
        detail += f", {already} already in"
    if skipped:
        detail += f", skipped {skipped}"
        if skipped_oversize:
            detail += f" ({skipped_oversize} over {limit // (1024 * 1024)} MB)"
    return detail


def _until_stopped(files):  # noqa: ANN001, ANN202
    """The walk, ended between files once Stop is pressed (L-world-class-66):
    what came in stays, and running the import again finishes the rest."""
    for f in files:
        if jobs.stop_requested():
            return
        yield f
