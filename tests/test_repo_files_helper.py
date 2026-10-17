"""The shared repo walk (`tests/_repo_files.py`) lists what a fresh walk lists.

About thirty scanners moved from their own `rglob` to this helper, so a wrong
answer here would quietly shrink every one of them. These pin the three shapes
they use (a source tree by suffix, a name pattern, the whole repo with
excluded directories), that the excludes behave, and that a second call does
not list the disk again.
"""

from __future__ import annotations

import os
from pathlib import Path

from tests import _repo_files
from tests._repo_files import ROOT, repo_files


def _fresh(root: Path, pattern: str) -> list[Path]:
    return sorted(root.rglob(pattern))


def test_a_suffix_under_a_source_tree_matches_a_fresh_rglob():
    src = ROOT / "src" / "tessellate"
    assert repo_files(src, suffixes=(".py",)) == _fresh(src, "*.py")
    assert repo_files(ROOT / "frontend" / "css", suffixes=(".css",)) == _fresh(ROOT / "frontend" / "css", "*.css")


def test_a_name_pattern_matches_a_fresh_rglob():
    tests = ROOT / "tests"
    assert repo_files(tests, patterns=("test_*.py",)) == _fresh(tests, "test_*.py")
    assert repo_files(ROOT / "docs", suffixes=(".md",)) == _fresh(ROOT / "docs", "*.md")


def test_the_whole_repo_matches_a_fresh_walk_less_the_pruned_directories():
    pruned = {".git", ".venv", "node_modules", "__pycache__", ".gate"}
    expected = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        here = Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in pruned and here / d != ROOT / ".claude" / "worktrees"]
        expected.extend(here / name for name in filenames if name not in pruned and not name.endswith(("-shm", "-wal", "-journal")))
    assert repo_files() == sorted(expected)
    assert repo_files(ROOT, suffixes=(".bat",)) == sorted(p for p in expected if p.name.endswith(".bat"))


def test_excludes_drop_directories_and_names_but_nothing_else():
    src = ROOT / "src" / "tessellate"
    everything = repo_files(src, suffixes=(".py",))
    no_vendor = repo_files(src, suffixes=(".py",), exclude_dirs=("vendor",))
    assert no_vendor == [p for p in everything if "vendor" not in p.relative_to(ROOT).parts]
    assert len(no_vendor) < len(everything), "src/tessellate/vendor is no longer there to exclude"
    assert repo_files(src, suffixes=(".py",), exclude_names=("jobruns.py",)) == [
        p for p in everything if p.name != "jobruns.py"
    ]
    # A directory name is matched anywhere in the path below the repo root, as `path.parts` was.
    assert repo_files(src, suffixes=(".py",), exclude_dirs=("src",)) == []


def test_overlapping_roots_list_a_file_once():
    both = repo_files(ROOT / "src", ROOT / "src" / "tessellate", suffixes=(".py",))
    assert both == repo_files(ROOT / "src", suffixes=(".py",))
    assert len(both) == len(set(both))


def test_a_second_call_does_not_list_the_disk_again(monkeypatch):
    _repo_files.forget()
    calls = []
    real_walk, real_scandir = os.walk, os.scandir

    def counting_walk(*args, **kwargs):
        calls.append(("walk", args[0]))
        return real_walk(*args, **kwargs)

    def counting_scandir(*args, **kwargs):
        calls.append(("scandir", args[0] if args else None))
        return real_scandir(*args, **kwargs)

    monkeypatch.setattr(os, "walk", counting_walk)
    monkeypatch.setattr(os, "scandir", counting_scandir)
    first = repo_files(ROOT / "src", suffixes=(".py",))
    after_first = len(calls)
    assert after_first, "the first call has to list the disk"
    # Another filter over the same tree, and a root inside it: same listing.
    assert repo_files(ROOT / "src", suffixes=(".py",)) == first
    assert repo_files(ROOT / "src" / "tessellate", patterns=("*.py",)) == [
        p for p in first if p.is_relative_to(ROOT / "src" / "tessellate")
    ]
    assert len(calls) == after_first, "a later call walked again"
