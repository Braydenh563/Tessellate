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


def _plan(*args: str, env: dict | None = None) -> list[list[str]]:
    import os
    import subprocess

    done = subprocess.run(
        ["bash", "scripts/ci_sweeps.sh", "--plan", *args], cwd=ROOT, capture_output=True, text=True, timeout=30,
        env={**os.environ, **(env or {})},
    )
    assert done.returncode == 0, done.stderr
    return [line.split() for line in done.stdout.splitlines() if line.strip()]


def _seconds() -> dict[str, int]:
    lines = (SWEEPS / "stable.txt").read_text(encoding="utf-8").splitlines()
    return {line.split()[0]: int(line.split()[1].rstrip("s")) for line in lines if line.strip() and not line.startswith("#")}


def test_a_long_sweep_runs_as_shards_each_well_under_the_timeout() -> None:
    """errors and fontmatrix took 324s and 45 minutes whole (2026-11-21), so a
    `|` in a line's env token splits it into runs of their own, each under
    its own 300s timeout; `--plan` prints the runs without starting a server.
    The font matrix runs whole: one SHARD per CELLS_PER_SHARD cells, so every
    font, theme and width is checked in CI. deepflows too: a width x theme took
    265 to 299s whole, so each is two shards (the settings flow, the rest)."""
    runs = _plan()
    errors = [r for r in runs if r[0] == "errors"]
    assert [r[1:] for r in errors] == [["WIDTHS=1440,1024"], ["WIDTHS=820,390"]]
    matrix = (SWEEPS / "fontmatrix.js").read_text(encoding="utf-8")
    per_shard = int(re.search(r"CELLS_PER_SHARD = (\d+)", matrix).group(1))
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    fonts = re.findall(r'<option value="([a-z0-9-]+)"', html.split('id="font-seg"')[1].split("</select>")[0])
    cells = len(fonts) * 2 * 3  # fonts x light, dark x 1440, 1024, 390
    shards = [r[1:] for r in runs if r[0] == "fontmatrix"]
    assert shards == [[f"SHARD={n}"] for n in range(1, -(-cells // per_shard) + 1)]
    flows = (SWEEPS / "deepflows.js").read_text(encoding="utf-8")
    sizes = re.search(r"const \[w, th\] = \[(.*?)\]\[Math", flows).group(1)
    halves = len(sizes.split("], [")) * 2  # each width x theme: settings, the rest
    assert [r[1:] for r in runs if r[0] == "deepflows"] == [[f"SHARD={n}"] for n in range(1, halves + 1)]
    sharded = ("errors", "fontmatrix", "deepflows")
    assert [r[0] for r in runs if r[0] not in sharded] == [n for n in _stable() if n not in sharded]
    for name, secs in _seconds().items():
        assert secs <= 240, name  # seconds per run


def test_the_slices_split_the_runs_and_each_fits_the_job() -> None:
    """The whole list is over an hour of runs, so CI runs it as SLICES jobs:
    `SLICE=k/n` keeps the k-th share, balanced by each line's seconds. The
    slices together are the plan, no run twice, and each stays under 35 of
    the job's 45 minutes (setup takes about 4)."""
    runs = _plan()
    secs = _seconds()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = ci[ci.index("\n  ui-sweeps:"):]
    n = len(re.search(r"slice: \[([0-9, ]+)\]", job).group(1).split(","))
    assert f"SLICE: ${{{{ matrix.slice }}}}/{n}" in job
    assert "ui-sweep-logs-${{ matrix.slice }}" in job  # one artifact per slice
    got = []
    for k in range(1, n + 1):
        part = _plan(env={"SLICE": f"{k}/{n}"})
        assert sum(secs[r[0]] for r in part) <= 35 * 60, (k, part)
        got += part
    assert sorted(map(tuple, got)) == sorted(map(tuple, runs))


def test_the_gate_runs_each_sweep_as_the_list_shards_it() -> None:
    """gate.sh --sweeps runs a listed sweep the way CI does (each shard on
    its own), and a seeded sweep finds the data dir the server uses."""
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "bash scripts/ci_sweeps.sh --runs" in gate
    assert _plan_runs("fontmatrix")[:2] == ["SHARD=1", "SHARD=2"]
    assert _plan_runs("docks") == [""]  # no env: one plain run
    script = (ROOT / "scripts" / "ci_sweeps.sh").read_text(encoding="utf-8")
    assert re.search(r"export DATA=", script)


def _plan_runs(name: str) -> list[str]:
    import subprocess

    done = subprocess.run(["bash", "scripts/ci_sweeps.sh", "--runs", name], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return done.stdout.splitlines()
