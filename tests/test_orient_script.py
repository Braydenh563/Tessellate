"""scripts/orient.sh is the SessionStart hook: short, fast, and wired in settings."""
import json
import resource
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_orient_prints_under_forty_lines_in_under_a_second():
    # The best of two runs: the first pays the disk cache. CPU time of the
    # script and everything it starts, not the wall clock (L-general-70): a CI
    # runner under the parallel suite once took 1.14 s on a script that runs in
    # 0.18 s warm.
    took = []
    for _ in range(2):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        out = subprocess.run(["bash", "scripts/orient.sh"], cwd=ROOT, capture_output=True, text=True, check=True)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        took.append(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime)
    assert min(took) < 1.0, took
    lines = out.stdout.splitlines()
    assert 0 < len(lines) < 40
    assert "**Now (" in out.stdout and "open INBOX items:" in out.stdout


def test_settings_runs_orient_at_session_start():
    cfg = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    cmds = [h["command"] for g in cfg["hooks"]["SessionStart"] for h in g["hooks"]]
    assert "bash scripts/orient.sh" in cmds
