"""Every workflow action is pinned to a commit and no checkout keeps its token.

A tag such as `@v7` can be moved by whoever owns the action; a 40-character
commit is what was reviewed. The behaviour is a CI run, which a unit test
cannot start, so this reads the workflow text (L-general-2).
"""

from __future__ import annotations

import pathlib
import re

WORKFLOWS = sorted((pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows").glob("*.yml"))
USES = re.compile(r"^\s*(?:- )?uses:\s*(\S+)@(\S+)")


def test_every_action_is_pinned_to_a_commit_sha():
    loose = []
    for path in WORKFLOWS:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found = USES.match(line)
            if found and not re.fullmatch(r"[0-9a-f]{40}", found[2]):
                loose.append(f"{path.name}:{number} {found[1]}@{found[2]}")
    assert not loose, loose


def test_every_checkout_drops_its_token():
    keeping = []
    for path in WORKFLOWS:
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines):
            if "actions/checkout@" in line and "persist-credentials: false" not in "\n".join(lines[number : number + 4]):
                keeping.append(f"{path.name}:{number + 1}")
    assert not keeping, keeping


def test_a_workflow_lint_job_exists():
    assert "zizmor" in (WORKFLOWS[0].parent / "workflow-lint.yml").read_text(encoding="utf-8")
