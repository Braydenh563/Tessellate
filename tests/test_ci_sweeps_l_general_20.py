"""Source text: CI runs the steady ui sweeps and deepflows.js (L-general-20);
the job and its list are YAML and shell, so these check they name real files."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _stable() -> list[str]:
    text = (ROOT / "scripts" / "ci_sweeps.sh").read_text(encoding="utf-8")
    block = re.search(r"STABLE=\(([^)]*)\)", text).group(1)
    return block.split()


def test_ci_runs_the_sweep_script():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "bash scripts/ci_sweeps.sh" in ci


def test_every_listed_sweep_exists_and_deepflows_runs_last():
    names = _stable()
    assert len(names) >= 25 and len(set(names)) == len(names)
    for name in names:
        # `sweep@1440,1024` runs one sweep at some widths only (errors.js, split to stay under CI's 180s).
        file = name.split("@")[0]
        assert (ROOT / "scratchpad" / "ui-sweeps" / f"{file}.js").exists(), name
    text = (ROOT / "scripts" / "ci_sweeps.sh").read_text(encoding="utf-8")
    assert text.index("deepflows-seed.js") > text.index("for name in")


def test_the_sweeps_run_in_two_legs_that_cover_the_list_once():
    # The one job ran 28 min of sweeps plus deepflows against a 30 min limit
    # (12a37347); two legs of about 14 min each keep the limit and every sweep.
    text = (ROOT / "scripts" / "ci_sweeps.sh").read_text(encoding="utf-8")
    split = re.search(r'SPLIT_AT=(\S+)', text).group(1)
    names = _stable()
    assert split in names and 0 < names.index(split) < len(names)
    assert 'SHARD:-' in text and '"$SHARD" != 2' in text  # deepflows in leg 1, not leg 2
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = ci[ci.index("  ui-sweeps:"):]
    assert "shard: [1, 2]" in job and "SHARD: ${{ matrix.shard }}" in job
    assert "timeout-minutes: 30" in job.split("steps:")[0]
