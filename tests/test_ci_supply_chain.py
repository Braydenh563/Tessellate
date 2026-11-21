"""CI supply chain (L-general-2): every action is pinned to a commit, no
checkout leaves its token in .git/config, and a workflow lints the workflows."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def test_every_action_is_pinned_to_a_commit_with_its_tag_beside_it():
    """A workflow is not code the suite can run; the pin is the line itself."""
    loose = [
        f"{p.name}: {line.strip()}"
        for p in WORKFLOWS
        for line in p.read_text(encoding="utf-8").splitlines()
        if re.search(r"\buses:", line) and not re.search(r"uses: [\w.-]+/[\w./-]+@[0-9a-f]{40} # \S+$", line)
    ]
    assert not loose, loose


def test_every_checkout_drops_its_credentials():
    """Only the workflow text says whether a checkout keeps its token."""
    for p in WORKFLOWS:
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "uses: actions/checkout@" in line:
                block = []
                for nxt in lines[i + 1:]:
                    if re.match(r"\s*- ", nxt) or not nxt.strip():
                        break
                    block.append(nxt.strip())
                assert "persist-credentials: false" in block, f"{p.name}:{i + 1}"


def test_the_workflows_are_linted_by_a_pinned_actionlint_and_zizmor():
    """The linters run in CI only; here, that the workflow names them pinned."""
    text = (ROOT / ".github" / "workflows" / "workflow-lint.yml").read_text(encoding="utf-8")
    assert re.search(r"actionlint-py==\d", text) and re.search(r"zizmor==\d", text)
    assert "run: actionlint" in text and "run: zizmor" in text
