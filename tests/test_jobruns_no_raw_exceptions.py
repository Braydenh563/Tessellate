"""A run's last-run line is a sentence, never `str(exc)` (ledger 1547).

An exception's text can carry the person's path or a library's wording.
`run.fail(exc)` and `run.fail(str(exc))` outside `core/jobruns.py` (which
words an exception itself, `failure_reason`) put it on the line; this holds
the audited modules to a sentence.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests._repo_files import repo_files

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"
_RAW = re.compile(r"\.fail\(\s*(?:str\()?(?:exc|error|err|e)\b")

#: Sites that still pass a raw value. Delete a line when its site is reworded.
ALLOWED = {
    "core/activity.py": 1,  # str(exc) or the type name, reviewed 2026-10-11: activity's own tools
    "core/jobs.py": 1,  # `error` is built by the pool from a typed failure
    "api/routes_recordings.py": 1,  # `error` is one of two fixed sentences
    "api/routes_studio.py": 1,  # `error` is one fixed sentence (the overview could not be made)
}


def test_run_fail_is_not_given_a_raw_exception():
    found = {}
    for path in repo_files(SRC, suffixes=(".py",)):
        rel = path.relative_to(SRC).as_posix()
        if rel == "core/jobruns.py":
            continue
        n = len(_RAW.findall(path.read_text(encoding="utf-8")))
        if n:
            found[rel] = n
    extra = {rel: n for rel, n in found.items() if n > ALLOWED.get(rel, 0)}
    assert not extra, f"word the failure as a sentence and log the exception: {extra}"
