"""The packaging workflow's two guards (OPEN ledger 292 and 293).

The workflow itself runs only on a Windows runner, so what is checked here is
the logic that can run anywhere (the traceback filter) and the text of the
workflow (the upgrade steps skip cleanly in a repository with no release).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / ".github" / "workflows" / "package-check.yml").read_text(encoding="utf-8")


def _checker():
    spec = importlib.util.spec_from_file_location("traceback_check", ROOT / "packaging" / "traceback_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAMPLE = """INFO started
Traceback (most recent call last):
  File "a.py", line 3, in run
    thing()
ConnectionResetError: [WinError 10054] An existing connection was forcibly closed
INFO still fine
Traceback (most recent call last):
  File "b.py", line 9, in boot
    boom()
KeyError: 'oops'
"""


def test_every_traceback_is_found_with_its_last_line():
    found = _checker().tracebacks(SAMPLE)
    assert len(found) == 2
    assert found[0].splitlines()[-1].startswith("ConnectionResetError")
    assert found[1].splitlines()[-1] == "KeyError: 'oops'"
    assert "INFO" not in "".join(found)


def test_a_traceback_on_the_allow_list_is_ignored_and_the_rest_still_fail():
    check = _checker()
    allowed = ["ConnectionResetError: [WinError 10054]"]
    left = check.unexpected(SAMPLE, allowed)
    assert len(left) == 1 and "KeyError" in left[0]
    assert check.unexpected(SAMPLE, allowed + ["KeyError: 'oops'"]) == []
    assert len(check.unexpected(SAMPLE, [])) == 2


def test_the_allow_list_file_reads_comments_and_blank_lines_away(tmp_path):
    path = tmp_path / "allow.txt"
    path.write_text("# why\n\nKeyError: 'oops'  # reason\n", encoding="utf-8")
    assert _checker().read_allowed(path) == ["KeyError: 'oops'"]


def test_main_exits_zero_clean_and_one_on_an_unexpected_traceback(tmp_path, capsys):
    check = _checker()
    clean = tmp_path / "clean.log"
    clean.write_text("all good\n", encoding="utf-8")
    bad = tmp_path / "bad.log"
    bad.write_text(SAMPLE, encoding="utf-8")
    missing = tmp_path / "none.log"
    empty_allow = tmp_path / "allow.txt"
    empty_allow.write_text("", encoding="utf-8")
    assert check.main([str(clean), str(missing), "--allow", str(empty_allow)]) == 0
    assert check.main([str(bad), "--allow", str(empty_allow)]) == 1
    assert "KeyError" in capsys.readouterr().out


def test_the_smoke_step_uses_the_filter_not_a_bare_grep():
    assert "packaging/traceback_check.py" in FLOW
    assert 'grep -q "Traceback"' not in FLOW


def test_the_upgrade_steps_skip_when_the_repository_has_no_release():
    """A fork has no published installer to upgrade from: that is a notice,
    not a red build. The upstream repository still fails loudly."""
    assert "id: previous" in FLOW
    assert "steps.previous.outputs.found == 'true'" in FLOW
    assert FLOW.count("steps.previous.outputs.found == 'true'") == 3
    step = FLOW[FLOW.index("id: previous") :]
    assert "Braydenh563/Tessellate" in step.split("- name:")[0]
    for name in (
        "Install the previous release and write a note in it",
        "Upgrade over it, and the note, the version and the schema are right",
        "Uninstall, and the program goes whole and the notes stay",
    ):
        block = FLOW[FLOW.index(f"- name: {name}") :].split("shell:")[0]
        assert "steps.previous.outputs.found == 'true'" in block, name


def _startup_time():
    spec = importlib.util.spec_from_file_location("startup_time", ROOT / "packaging" / "startup_time.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_startup_time_counts_seconds_to_the_first_200():
    st = _startup_time()
    now = [0.0]
    codes = iter([0, 0, 503, 200])

    def sleep(seconds):
        now[0] += 1.5

    seconds = st.seconds_to_health(
        "http://x", clock=lambda: now[0], sleep=sleep, fetch=lambda url: next(codes)
    )
    assert seconds == 4.5
    assert st.summary_line(seconds) == "Frozen Windows startup: 4.5 s to the first 200 from /health"


def test_startup_time_gives_up_past_the_limit_and_the_summary_is_written(tmp_path):
    st = _startup_time()
    now = [0.0]

    def sleep(seconds):
        now[0] += 10

    assert st.seconds_to_health("http://x", 30, clock=lambda: now[0], sleep=sleep, fetch=lambda u: 0) is None
    out = tmp_path / "summary.md"
    original = st.seconds_to_health
    st.seconds_to_health = lambda base, limit: 2.0
    try:
        assert st.main(["--base", "http://x", "--summary", str(out)]) == 0
    finally:
        st.seconds_to_health = original
    assert out.read_text(encoding="utf-8") == "Frozen Windows startup: 2.0 s to the first 200 from /health\n"


def test_the_workflow_records_startup_with_no_failing_threshold():
    block = FLOW[FLOW.index("- name: Record the frozen app's startup time") :].split("- name:", 2)[1]
    assert "packaging/startup_time.py" in block and "GITHUB_STEP_SUMMARY" in block
    assert "|| true" in block
