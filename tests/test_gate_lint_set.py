"""The merge gate's lint set names the lints no changed file selects.

`scripts/gate.sh --staged` runs only the `LINTS` list against the index, so a
lint that reads the Guide, the markup and the frontend all at once has to be
named there: no diff ever selects it by file name. A help edit once put the
Guide's whiteboard keys entry at 1,926 characters against its 1,920 budget and
passed the gate, because `tests/test_help_controls.py` was not in the list.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _lints() -> str:
    text = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    start = text.index("LINTS=(")
    return text[start : text.index("step lints", start)]


def test_the_lints_that_no_changed_file_selects_are_in_the_gate():
    lints = _lints()
    for name in ("test_help_controls.py", "test_like_escaping.py", "test_scratchpad_size.py", "test_codeql_shapes.py"):
        assert f"tests/{name}" in lints, f"scripts/gate.sh LINTS does not run {name}"
        assert (ROOT / "tests" / name).is_file()


def test_every_sweep_the_sweeps_mode_names_exists():
    """`gate.sh --sweeps` runs `node scratchpad/ui-sweeps/<name>.js` for each
    name in its list, and a name whose file is gone fails that step for ever:
    fifteen were (the 2026-10 sweep cleanup deleted the files and left the
    names). The list and the folder have to agree."""
    import re

    text = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    names = re.search(r"for s in ([a-z0-9 ]+); do step", text)
    assert names, "gate.sh has no sweep list"
    missing = [n for n in names.group(1).split() if not (ROOT / "scratchpad" / "ui-sweeps" / f"{n}.js").is_file()]
    assert not missing, f"scripts/gate.sh --sweeps names sweeps that do not exist: {missing}"


def test_a_hung_test_fails_by_name_rather_than_by_the_shell_timeout():
    """The full suite stopped twice at 92% and 99% under -q with nothing named
    (ledger 2026-11-12b). With pytest-timeout installed the targeted and full
    runs carry a per-test limit, so a hang names its test and its stacks."""
    text = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert 'import pytest_timeout" 2>/dev/null && TIMEOUT=(--timeout=' in text
    for step in ("step changed-tests", "step full-suite"):
        line = next(l for l in text.splitlines() if step in l and "pytest" in l)
        assert '"${TIMEOUT[@]}"' in line, f"{step} runs without the per-test limit"
