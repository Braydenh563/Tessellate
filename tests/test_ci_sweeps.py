"""The stable ui sweeps run in CI (L-general-20).

These read the workflow and the list because the job itself runs only on
GitHub's runner: what can be checked here is that the job calls the script,
the script reads the list, and every listed sweep exists and is one the gate
also runs.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SWEEPS = ROOT / "scratchpad" / "ui-sweeps"


def _stable() -> list[str]:
    lines = (SWEEPS / "stable.txt").read_text(encoding="utf-8").splitlines()
    return [line.split()[0] for line in lines if line.strip() and not line.startswith("#")]


def test_every_stable_sweep_exists_and_is_one_the_gate_runs() -> None:
    """A name on the list that is not a file would fail CI for the wrong reason."""
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    names = _stable()
    assert len(names) >= 20, names
    assert len(names) == len(set(names)), names
    for name in names:
        assert (SWEEPS / f"{name}.js").is_file(), name
        assert re.search(rf"\b{re.escape(name)}\b", gate), f"{name} is not in gate.sh's sweep list"


def test_the_ci_job_runs_the_script_and_the_script_runs_the_list() -> None:
    """The workflow is the only place the job is defined; this pins its wiring."""
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = ci[ci.index("\n  ui-sweeps:"):]
    assert "bash scripts/ci_sweeps.sh" in job
    assert "npx playwright install --with-deps chromium" in job
    script = (ROOT / "scripts" / "ci_sweeps.sh").read_text(encoding="utf-8")
    assert "scratchpad/ui-sweeps/stable.txt" in script
    assert "timeout 300 node" in script  # one stuck sweep cannot eat the job
