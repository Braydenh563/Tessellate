"""`scripts/gate.sh --staged` runs the lint set once, against the index.

It used to run the lint set twice back to back, first against the working tree
(the plain `lints` step) and then against a checkout of the index
(`staged-lints`), so a staged commit paid for the set twice: over twenty-five
minutes under load (OPEN.md, "Smaller backend and gate rows"). The working-tree
run adds nothing the staged one lacks, since both run the one `LINTS` array
over the same tracked files and the staged one reads what the commit will hold,
so under `--staged` it is skipped.

Three things are pinned, in a scratch repository with the real script and a
stand-in interpreter that logs every pytest call it is handed (the real lints
are the slow part, and what is under test is which tree they are run in):

1. with something staged, the lint set runs once, in a checkout of the index
   (it reads the staged file, not the one in the folder);
2. that one run is handed exactly the arguments a plain `gate.sh` hands its
   own, so nothing the working-tree run checked was lost;
3. with nothing staged there is no index to check, so the working tree is
   linted once instead: `--staged` never runs zero lints.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "gate.sh"


def _git(repo: Path, *args: str) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo.parent)}
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env, check=True)


@pytest.fixture
def scratch(tmp_path: Path) -> dict:
    if not shutil.which("git") or not shutil.which("bash"):  # pragma: no cover - both are in the sandbox and CI
        pytest.skip("git or bash is not available")
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "frontend" / "js").mkdir(parents=True)
    (repo / ".venv" / "bin").mkdir(parents=True)
    shutil.copy(GATE, repo / "scripts" / "gate.sh")
    (repo / "frontend" / "js" / "a.js").write_text("let a = 1;\n", encoding="utf-8")
    (repo / "frontend" / "sw.js").write_text("let s = 1;\n", encoding="utf-8")
    (repo / "marker.txt").write_text("committed", encoding="utf-8")
    (repo / "scripts" / "codemap.py").write_text("# stand-in\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "CODEMAP.md").write_text("map of committed\n", encoding="utf-8")
    ruff = repo / ".venv" / "bin" / "ruff"
    ruff.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ruff.chmod(0o755)
    # The stand-in interpreter: every `-m pytest` call is logged with the
    # folder it ran in, the marker file it could read there, and its arguments.
    stub = tmp_path / "py"
    stub.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            case "$*" in
              *"-m pytest"*) echo "RUN|$(pwd -P)|$(cat marker.txt 2>/dev/null)|$*" >> "$STUB_LOG" ;;
            esac
            # The stand-in map builder writes a map of the marker beside it.
            case "$1" in
              */scripts/codemap.py) d="$(dirname "$(dirname "$1")")"; mkdir -p "$d/docs"
                echo "map of $(cat "$d/marker.txt")" > "$d/docs/CODEMAP.md" ;;
            esac
            exit 0
            """
        ),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-f", ".")
    _git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "base")
    return {"repo": repo, "stub": stub, "log": tmp_path / "stub.log", "gate_log": tmp_path / "gate-logs"}


def _gate(scratch: dict, *flags: str) -> tuple[list[tuple[str, str, str]], str]:
    """Run the scratch repo's gate; return its pytest calls (cwd, marker, args) and its stdout."""
    scratch["log"].write_text("", encoding="utf-8")
    env = {**os.environ, "PY": str(scratch["stub"]), "STUB_LOG": str(scratch["log"]),
           "GATE_LOG": str(scratch["gate_log"])}
    done = subprocess.run(["bash", "scripts/gate.sh", *flags], cwd=scratch["repo"], capture_output=True,
                          text=True, env=env, check=False)
    runs = []
    for line in scratch["log"].read_text(encoding="utf-8").splitlines():
        _, cwd, marker, args = line.split("|", 3)
        runs.append((cwd, marker, args))
    return runs, done.stdout


def _stage_a_change(scratch: dict) -> None:
    marker = scratch["repo"] / "marker.txt"
    marker.write_text("staged", encoding="utf-8")
    _git(scratch["repo"], "add", "marker.txt")
    # The folder then moves on from the index, as an agent's half-written
    # file does: the two trees now disagree about the marker.
    marker.write_text("working", encoding="utf-8")


def test_staged_runs_the_lint_set_once_and_against_the_index(scratch):
    _stage_a_change(scratch)
    runs, out = _gate(scratch, "--staged")
    assert len(runs) == 1, f"the lint set ran {len(runs)} times under --staged: {runs}"
    cwd, marker, args = runs[0]
    assert Path(cwd) != Path(scratch["repo"]).resolve(), "--staged linted the working tree, not a checkout of the index"
    assert marker == "staged", f"the lints saw {marker!r}, not what is staged"
    assert "tests/test_style_scale.py" in args
    assert "ran:     lints" not in out
    assert "staged-lints" in out.split("passed:")[1].splitlines()[0]


def test_staged_hands_the_index_the_whole_lint_set_a_plain_run_checks(scratch):
    plain, _ = _gate(scratch)
    assert len(plain) == 1
    _stage_a_change(scratch)
    staged, _ = _gate(scratch, "--staged")
    assert len(staged) == 1
    # Same interpreter flags, same files, same order: nothing the working-tree
    # run checked was dropped by skipping it.
    assert staged[0][2] == plain[0][2]
    assert len(staged[0][2].split()) > 20  # the real LINTS array, not an empty list


def test_staged_with_nothing_staged_lints_the_working_tree_once(scratch):
    (scratch["repo"] / "marker.txt").write_text("working", encoding="utf-8")
    runs, out = _gate(scratch, "--staged")
    assert len(runs) == 1, f"--staged with nothing staged ran the lints {len(runs)} times: {runs}"
    cwd, marker, _ = runs[0]
    assert Path(cwd) == Path(scratch["repo"]).resolve()
    assert marker == "working"
    assert "staged-lints (nothing staged" in out


def test_staged_builds_the_code_map_from_the_index_not_the_folder(scratch):
    """2026-11-02: the map was built from the folder and staged, so a commit made while
    other files had unstaged edits carried a map of code it did not hold, and
    test_codemap_fresh failed in the staged lints (twice this session, and repo3a-1102)."""
    _stage_a_change(scratch)
    _gate(scratch, "--staged")
    done = subprocess.run(["git", "-C", str(scratch["repo"]), "show", ":docs/CODEMAP.md"],
                          capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "map of staged"


def test_a_plain_gate_builds_the_code_map_from_the_folder(scratch):
    (scratch["repo"] / "marker.txt").write_text("working", encoding="utf-8")
    _gate(scratch)
    assert (scratch["repo"] / "docs" / "CODEMAP.md").read_text(encoding="utf-8").strip() == "map of working"


def test_staged_with_a_clean_folder_leaves_the_folder_map_matching_the_index(scratch):
    marker = scratch["repo"] / "marker.txt"
    marker.write_text("staged", encoding="utf-8")
    _git(scratch["repo"], "add", "marker.txt")
    _gate(scratch, "--staged")
    assert (scratch["repo"] / "docs" / "CODEMAP.md").read_text(encoding="utf-8").strip() == "map of staged"
