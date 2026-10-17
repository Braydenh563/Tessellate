"""One cached walk of the checkout for the tests that scan source files.

About thirty tests used to walk the tree themselves (`SRC.rglob("*.py")`,
`ROOT.rglob("*")`, `ROOT.glob("**/*.bat")`), each paying for its own directory
listing of `src/` or the whole repo, and each keeping its own exclusion list.
`repo_files` walks each top-level directory once per process (a pytest-xdist
worker is a process) and every later call filters that list, so the scanners
share the walk. Their text reads share the decoded copy through the
`Path.read_text` cache in `conftest.py`.

What a caller still owns is what it scans: this module never decides that
vendored code, `.claude/` or docs are in or out. A scanner names its own
`suffixes`, `patterns` and `exclude_dirs`, so `test_no_silent_except` skips
`vendor` and `test_flaw_class_lints` does not, exactly as before.

Only directories no scanner has ever wanted are pruned from the walk itself:
`.git`, `.venv`, `node_modules`, `__pycache__`, `.gate` and `.claude/worktrees`
(another branch's checkout per running agent).

`exclude_dirs` and `exclude_names` are matched against the path relative to the
repo root. The scanners they replace tested `path.parts`, which also holds the
checkout's own location, so a checkout under `.claude/worktrees/` used to skip
everything that looked for `worktrees` or `.claude`.

The list is fixed when first asked for. No test writes into `src/`, `tests/`,
`frontend/` or `docs/` (the launcher tests copy into `tmp_path` first), so
nothing goes stale; a test that ever does must walk for itself.

Not named `test_*.py` on purpose, as `_app_js.py` and `_css_paths.py`.
"""

from __future__ import annotations

import os
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Never walked into, at any depth (a file of one of these names is left out too:
#: a linked worktree's `.git` is a file).
_PRUNE_DIRS = frozenset({".git", ".venv", "node_modules", "__pycache__", ".gate"})
#: Never walked into: directories by path relative to the root.
_PRUNE_PATHS = frozenset({(".claude", "worktrees")})

#: SQLite's sidecar files. A test that opens the app's default `data/` database
#: makes and removes them while the suite runs, so a cached walk and a fresh one
#: disagree about them; no scanner reads them.
_TRANSIENT = ("-shm", "-wal", "-journal")

# One entry per file: (path, parts relative to ROOT).
_Entry = tuple[Path, tuple[str, ...]]


@lru_cache(maxsize=None)
def _walk_top(top: str) -> tuple[_Entry, ...]:
    """Every file under the top-level directory `ROOT / top`, sorted."""
    base = ROOT / top
    out: list[_Entry] = []
    for dirpath, dirnames, filenames in os.walk(base):
        rel = Path(dirpath).relative_to(ROOT).parts
        dirnames[:] = [d for d in dirnames if d not in _PRUNE_DIRS and (*rel, d) not in _PRUNE_PATHS]
        out.extend((Path(dirpath, name), (*rel, name)) for name in filenames if name not in _PRUNE_DIRS and not name.endswith(_TRANSIENT))
    out.sort(key=lambda entry: entry[0])
    return tuple(out)


@lru_cache(maxsize=None)
def _top_level() -> tuple[tuple[str, ...], tuple[_Entry, ...]]:
    """The directories directly under the root, and the files in it."""
    dirs, files = [], []
    with os.scandir(ROOT) as it:
        for entry in it:
            if entry.name in _PRUNE_DIRS:
                continue  # also a linked worktree's `.git` file
            if entry.is_dir(follow_symlinks=False):
                dirs.append(entry.name)
            elif entry.is_file():
                files.append((ROOT / entry.name, (entry.name,)))
    return tuple(sorted(dirs)), tuple(sorted(files, key=lambda e: e[0]))


def forget() -> None:
    """Drop the cached walk, so the next call lists the disk again."""
    _walk_top.cache_clear()
    _top_level.cache_clear()


def _under(root: Path) -> tuple[_Entry, ...]:
    rel = root.relative_to(ROOT).parts
    if not rel:
        dirs, files = _top_level()
        merged = list(files)
        for top in dirs:
            merged.extend(_walk_top(top))
        return tuple(merged)
    entries = _walk_top(rel[0])
    if len(rel) == 1:
        return entries
    return tuple(e for e in entries if e[1][: len(rel)] == rel)


def repo_files(
    *roots: Path | str,
    suffixes: tuple[str, ...] = (),
    patterns: tuple[str, ...] = (),
    exclude_dirs: tuple[str, ...] = (),
    exclude_names: tuple[str, ...] = (),
) -> list[Path]:
    """Sorted files under `roots` (default: the whole repo), from the cached walk.

    `suffixes`: keep a file whose name ends with one of these (`".py"`, as
    `rglob("*.py")` does). `patterns`: keep a file whose name matches one of
    these `fnmatch` patterns (`"test_*.py"`). With both, a file needs one of
    each. `exclude_dirs`: drop a file with a directory of one of these names
    anywhere in its path below the repo root (so `("src",)` empties a `src/` scan). `exclude_names`: drop a file with
    one of these exact names.
    """
    wanted = [Path(r) if Path(r).is_absolute() else ROOT / r for r in roots] or [ROOT]
    skip_dirs = frozenset(exclude_dirs)
    skip_names = frozenset(exclude_names)
    seen: set[Path] = set()
    found: list[Path] = []
    for root in wanted:
        for path, parts in _under(root):
            if len(wanted) > 1:  # overlapping roots (src and src/tessellate) list a file once
                if path in seen:
                    continue
                seen.add(path)
            name = parts[-1]
            if suffixes and not name.endswith(suffixes):
                continue
            if patterns and not any(fnmatchcase(name, p) for p in patterns):
                continue
            if name in skip_names or (skip_dirs and not skip_dirs.isdisjoint(parts[:-1])):
                continue
            found.append(path)
    found.sort()
    return found
