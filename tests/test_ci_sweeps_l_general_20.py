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
