"""The launcher scripts, checked from Linux CI.

Brief 17's contract is that `./start.sh` and `start.bat` are one launcher
with two spellings: the same flags, in the same order, in the same help
text, writing the same status protocol. Nothing in the suite can run cmd or
PowerShell, so this file reads the two scripts as text and fails the build
when they drift, which is the only way that promise survives a session that
only edits one of them.
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]


# **The repo's own .venv is not a fixture.** The first version of the shortcut
# round-trip below ran `./uninstall.sh --shortcuts --yes` with cwd=ROOT, and
# `--shortcuts` is "also remove", so `--yes` took the sandbox's real .venv
# with it, mid-suite, and every later test that spawned sys.executable died
# with "No such file or directory". A test that runs a script capable of
# deleting things runs it in a scratch copy (see `_scratch_repo`), and this
# fixture fails loudly if anything here ever touches the real one again.
@pytest.fixture(autouse=True)
def _repo_venv_is_not_a_fixture():
    before = (ROOT / ".venv").exists()
    yield
    after = (ROOT / ".venv").exists()
    assert before == after, "a test in this module created or deleted the repo's .venv"


def _scratch_repo(tmp_path: Path) -> Path:
    """A throwaway copy of the two scripts and the one asset `--shortcut`
    reads, with a fake .venv, so an uninstaller run has something of its
    own to remove and nothing of ours."""
    repo = tmp_path / "repo"
    (repo / "frontend").mkdir(parents=True)
    (repo / ".venv" / "bin").mkdir(parents=True)
    for name in ("start.sh", "uninstall.sh"):
        target = repo / name
        shutil.copy2(ROOT / name, target)
        target.chmod(0o755)
    shutil.copy2(ROOT / "frontend" / "icon-512.png", repo / "frontend" / "icon-512.png")
    return repo
START_SH = ROOT / "start.sh"
START_BAT = ROOT / "start.bat"
START_DESKTOP_SH = ROOT / "start-desktop.sh"
START_DESKTOP_BAT = ROOT / "start-desktop.bat"
#: One-double-click files for the launcher's actions (the owner 2026-10-11:
#: "I just need easy ways to run the set scripts and actions").
ACTION_SH = [ROOT / n for n in ("doctor.sh", "reinstall.sh", "tools.sh")]
ACTION_BAT = ["doctor.bat", "reinstall.bat", "tools.bat"]
UNINSTALL_SH = ROOT / "uninstall.sh"
UNINSTALL_BAT = ROOT / "uninstall.bat"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


class TestPortFromEnv:
    """`--port N` reaches the server.

    The launcher exports TESSELLATE_PORT; before this was read, the flag
    moved the launcher's port checks and the URL it opened but left the
    server itself on 8000, so `--port 8010` opened a browser at a port
    nothing was listening on.
    """

    def test_default_is_8000(self, monkeypatch):
        from tessellate.__main__ import _port_from_env

        monkeypatch.delenv("TESSELLATE_PORT", raising=False)
        assert _port_from_env() == 8000

    def test_a_number_is_honoured(self):
        from tessellate.__main__ import _port_from_env

        assert _port_from_env("8010") == 8010
        assert _port_from_env(" 8781 ") == 8781

    @pytest.mark.parametrize("raw", ["", "abc", "80.5", "0", "-1", "65536", "99999999"])
    def test_junk_falls_back_rather_than_raising(self, raw):
        from tessellate.__main__ import _port_from_env

        assert _port_from_env(raw) == 8000

    def test_the_module_reads_the_environment(self, monkeypatch):
        """PORT is what the desktop paths and _run_server actually use."""
        import importlib

        monkeypatch.setenv("TESSELLATE_PORT", "8123")
        launcher = importlib.reload(importlib.import_module("tessellate.__main__"))
        try:
            assert launcher.PORT == 8123
        finally:
            monkeypatch.delenv("TESSELLATE_PORT", raising=False)
            importlib.reload(launcher)

    def test_start_sh_exports_the_variable_the_module_reads(self):
        assert re.search(r"export\s+TESSELLATE_PORT=", _read(START_SH))

    def test_start_bat_sets_the_variable_the_module_reads(self):
        assert 'set "TESSELLATE_PORT=!MM_PORT!"' in _read(START_BAT)


class TestTheShellScriptsParse:
    @pytest.mark.parametrize(
        "script",
        ["start.sh", "start-desktop.sh", "uninstall.sh", "doctor.sh", "reinstall.sh", "tools.sh"],
    )
    def test_bash_n(self, script):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / script)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr

    def test_they_are_executable(self):
        for script in (START_SH, START_DESKTOP_SH, UNINSTALL_SH, *ACTION_SH):
            assert os.access(script, os.X_OK), script


# --- the two launchers, read as one contract -------------------------------

FLAG_ORDER = [
    "desktop",
    "--port",
    "--no-browser",
    "--no-update",
    "--reinstall",
    "--doctor",
    "--logs",
    "--shortcut",
    "--version",
    "--help",
]


def _help_flags(text: str, start: str, end: str) -> list[str]:
    """The flags named in a help block, in the order they are printed."""
    at = text.index(start)
    body = text[at : text.index(end, at)]
    found = []
    for line in body.splitlines():
        # The flag, its optional single-letter argument placeholder, then
        # the column of description text.
        m = re.match(r"^\s*(?:echo\s+)?(--?[a-zA-Z-]+|desktop)(?:\s[A-Z])?\s{2,}\S", line)
        if m:
            found.append(m.group(1))
    return found


class TestOneLauncherTwoSpellings:
    """`start --doctor` has to be the same sentence on both platforms."""

    def test_the_help_texts_list_the_same_flags_in_the_same_order(self):
        sh = _help_flags(_read(START_SH), "Tessellate launcher", "MM_HELP\n}")
        bat = _help_flags(_read(START_BAT), "echo Tessellate launcher", "\n:log")
        assert sh == FLAG_ORDER, sh
        assert bat == FLAG_ORDER, bat

    def test_both_print_where_the_notes_are(self):
        assert "Your notes: $MM_DATA_DIR" in _read(START_SH)
        assert "Your notes: !MM_DATA_DIR!" in _read(START_BAT)

    def test_both_reject_an_unknown_flag_with_exit_2(self):
        assert "exit 2" in _read(START_SH)
        assert "exit /b 2" in _read(START_BAT)

    def test_both_point_at_their_own_uninstaller(self):
        assert "./uninstall.sh --help" in _read(START_SH)
        assert "uninstall.bat --help" in _read(START_BAT)


class TestStatusProtocol:
    """Every phase writes a `step|total|title|detail|state` line, or the
    splash renders a step list with a hole in it."""

    def test_the_two_scripts_use_the_same_phase_titles(self):
        sh = set(re.findall(r'mm_status "\$MM_STEP_\w+" "([^"]+)"', _read(START_SH)))
        bat = set(re.findall(r'call :status \S+ "([^"]+)"', _read(START_BAT)))
        assert sh, "start.sh writes no status lines at all"
        assert sh == bat, sh ^ bat

    def test_every_phase_is_covered(self):
        expected = {"Update", "Python", "Dependencies", "Desktop window", "Start"}
        sh = set(re.findall(r'mm_status "\$MM_STEP_\w+" "([^"]+)"', _read(START_SH)))
        assert expected <= sh, expected - sh

    def test_both_scripts_carry_the_same_step_totals(self):
        for text in (_read(START_SH), _read(START_BAT)):
            assert "MM_STEP_TOTAL=5" in text and "MM_STEP_TOTAL=4" in text

    def test_the_line_shape_is_the_one_the_parser_expects(self):
        from tessellate.core.launch_status import parse_line

        assert parse_line("2|5|Python|Building the environment|active") is not None

    def test_both_poll_the_same_cancel_file(self):
        assert "__cancel__" in _read(START_SH)
        assert "__cancel__" in _read(START_BAT)
        assert "${MM_SPLASH_FILE}.cancel" in _read(START_SH)
        assert "!MM_SPLASH_FILE!.cancel" in _read(START_BAT)


class TestBatchFileRules:
    """The cmd rules start.bat's own header records, checked rather than
    trusted: PowerShell and cmd cannot run in this suite, so a structural
    read is the only gate there is.
    """

    def _lines(self, path: Path = START_BAT):
        return _read(path).splitlines()

    @staticmethod
    def _unquoted(ln: str) -> str:
        out = re.sub(r'"[^"]*"', "", ln)
        # `echo(` is cmd's empty-safe echo, not an opening bracket, and `^(`
        # is an escaped literal.
        out = re.sub(r"(?i)\becho\(", "echo ", out)
        return out.replace("^(", "").replace("^)", "")

    @pytest.mark.parametrize("name", ["start.bat", "uninstall.bat", "start-desktop.bat", *ACTION_BAT])
    def test_no_parenthesis_inside_an_echo_within_a_block(self, name):
        """cmd reads the ) as the end of the block and the script dies."""
        depth = 0
        offenders = []
        for i, ln in enumerate(self._lines(ROOT / name), 1):
            if re.match(r"(?i)^\s*(rem\b|::)", ln):
                continue
            unquoted = self._unquoted(ln)
            if depth > 0 and re.match(r"(?i)^\s*echo[ (.]", ln.strip()):
                body = re.sub(r"(?i)^\s*echo\(", "", unquoted)
                if "(" in body or ")" in body:
                    offenders.append((i, ln.strip()[:80]))
            depth += unquoted.count("(") - unquoted.count(")")
        assert not offenders, offenders

    @pytest.mark.parametrize("name", ["start.bat", "uninstall.bat", "start-desktop.bat", *ACTION_BAT])
    def test_the_blocks_balance(self, name):
        depth = 0
        for ln in self._lines(ROOT / name):
            if re.match(r"(?i)^\s*(rem\b|::)", ln):
                continue
            depth += self._unquoted(ln).count("(") - self._unquoted(ln).count(")")
            assert depth >= 0, ln
        assert depth == 0

    @pytest.mark.parametrize("name", ["start.bat", "uninstall.bat", *ACTION_BAT])
    def test_every_goto_and_call_target_exists(self, name):
        text = _read(ROOT / name)
        labels = {
            m.group(1).lower() for m in re.finditer(r"(?m)^\s*:([A-Za-z_0-9]+)", text)
        }
        targets = {
            m.group(1).lower()
            for m in re.finditer(r"(?:^|\s)(?:goto|call)\s+:([A-Za-z_0-9]+)", text, re.I)
        }
        assert targets - labels - {"eof"} == set()

    def test_the_relaunch_guard_survives_the_new_flags(self):
        """A running .bat is read by byte offset, so the self-update has to
        relaunch a fresh copy; MM_CHILD is what stops that looping. It must
        also pass the flags on, which SHIFT would otherwise have eaten."""
        text = _read(START_BAT)
        assert 'set "MM_ARGS=%*"' in text
        assert 'call "!MM_SELF!" !MM_ARGS!' in text
        relaunch = text.index('call "!MM_SELF!"')
        assert "if defined MM_CHILD goto :after_update" in text[:relaunch]
        assert 'set "MM_CHILD=1"' in text[:relaunch]

    def test_the_port_flag_reads_its_value_before_shifting(self):
        """%1 inside a block is expanded when the block is parsed, so a
        SHIFT earlier in the same block does not move it."""
        text = _read(START_BAT)
        block = text[text.index('if /i "%~1"=="--port" (') :]
        block = block[: block.index("\n)")]
        assert block.index('set "MM_PORT=%~2"') < block.index("shift")

    def test_nothing_after_the_parser_reads_its_own_path_from_percent_zero(self):
        """SHIFT moves %0 with the rest, so after start-desktop.bat had passed
        --desktop, "%~f0" in the self-update relaunch expanded to
        "...\\MemoryMap-AI\\--desktop" and cmd reported it "is not recognized as
        an internal or external command". The path is captured once, before
        :parse_args, and only the captured copy is used after it."""
        text = _read(START_BAT)
        before, after = text.split("\n:parse_args\n", 1)
        assert 'set "MM_HOME=%~dp0"' in before and 'set "MM_SELF=%~f0"' in before
        offenders = [
            line for line in after.splitlines()
            if ("%~f0" in line or "%~dp0" in line) and not line.strip().upper().startswith("REM")
        ]
        assert offenders == [], offenders
        assert 'call "!MM_SELF!" !MM_ARGS!' in after

    def test_the_own_path_is_read_before_delayed_expansion_is_on(self):
        """%~dp0 and %~f0 are expanded when the line is parsed, and with
        delayed expansion on cmd then scans the result for "!": a folder named
        "Notes!" lost the character, and MM_HOME, MM_SELF and the cd named a
        folder that does not exist. Every line that reads the script's own
        path comes before the first enabledelayedexpansion, after an explicit
        disabledelayedexpansion."""
        lines = [
            line.strip().lower()
            for line in _read(START_BAT).splitlines()
            if not re.match(r"(?i)^\s*(rem\b|::)", line)
        ]
        on = next(i for i, line in enumerate(lines) if line.startswith("setlocal enabledelayedexpansion"))
        off = next(i for i, line in enumerate(lines) if line.startswith("setlocal disabledelayedexpansion"))
        own_path = [i for i, line in enumerate(lines) if "%~dp0" in line or "%~f0" in line]
        assert own_path, "the script no longer reads its own path"
        assert off < min(own_path) and max(own_path) < on, (off, own_path, on)

    def test_the_status_write_puts_the_redirect_first(self):
        """A value ending in a digit turns `echo !VAR!>>file` into a
        numbered stream redirect."""
        text = _read(START_BAT)
        assert '>>"!MM_SPLASH_FILE!" echo(!MM_ST_LINE!' in text
        assert '>>"!MM_LOG!" echo(' in text

    def test_python_one_liners_with_apostrophes_use_backquotes(self):
        """FOR /F ends a single-quoted command at the next apostrophe, so a
        Python one-liner full of them needs `usebackq` and backticks."""
        for ln in self._lines():
            m = re.search(r"for /f [^(]*\('(.*)'\)", ln)
            if m and "'" in m.group(1):
                pytest.fail(f"apostrophe inside a single-quoted FOR /F: {ln.strip()}")


class TestDesktopWrappers:
    """Item 4: both wrappers exist and pass their arguments through, so
    `start-desktop --port 8010` is not silently a plain `desktop`."""

    def test_the_shell_wrapper_execs_the_launcher_with_its_arguments(self):
        text = _read(START_DESKTOP_SH)
        assert 'cd "$(dirname "$0")"' in text
        assert './start.sh --desktop "$@"' in text

    def test_the_batch_wrapper_passes_everything_through(self):
        assert 'start.bat" --desktop %*' in _read(START_DESKTOP_BAT)


class TestUninstallers:
    """Item 5: the same flag set, and the guards that stop an uninstall
    deleting under a running app."""

    UNINSTALL_FLAGS = [
        "--dry-run",
        "--export",
        "--delete-data",
        "--shortcuts",
        "--yes",
        "--help",
    ]

    def test_both_take_the_same_flags(self):
        sh, bat = _read(UNINSTALL_SH), _read(UNINSTALL_BAT)
        for flag in self.UNINSTALL_FLAGS:
            assert flag in sh, flag
            assert flag in bat, flag

    def test_both_check_the_port_before_deleting(self):
        assert "mm_port_open" in _read(UNINSTALL_SH)
        assert ":port_check" in _read(UNINSTALL_BAT)

    def test_env_is_only_removed_with_delete_data(self):
        """.env carries settings someone chose; a reinstall should find them
        again unless the notes are going too."""
        sh = _read(UNINSTALL_SH)
        # The only rm of .env sits inside the DELETE confirmation, after the
        # notes have gone: .env carries the path to the notebook, so
        # removing it while the notes survive loses them.
        removals = [
            ln for ln in sh.splitlines() if re.search(r'rm -f "\.env"', ln)
        ]
        assert len(removals) == 1, removals
        at = sh.index(removals[0])
        assert sh.index('if [ "$DELETE_DATA" = "1" ]; then', sh.index("--- 3.")) < at
        assert sh.index('reply" = "DELETE"') < at

        bat = _read(UNINSTALL_BAT)
        bat_removals = [ln for ln in bat.splitlines() if 'del /q ".env"' in ln]
        assert len(bat_removals) == 1, bat_removals
        assert bat.index('if not "!REPLY!"=="DELETE"') < bat.index(bat_removals[0])

    def test_the_export_entry_point_exists(self):
        text = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")
        assert "--export" in text


class TestTheDoctorRunsHere:
    """`./start.sh --doctor` is run for real: it is the one part of this
    contract Linux CI can actually execute."""

    def test_it_exits_0_or_1_and_prints_the_table(self, tmp_path):
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(tmp_path / "data"))
        env.pop("TESSELLATE_PORT", None)
        result = subprocess.run(
            ["./start.sh", "--doctor"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode in (0, 1), result.stdout + result.stderr
        out = result.stdout
        # Every assertion below carries the whole table: this failed once,
        # under a full suite running beside it, and did not reproduce in
        # forty runs afterwards, so the next occurrence needs to arrive
        # with its own evidence rather than a bare label name.
        assert "Tessellate - checks" in out, out + result.stderr
        for label in ("Python", ".venv", "Disk", "Port", "Updates", "Notes", "Last run"):
            assert label in out, f"{label} missing from:\n{out}"
        assert "[ok]" in out or "[x]" in out, out

    def test_an_unknown_flag_exits_2_with_the_help(self, tmp_path):
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(tmp_path / "data"))
        result = subprocess.run(
            ["./start.sh", "--no-browsr"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 2
        assert "Unknown option: --no-browsr" in result.stdout
        assert "--no-browser" in result.stdout

    @pytest.mark.parametrize("bad", ["abc", "0", "70000"])
    def test_a_bad_port_exits_2(self, bad, tmp_path):
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(tmp_path / "data"))
        result = subprocess.run(
            ["./start.sh", "--port", bad],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 2, result.stdout

    def test_version_prints_the_version_and_the_paths(self, tmp_path):
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(tmp_path / "data"))
        result = subprocess.run(
            ["./start.sh", "--version"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert "Tessellate" in result.stdout
        assert "Your notes:" in result.stdout


class TestSelfRepairStructure:
    """INBOX 253's "no prompt" requirement, read as text first: the fast,
    deterministic half of the gate, run on every `--changed` pass. The slow
    half (a real broken venv actually coming back) is `TestSelfRepair`
    below, which this class does not replace - a comment that says the
    right words is not a script that does the right thing.
    """

    def test_both_scripts_repair_once_and_stop(self):
        for text in (_read(START_SH), _read(START_BAT)):
            assert "MM_AUTO_REPAIRED" in text
            # The loop guard: an already-repaired run that is still broken
            # fails with a real message instead of repairing forever.
            assert text.count("MM_AUTO_REPAIRED") >= 4, text.count(
                "MM_AUTO_REPAIRED"
            )

    def test_both_scripts_check_the_real_import_chain(self):
        """`import tessellate` alone (src/tessellate/__init__.py) never fails
        just because a real dependency like python-dotenv is gone - it is a
        five-line package with no imports of its own. `tessellate.api.app`
        is what `python -m tessellate` actually loads first, so it is the
        only check that can see a missing dependency at all."""
        for text in (_read(START_SH), _read(START_BAT)):
            assert "import tessellate.api.app" in text
            # The old, shallow check may still be named in a comment
            # explaining why it was not enough; it must not still be a
            # command anywhere.
            assert '-c "import fastapi, sqlalchemy, memorymap"' not in text

    def test_start_sh_reexecs_with_the_arguments_it_was_given(self):
        """Every `shift` in the flag-parsing loop above consumes "$@" one
        argument at a time, down to nothing - by the time any `exec "$0"
        "$@"` below it ran, `--no-browser` (and everything else that is not
        an exported environment variable) had already been silently
        dropped. Reproduced directly: a self-repair triggered under
        `--no-browser` popped a browser tab open anyway. MM_ORIG_ARGS is
        captured once, before that loop, and is what every re-exec below
        must use instead."""
        text = _read(START_SH)
        captured_at = text.index('MM_ORIG_ARGS=("$@")')
        loop_at = text.index("while [ $# -gt 0 ]; do")
        assert captured_at < loop_at
        # Code lines only - line 32's own comment quotes the broken form
        # (`exec "$0" "$@"`) as the bug this capture fixes, on purpose.
        reexecs = [
            ln.strip()
            for ln in text.splitlines()
            if re.match(r'^\s*exec "\$0"', ln) and not ln.strip().startswith("#")
        ]
        assert reexecs, "start.sh has no self-relaunch left to check"
        for line in reexecs:
            assert line == 'exec "$0" "${MM_ORIG_ARGS[@]}"', line

    def test_start_bat_relaunches_carry_mm_args(self):
        """start.bat's own MM_ARGS (captured from %* before :parse_args,
        see TestBatchFileRules) is the same fix already in place there;
        the two self-repair relaunches just have to keep using it."""
        text = _read(START_BAT)
        assert text.count('call "!MM_SELF!" !MM_ARGS!') >= 3


class TestSelfRepair:
    """INBOX 253, the owner verbatim: "the app needs to work even if it
    cant update or isnt available to the internet, and it needs to be
    automatically recoverable and revivable for the user with one click."

    Run against a copy of this sandbox's own real .venv, but with `pip`
    itself replaced by a two-line stub (`_fake_pip`) before start.sh ever
    runs: `tests/conftest.py`'s `_no_test_runs_pip` fixture refuses any
    subprocess whose argv mentions "pip", on purpose (its own docstring:
    one test once carried a real `pip install sentence-transformers` for
    twenty minutes), and that guard has to hold for what a *shell script*
    spawns just as much as for what Python spawns directly - the fixture
    cannot see inside start.sh's own child processes to enforce it there,
    so this class enforces it by construction instead: there is no real
    pip left in the scratch copy to reach. The stub still exercises the
    thing this gate is actually about - start.sh's own detection, its
    single automatic retry, and the flags it carries across the retry -
    against a real subprocess, a real broken import, and a real server
    that either comes back up or does not.

    Skipped where no real .venv exists to copy from - a sandbox with
    nothing built has nothing to prove this against.

    Confirmed against the pre-fix start.sh before this class existed: the
    same broken venv below produced a bare `ModuleNotFoundError: No module
    named 'dotenv'` traceback and exit 1, no repair, because the existing
    NEED_INSTALL marker check only asks "did requirements.txt's hash
    change", and the existing relink check only asks "does `import
    tessellate` work" - neither one imports the dependency that was
    actually deleted.
    """

    def _main_venv(self) -> Path | None:
        try:
            common = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "--git-common-dir"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except OSError:
            return None
        if common.returncode != 0 or not common.stdout.strip():
            return None
        git_dir = (ROOT / common.stdout.strip()).resolve()
        venv = git_dir.parent / ".venv"
        return venv if (venv / "bin" / "python").exists() else None

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @staticmethod
    def _site_packages(venv: Path) -> Path:
        (site_packages,) = (venv / "lib").glob("python3.*/site-packages")
        return site_packages

    def _fake_pip(self, site_packages: Path) -> None:
        """Replaces the real `pip` package with a stub that never touches
        the network: every `install` call prints one line and exits 0,
        after restoring whatever this test stashed with `_break_dependency`
        below (the `install -r requirements.txt` step 2 runs for real,
        exactly as production start.sh does - only pip's own idea of
        "install" is faked). `python -m pip ...`, which is the only way
        start.sh ever invokes it, resolves `pip` off `sys.path` the same
        way any other import does, so replacing the package is enough;
        nothing calls the `pip` console-script directly.
        """
        real_pip = site_packages / "pip"
        for dist_info in site_packages.glob("pip-*.dist-info"):
            shutil.rmtree(dist_info)
        if real_pip.exists():
            shutil.rmtree(real_pip)
        real_pip.mkdir()
        (real_pip / "__init__.py").write_text(
            '"""Stub pip - tests/conftest.py refuses the real one."""\n',
            encoding="utf-8",
        )
        (real_pip / "__main__.py").write_text(
            '''import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    if "install" in sys.argv[1:]:
        stash = os.environ.get("MM_TEST_RESTORE_FROM")
        target = os.environ.get("MM_TEST_RESTORE_TO")
        if stash and target and Path(stash).is_dir():
            for entry in Path(stash).iterdir():
                dest = Path(target) / entry.name
                if not dest.exists():
                    if entry.is_dir():
                        shutil.copytree(entry, dest)
                    else:
                        shutil.copy2(entry, dest)
        print("Requirement already satisfied: fake-pip stub for launcher tests")
    sys.exit(0)


if __name__ == "__main__":
    main()
''',
            encoding="utf-8",
        )

    def _healthy_scratch(self, tmp_path: Path, main_venv: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        shutil.copy2(ROOT / "start.sh", repo / "start.sh")
        (repo / "start.sh").chmod(0o755)
        for name in ("src", "frontend", "migrations"):
            shutil.copytree(ROOT / name, repo / name)
        for name in ("alembic.ini", "pyproject.toml", "requirements.txt", ".env.example"):
            shutil.copy2(ROOT / name, repo / name)
        shutil.copytree(main_venv, repo / ".venv", symlinks=True)
        venv_py = repo / ".venv" / "bin" / "python"
        site_packages = self._site_packages(repo / ".venv")
        self._fake_pip(site_packages)
        # What a real `pip install -e .` would leave behind: the scratch
        # source tree on sys.path, done here with a plain .pth file rather
        # than pip (this sandbox runs the real app the same way, with
        # PYTHONPATH=src rather than an editable install - CLAUDE.md
        # section 7 - so nothing about production behaviour is skipped by
        # doing it directly instead of through the now-fake installer).
        (site_packages / "mm_test_editable.pth").write_text(
            str(repo / "src") + "\n", encoding="utf-8"
        )
        req_hash = subprocess.run(
            ["cksum", "requirements.txt"], cwd=repo, capture_output=True, text=True, check=True
        ).stdout.split()[0]
        (repo / ".venv" / ".mm_installed").write_text(req_hash, encoding="utf-8")
        healthy = subprocess.run(
            [str(venv_py), "-c", "import tessellate.api.app"], capture_output=True
        )
        assert healthy.returncode == 0, "the scratch venv is not healthy before this test even breaks it"
        return repo

    def _break_dependency(self, repo: Path, tmp_path: Path) -> None:
        """The smallest real dependency in requirements.txt, moved aside
        (not deleted outright) so the fake pip above can put it straight
        back the moment start.sh's own step 2 asks it to "install". Moved,
        not `memorymap` itself: deleting `memorymap` is exactly what the
        pre-existing relink check already catches (`import tessellate`
        alone succeeds no matter which real dependency is gone - it is a
        five-line package with no imports of its own) - this is the gap
        that check has, which this self-repair closes.
        """
        site_packages = self._site_packages(repo / ".venv")
        stash = tmp_path / "dependency_stash"
        stash.mkdir()
        moved = 0
        for pattern in ("dotenv", "python_dotenv*"):
            for entry in site_packages.glob(pattern):
                moved += 1
                shutil.move(str(entry), str(stash / entry.name))
        assert moved >= 2, "python-dotenv was not where this test expected it"
        venv_py = repo / ".venv" / "bin" / "python"
        broken = subprocess.run(
            [str(venv_py), "-c", "import tessellate.api.app"], capture_output=True
        )
        assert broken.returncode != 0, "moving dotenv aside did not actually break the import"
        return stash

    def _run(self, repo: Path, stash: Path, port: int, **extra_env: str) -> subprocess.Popen:
        env = dict(
            os.environ,
            TESSELLATE_DATA_DIR=str(repo / "data"),
            TESSELLATE_PORT=str(port),
            MM_TEST_RESTORE_FROM=str(stash),
            MM_TEST_RESTORE_TO=str(self._site_packages(repo / ".venv")),
            **extra_env,
        )
        return subprocess.Popen(
            ["./start.sh", "--no-browser", "--no-update"],
            cwd=repo,
            env=env,
            # DEVNULL, not a pipe with nothing written to it: a script that
            # ever actually tried to prompt would block reading from a pipe
            # forever (a timeout, indistinguishable from any other hang);
            # against /dev/null a stray read gets EOF immediately, which is
            # what "no prompt" has to mean for an automated check to say it.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def test_a_deleted_dependency_is_repaired_with_no_prompt(self, tmp_path):
        main_venv = self._main_venv()
        if main_venv is None:
            pytest.skip("no real .venv in this sandbox to copy from")
        repo = self._healthy_scratch(tmp_path, main_venv)
        stash = self._break_dependency(repo, tmp_path)

        port = self._free_port()
        proc = self._run(repo, stash, port)
        up = False
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/", timeout=2
                    ) as resp:
                        up = resp.status == 200
                        break
                except (OSError, urllib.error.URLError):
                    time.sleep(1)
        finally:
            proc.terminate()
            try:
                out = proc.communicate(timeout=15)[0]
            except subprocess.TimeoutExpired:
                proc.kill()
                out = proc.communicate(timeout=15)[0]

        assert up, "the app never came back up after the automatic repair:\n" + out
        # Repaired once, not in a loop, and said so in one line.
        assert out.count("looks broken - reinstalling") == 1, out
        # The flag this run was started with survived the repair's own
        # relaunch (see TestSelfRepairStructure.
        # test_start_sh_reexecs_with_the_arguments_it_was_given).
        assert "No browser will be opened (--no-browser)" in out, out

    def test_a_repair_that_does_not_fix_it_fails_once_with_no_loop(self, tmp_path):
        """MM_AUTO_REPAIRED pre-set is the same state the script leaves
        itself in after its own first repair attempt - this is what a
        SECOND, still-broken run does, without a real second `exec` in the
        way of watching it happen. No restore stash on purpose: the point
        is that this run's own repair attempt (if it wrongly tried one)
        would find nothing to fix."""
        main_venv = self._main_venv()
        if main_venv is None:
            pytest.skip("no real .venv in this sandbox to copy from")
        repo = self._healthy_scratch(tmp_path, main_venv)
        self._break_dependency(repo, tmp_path)

        result = subprocess.run(
            ["./start.sh", "--no-browser", "--no-update"],
            cwd=repo,
            env=dict(
                os.environ,
                TESSELLATE_DATA_DIR=str(repo / "data"),
                TESSELLATE_PORT=str(self._free_port()),
                MM_AUTO_REPAIRED="1",
            ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 1, result.stdout
        out = result.stdout
        assert "did not fix it" in out, out
        assert "Log:" in out, out
        assert "Checks: ./start.sh --doctor" in out, out
        # Not a second attempt: the loop guard has to stop it here, once.
        assert "looks broken - reinstalling" not in out, out


class TestTheWindowsSplash:
    """scripts/splash.ps1 cannot be run here: no PowerShell, no WinForms, no
    display. So it is read instead, for the things Brief 17 asks it to draw
    and for the regressions its own comments record.
    """

    @property
    def text(self) -> str:
        return _read(ROOT / "scripts" / "splash.ps1")

    def test_the_braces_balance(self):
        """The one structural error a read can catch. Counted outside
        strings and comments, which is where every brace in this file that
        is not a block actually lives."""
        depth = 0
        for raw in self.text.splitlines():
            line = re.sub(r"'[^']*'", "", raw)
            line = re.sub(r'"[^"]*"', "", line)
            line = re.sub(r"#.*$", "", line)
            depth += line.count("{") - line.count("}")
            assert depth >= 0, raw
        assert depth == 0

    def test_the_window_keeps_one_size_however_many_steps_finish(self):
        """C02, then INBOX 1301 D2 (the owner: the splash "is still pushing
        down to the bottom of the screen every step completed"). It was
        centred at 252px and grew downwards, a row per step and the log under
        them. Now nothing assigns its height after creation: the rows are a
        fixed panel and Details swaps the log into it. Not verified on
        Windows."""
        t = self.text
        assert "$form.Size            = New-Object System.Drawing.Size($WIDTH, $HEIGHT)" in t
        assert "$form.Height =" not in t and "$form.Height=" not in t
        assert t.count("New-RoundRegion $WIDTH") == 1, "the region is cut once, at the one size"
        layout = t[t.index("  function Set-Layout {") : t.index("  Set-Layout\n")]
        assert "Size" not in layout.replace("SuspendLayout", "").replace("ResumeLayout", "")
        assert "$on = -not $details.Visible" in layout, "the log replaces the rows, in place"
        assert "$list.Controls.Add($details)" in t
        rows = t[t.index("  function Update-Rows($steps) {") : t.index("  function Update-Hint($steps) {")]
        assert "$first = [Math]::Max(0, $all.Count - $MAX_ROWS)" in rows
        assert "$all[$first + $i]" in rows
        #: Centred in the working area before it shows (a Shown handler that
        #: moved it was a visible jump, 2026-10-26), and drawn only once the
        #: first status read has filled it.
        placed = t[t.index('$form.StartPosition   = "Manual"') : t.index("$form.Opacity         = 0")]
        assert "WorkingArea" in placed and "[Math]::Max(0, ($area.Height - $HEIGHT) / 2)" in placed
        shown = t[t.index("  $form.Add_Shown({") :].split("})")[0]
        assert "& $refresh" in shown and "$form.Opacity = 1" in shown

    def test_it_says_which_step_of_how_many(self):
        t = self.text
        assert '$counted = "Step $([Math]::Min($total, $done + 1)) of $total"' in t
        assert '$count.Text = "Stopped at step $($step.Step) of $($step.Total)"' in t

    def test_it_does_not_repaint_what_did_not_change(self):
        """C38: "the splash popup flickers quite a bit". The form is double
        buffered, the layout is skipped when its inputs are the same as last
        tick, labels are written only when different, and row updates sit in
        one Suspend/ResumeLayout. Not verified on Windows."""
        t = self.text
        assert '"DoubleBuffered"' in t and "SetValue($form, $true, $null)" in t
        layout = t[t.index("  function Set-Layout {") : t.index("  Set-Layout\n")]
        assert "if ($key -eq $st.layoutKey) { return }" in layout
        assert "$form.SuspendLayout()" in layout and "$form.ResumeLayout($true)" in layout
        rows = t[t.index("  function Update-Rows($steps) {") : t.index("  function Update-Hint($steps) {")]
        assert "$form.SuspendLayout()" in rows and "$form.ResumeLayout($true)" in rows
        assert "if ($label.Text -ne $text) { $label.Text = $text }" in t
        assert "if ($hint.Text -ne $text) { $hint.Text = $text }" in t

    def test_it_parses_the_protocol_not_the_last_line_as_text(self):
        """Between the protocol landing and this, the window showed a raw
        `1|5|Update|...|active` line as its status text."""
        t = self.text
        assert "-split '\\|'" in t
        assert "$parts.Count -lt 5" in t
        assert '$state -ne "active"' in t

    def test_it_draws_a_step_list_with_marks(self):
        t = self.text
        assert "0x2713" in t  # tick, done
        assert "0x00D7" in t  # cross, failed
        assert "0x25CF" in t  # dot, active
        assert "$rowName" in t and "$rowDetail" in t

    def test_the_one_bar_counts_finished_steps_in_the_app_accent(self):
        """Brief 85: a stock ProgressBar was green under the system theme and
        a Marquee bar white beside it. One hand-painted bar in the accent."""
        t = self.text
        assert "$progress" not in t and "$bar." not in t
        assert "$barFill.BackColor = $accent" in t
        assert '$_.State -eq "done"' in t
        assert "$pct = [int](($done * 100) / $total)" in t

    def test_the_mark_is_decoded_before_the_window_is_shown(self):
        """The icon used to appear about a second after the window."""
        t = self.text
        assert t.index("$logoBmp = New-LogoBitmap") < t.index("ShowDialog()")
        assert "DrawImage($logoBmp" in t

    def test_the_mark_is_the_three_cell_logo_not_the_old_nodes(self):
        t = self.text
        assert "35.3,48.7" in t and "57.3,18.4" in t  # favicon.svg cells
        assert "78.5, 40.7" not in t  # the old five-node ring

    def test_the_tagline_and_a_borderless_rounded_window(self):
        t = self.text
        assert '"Your notes, pieced together"' in t
        assert '$form.FormBorderStyle = "None"' in t
        assert "New-RoundRegion" in t

    def test_the_links_and_the_list_show_at_once(self):
        """The list waited a second and then grew the window; since INBOX
        1301 D2 it is the fixed panel, there from the first frame."""
        t = self.text
        assert "$SHOW_LINKS_AFTER = 0" in t
        assert "SHOW_LIST_AFTER" not in t and "showList" not in t
        assert "$st.failed" in t

    def test_the_active_step_shows_its_elapsed_seconds(self):
        assert "TotalSeconds" in self.text
        assert '$($secs)s' in self.text

    def test_there_are_five_tips_and_they_rotate_every_six_seconds(self):
        t = self.text
        block = t[t.index("$tips = @(") : t.index("$tip  ", t.index("$tips = @("))]
        quoted = re.findall(r'^\s*"[^"]+",?\s*$', block, re.M)
        assert len(quoted) == 4, quoted  # the fifth is the data folder, below
        assert "as plain files you can copy" in t
        assert "TotalSeconds -ge 6" in t

    def test_the_footer_has_all_three_links(self):
        t = self.text
        assert 'New-FooterLink "Details"' in t
        assert 'New-FooterLink "Copy diagnostics"' in t
        assert 'New-FooterLink "Cancel"' in t

    def test_cancel_writes_the_control_file_the_launcher_polls(self):
        t = self.text
        assert '$StatusFile + ".cancel"' in t
        assert '"__cancel__"' in t

    def test_the_slow_step_hints_name_both_steps_and_their_budgets(self):
        t = self.text
        assert '$s.Title -eq "Dependencies" -and $secs -gt 300' in t
        assert '$s.Title -eq "Update" -and $secs -gt 30' in t

    def test_the_error_card_offers_the_log_and_a_retry(self):
        t = self.text
        assert "function Show-ErrorCard" in t
        assert '$btnDetails.Text = "Open log"' in t
        assert 'New-FooterLink "Try again"' in t
        assert "Start-Process -FilePath $LauncherPath" in t

    def test_the_three_ways_to_die_survive(self):
        t = self.text
        assert "MaxMinutes" in t
        assert "Test-Path -LiteralPath $StatusFile" in t
        assert "__done__" in t

    def test_one_click_handler_per_button(self):
        """WinForms runs every handler on a button: a second Add_Click added
        later fires alongside the first, so "Open log" would also toggle the
        details panel."""
        t = self.text
        for name in ("$btnDetails", "$btnCancel", "$btnCopy"):
            assert t.count(f"{name}.Add_Click(") == 1, name

    def test_the_launcher_passes_the_new_arguments(self):
        bat = _read(START_BAT)
        for flag in ("-StatusFile", "-IconPath", "-LogPath", "-LauncherPath", "-DataDir"):
            assert flag in bat, flag


class TestTheBrowserBootSplash:
    def test_it_carries_a_tip_line_in_the_markup(self):
        """In the markup, not built by boot-guard.js: it has to be there
        before first paint and survive a script that never runs, which is
        the case boot-guard.js itself exists for."""
        html = _read(ROOT / "frontend" / "index.html")
        assert 'class="boot-splash-tip"' in html
        assert "Your notes never leave this machine." in html

    def test_the_tip_line_is_styled_in_the_first_stylesheet(self):
        css = _read(ROOT / "frontend" / "css" / "00-tokens-shell.css")
        assert ".boot-splash-tip {" in css

    def test_still_loading_appears_at_eight_seconds_with_the_way_out(self):
        js = _read(ROOT / "frontend" / "js" / "boot-guard.js")
        at = js.index("}, 8000);")
        block = js[js.rindex("setTimeout(", 0, at) : at]
        assert "Still loading" in block
        assert "offerReload(splash)" in block
        # And the 12-second notice is still there, saying something else.
        assert "}, 12000);" in js
        assert "taking longer than it should" in js


class TestOneDesignThreeSurfaces:
    """The tips and the marks are the same on all three, or a first run
    reads as three different programs."""

    def test_the_same_tips_appear_on_every_surface(self):
        main = _read(ROOT / "src" / "tessellate" / "__main__.py")
        ps1 = _read(ROOT / "scripts" / "splash.ps1")
        html = _read(ROOT / "frontend" / "index.html")
        shared = "Your notes never leave this machine."
        assert shared in main and shared in ps1 and shared in html
        for tip in (
            "Ctrl+K opens the command palette.",
            "The first run installs about 300 MB once. Later starts take seconds.",
        ):
            assert tip in main, tip
            assert tip in ps1, tip

    def test_the_loading_window_seeds_itself_from_the_launcher(self):
        main = _read(ROOT / "src" / "tessellate" / "__main__.py")
        assert "def _loading_html" in main
        assert "launch_status.read_file" in main
        # Read before _close_launch_splash deletes the file: create_window's
        # own argument list is the only place that is guaranteed.
        assert main.index("html=_loading_html()") < main.index("_close_launch_splash()\n    #")

    def test_reduced_motion_is_respected_on_the_python_window(self):
        main = _read(ROOT / "src" / "tessellate" / "__main__.py")
        assert "prefers-reduced-motion: reduce" in main
        assert "animation: none" in main


class TestTheSplashLayoutDoesNotOverlap:
    """The one thing a read can check about a window nothing here can draw.

    Every control in splash.ps1 is absolutely positioned, so a band that
    starts before the one above it ends is a control drawn on top of
    another. It happened once already: the status label was 34px tall at
    y=306 and ran under the footer buttons at y=336. Since INBOX 1301 D2 the
    window has one height, so every band also has to end inside it.
    """

    HEIGHTS = {  # control -> its own height, from the Size line beside it
        "hint": 18,
        "tip": 18,
        "status": 20,
    }

    def _ps1(self) -> str:
        return _read(ROOT / "scripts" / "splash.ps1")

    def _y(self, name: str) -> int:
        m = re.search(
            r"\$" + name + r"\.Location\s*=\s*New-Object System\.Drawing\.Point\(\d+, (\d+)\)",
            self._ps1(),
        )
        assert m, name
        return int(m.group(1))

    def _int(self, pattern: str) -> int:
        m = re.search(pattern, self._ps1())
        assert m, pattern
        return int(m.group(1))

    def test_the_bands_are_in_order_and_fit_the_one_height(self):
        rows = self._int(r"\$MAX_ROWS\s*=\s*(\d+)")
        row_top = self._int(r"\$ROW_TOP\s*=\s*(\d+)")
        step = self._int(r"\$ROW_STEP\s*=\s*(\d+)")
        panel_top = self._int(r"\$PANEL_TOP\s*=\s*(\d+)")
        panel_h = self._int(r"\$PANEL_H\s*=\s*(\d+)")
        height = self._int(r"\$HEIGHT\s*=\s*(\d+)")
        bar = self._int(r"\$barTrack\.Location = New-Object System\.Drawing\.Point\(\$BAR_X, (\d+)\)")
        links = self._int(
            r"\$b\.Location\s*=\s*New-Object System\.Drawing\.Point\(\$x, (\d+)\)"
        )
        bands = [
            ("status", self._y("status"), self._y("status") + self.HEIGHTS["status"]),
            ("bar", bar, bar + 4),
            ("steps", panel_top, panel_top + panel_h),
            ("hint", self._y("hint"), self._y("hint") + self.HEIGHTS["hint"]),
            ("tip", self._y("tip"), self._y("tip") + self.HEIGHTS["tip"]),
            ("links", links, links + 20),
        ]
        for (name_a, _, end_a), (name_b, start_b, _) in zip(bands, bands[1:]):
            assert end_a <= start_b, name_a + " runs into " + name_b
        assert bands[-1][2] <= height, "the links row ends inside the window"
        # Every row, and the log that takes their place, inside the panel.
        assert row_top + rows * step <= panel_h
        assert "$details.Size         = New-Object System.Drawing.Size(($BAR_W - 20), ($PANEL_H - 16))" in self._ps1()

    def test_the_retry_link_shares_the_links_row(self):
        assert "$btnRetry   = New-FooterLink" in self._ps1()

    def test_rows_past_the_end_are_blanked_not_left_stale(self):
        """The marquee is moved to the active row, and a list longer than
        MAX_ROWS would otherwise park it beyond the last row that exists."""
        ps1 = self._ps1()
        assert "($first + $i) -ge $all.Count" in ps1


class TestAFlagMissingItsValue:
    """A flag that takes a value shifts once inside its own branch, so
    `--port` or `--export` typed as the last argument leaves nothing for the
    loop's own shift to consume. Under `set -e` that failing shift killed
    the script with exit 1 and no message at all, instead of reaching the
    validation that prints the help and exits 2. Found by running it.
    """

    def _run(self, script: str, args: list[str], tmp_path):
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(tmp_path / "data"))
        env.pop("TESSELLATE_PORT", None)
        # The uninstaller runs in a scratch copy even for a flag that should
        # fail before it removes anything: "should" is the word this module
        # once got wrong (see `_repo_venv_is_not_a_fixture`).
        cwd = _scratch_repo(tmp_path) if script == "uninstall.sh" else ROOT
        return subprocess.run(
            ["./" + script, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_start_sh_port_with_no_value(self, tmp_path):
        result = self._run("start.sh", ["--port"], tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "--port needs a number" in result.stdout
        assert "Tessellate launcher" in result.stdout

    def test_uninstall_sh_export_with_no_value(self, tmp_path):
        result = self._run("uninstall.sh", ["--export"], tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "--export needs a path" in result.stdout

    def test_uninstall_sh_export_swallowing_the_next_flag(self, tmp_path):
        """`--export --yes` used to export to a file called "--yes"."""
        result = self._run("uninstall.sh", ["--export", "--yes"], tmp_path)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "--export needs a path" in result.stdout

    def test_both_loops_tolerate_the_empty_shift(self):
        for script in (START_SH, UNINSTALL_SH):
            assert "shift || break" in _read(script), script


class TestTheDesktopShortcut:
    """`./start.sh --shortcut` is run for real against a scratch HOME, and
    `./uninstall.sh --shortcuts` has to remove exactly what it wrote.
    """

    def _env(self, home, tmp_path):
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["TESSELLATE_DATA_DIR"] = str(tmp_path / "data")
        # Nothing must be able to look like a running Tessellate and stop the
        # uninstaller half way through this test.
        env["TESSELLATE_PORT"] = "9"
        return env

    def test_it_writes_an_entry_and_the_uninstaller_removes_it(self, tmp_path):
        home = tmp_path / "home"
        (home / "Desktop").mkdir(parents=True)
        env = self._env(home, tmp_path)
        repo = _scratch_repo(tmp_path)

        made = subprocess.run(
            ["./start.sh", "--shortcut"], cwd=repo, env=env,
            capture_output=True, text=True, timeout=60,
        )
        assert made.returncode == 0, made.stdout + made.stderr
        entry = home / ".local" / "share" / "applications" / "memorymap-ai.desktop"
        copy = home / "Desktop" / "memorymap-ai.desktop"
        assert entry.exists() and copy.exists()

        body = entry.read_text(encoding="utf-8")
        assert "Exec=" in body and "--desktop" in body
        assert "Terminal=false" in body  # the case the splash exists for
        icon = re.search(r"^Icon=(.+)$", body, re.M).group(1)
        # Icon=frontend/icon.png was written for a file that has never
        # existed in this repo, so both entries fell back to a generic icon.
        assert Path(icon).exists(), icon

        removed = subprocess.run(
            ["./uninstall.sh", "--shortcuts", "--yes"], cwd=repo, env=env,
            capture_output=True, text=True, timeout=60,
        )
        assert removed.returncode == 0, removed.stdout + removed.stderr
        assert not entry.exists() and not copy.exists()

    def test_the_dry_run_lists_the_shortcut_and_removes_nothing(self, tmp_path):
        home = tmp_path / "home"
        (home / "Desktop").mkdir(parents=True)
        env = self._env(home, tmp_path)
        repo = _scratch_repo(tmp_path)
        subprocess.run(
            ["./start.sh", "--shortcut"], cwd=repo, env=env,
            capture_output=True, text=True, timeout=60,
        )
        entry = home / ".local" / "share" / "applications" / "memorymap-ai.desktop"
        dry = subprocess.run(
            ["./uninstall.sh", "--shortcuts", "--dry-run"], cwd=repo, env=env,
            capture_output=True, text=True, timeout=60,
        )
        assert dry.returncode == 0, dry.stdout + dry.stderr
        assert str(entry) in dry.stdout
        assert "dry run" in dry.stdout
        assert entry.exists()


class TestBothUninstallersRejectAnExportWithNoPath:
    """`--export` with nothing after it used to fall through as "no export
    asked for": the uninstall then carried on and removed .venv while the
    export nobody noticed was skipped. The shell one is run for this in
    TestAFlagMissingItsValue; cmd cannot be run here, so the batch one is
    read for the same three decisions.
    """

    def test_the_batch_file_separates_absent_from_empty(self):
        bat = _read(UNINSTALL_BAT)
        assert 'set "EXPORT_GIVEN=1"' in bat
        assert "if not defined EXPORT_GIVEN goto :export_ok" in bat
        assert "if not defined EXPORT_TO goto :export_missing" in bat

    def test_the_batch_file_rejects_the_next_flag_as_a_path(self):
        assert 'if "!EXPORT_TO:~0,1!"=="-" goto :export_missing' in _read(UNINSTALL_BAT)

    def test_it_exits_2_before_removing_anything(self):
        bat = _read(UNINSTALL_BAT)
        # The label definitions, not the gotos that jump to them.
        missing = re.search(r"(?m)^:export_missing$", bat).start()
        ok = re.search(r"(?m)^:export_ok$", bat).start()
        # The guard sits above every removal in the file.
        for removal in ('rmdir /s /q ".venv"', 'rmdir /s /q ".pytest_cache"'):
            assert missing < bat.index(removal), removal
        assert "exit /b 2" in bat[missing:ok]

    def test_both_say_the_same_thing(self):
        assert "--export needs a path" in _read(UNINSTALL_SH)
        assert "--export needs a path" in _read(UNINSTALL_BAT)


def test_the_self_update_relaunch_cannot_run_an_empty_command():
    """Reported with a screenshot: "Checking for updates..." then
    `'""' is not recognized as an internal or external command` and
    "Tessellate has stopped".

    That is the self-update relaunch with `MM_SELF` empty: cmd reports the
    empty program name and the script exits, so the app never starts. The
    update has already landed on disk by then, so the repair is to skip the
    relaunch and carry on launching this copy rather than to die.
    """
    start_bat = (ROOT / "start.bat").read_text(encoding="utf-8", errors="replace")
    relaunch = start_bat.index('call "!MM_SELF!" !MM_ARGS!')
    guard = start_bat.rindex("if not defined MM_SELF (", 0, relaunch)
    between = start_bat[guard:relaunch]
    assert "goto :after_update" in between, (
        "the empty-MM_SELF guard must carry on with the launch, not fall "
        "through to the call it is guarding"
    )


def test_the_windows_launchers_use_crlf():
    """`call :label` in an LF-only batch file cannot find its label.

    cmd.exe does not parse a batch file up front. It remembers a byte offset,
    re-opens the file at each `call`, and seeks the label with a scanner that
    expects CRLF; in an LF-only file the seek lands mid-line, so it prints
    "The system cannot find the batch label specified - <label>" and carries
    on with the next command as though the call had returned.

    Reported from a real install, between steps 1/4 and 2/4 of setup:
    "The system cannot find the batch label specified - bail_if_cancelled".
    `bail_if_cancelled` is the routine that stops the installer after someone
    answers no, so on that machine every cancel was silently ignored.

    The cause was `.gitattributes` saying `* text=auto eol=lf`, which is right
    for the frontend (a `?v=` stamp, a CSS brace count and a wordlist the
    spell checker matches with `Set.has` all change under CRLF) and wrong for
    anything cmd.exe reads. `*.bat text eol=crlf` fixes the checkout; this
    fails the build if a file ever comes back with lone LFs anyway, which is
    what happens when one is written by a tool that ignores gitattributes.
    """
    offenders = []
    for path in repo_files(ROOT, suffixes=(".bat",)) + repo_files(ROOT, suffixes=(".cmd",)):
        #: An agent worktree under `.claude/` is another checkout, made
        #: without the attributes pass, so its batch files are LF and are not
        #: this tree's: the orchestrator's gate walked twenty of them once.
        #: (`.git`, `.venv` and `node_modules` are never in the shared walk.)
        if ".claude" in path.parts or ".venv" in path.parts:
            continue
        raw = path.read_bytes()
        lone = raw.count(b"\n") - raw.count(b"\r\n")
        if lone:
            offenders.append(f"{path.relative_to(ROOT)}: {lone} lone LF")
    assert not offenders, (
        "Windows batch files must be CRLF, or `call :label` fails: "
        + ", ".join(offenders)
    )


class TestUpdatesAskOnce:
    """The owner's decision, 2026-10-05: the first launch asks whether to check
    for updates automatically, and until that is answered nothing touches the
    network. Run for real in a scratch copy (`_scratch_repo`), never in ROOT,
    with a `git` on PATH that writes down every call and reaches nothing."""

    def _fake_git(self, tmp_path: Path) -> tuple[Path, Path]:
        bin_dir = tmp_path / "fakebin"
        bin_dir.mkdir()
        calls = tmp_path / "git-calls.txt"
        stub = bin_dir / "git"
        stub.write_text(f'#!/bin/sh\necho "$*" >> "{calls}"\nexit 0\n')
        stub.chmod(0o755)
        return bin_dir, calls

    def test_the_doctor_does_not_reach_the_remote_before_the_answer(self, tmp_path):
        repo = _scratch_repo(tmp_path)
        (repo / ".git").mkdir()
        bin_dir, calls = self._fake_git(tmp_path)
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(tmp_path / "data"))
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env.pop("TESSELLATE_PORT", None)
        result = subprocess.run(
            ["./start.sh", "--doctor"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode in (0, 1), result.stdout + result.stderr
        assert "not chosen yet" in result.stdout, result.stdout
        called = calls.read_text() if calls.exists() else ""
        assert "ls-remote" not in called and "pull" not in called, called

    def test_after_yes_the_doctor_does_reach_it(self, tmp_path):
        """The control: the same run with the question answered yes."""
        repo = _scratch_repo(tmp_path)
        (repo / ".git").mkdir()
        data = tmp_path / "data"
        data.mkdir()
        (data / "preferences.json").write_text(
            '{\n  "update_choice_made": true,\n  "auto_update_enabled": true\n}\n'
        )
        bin_dir, calls = self._fake_git(tmp_path)
        env = dict(os.environ, TESSELLATE_DATA_DIR=str(data))
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env.pop("TESSELLATE_PORT", None)
        result = subprocess.run(
            ["./start.sh", "--doctor"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode in (0, 1), result.stdout + result.stderr
        assert "ls-remote" in calls.read_text()

    _ASK = r"""
set -u
eval "$(sed -n '/^mm_ask_update_choice() {/,/^}/p' "$1")"
mm_ask_update_choice
"""

    def _ask(self, tmp_path: Path, typed: bytes | None) -> tuple[str, str]:
        """Runs the live function with a terminal on stdin (a pty) when
        `typed` is given, and with no terminal at all when it is None."""
        import pty

        script = tmp_path / "start.sh"
        shutil.copy2(START_SH, script)
        if typed is None:
            result = subprocess.run(
                ["bash", "-c", self._ASK, "probe", str(script)],
                stdin=subprocess.DEVNULL, capture_output=True, timeout=30,
            )
            return result.stdout.decode(), result.stderr.decode()
        primary, secondary = pty.openpty()
        try:
            proc = subprocess.Popen(
                ["bash", "-c", self._ASK, "probe", str(script)],
                stdin=secondary, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            os.write(primary, typed)
            out, err = proc.communicate(timeout=30)
        finally:
            os.close(primary)
            os.close(secondary)
        return out.decode(), err.decode()

    def test_no_terminal_means_no_question_and_no_answer(self, tmp_path):
        out, err = self._ask(tmp_path, None)
        assert out == "" and "Check for updates" not in err

    @pytest.mark.parametrize(("typed", "answer"), [(b"y\n", "yes"), (b"YES\n", "yes"), (b"n\n", "no"), (b"\n", "no")])
    def test_a_person_at_the_terminal_is_asked_once(self, tmp_path, typed, answer):
        out, err = self._ask(tmp_path, typed)
        assert out == answer
        assert "Check for updates automatically" in err

    def test_the_answer_is_handed_to_the_app(self):
        text = _read(START_SH)
        assert 'MM_UPDATE_CHOICE="$(mm_ask_update_choice)"' in text
        assert "export MM_UPDATE_CHOICE" in text


def test_the_windows_shortcut_lands_on_the_desktop_the_shell_shows():
    """OneDrive's folder backup, on by default on many new PCs, moves the
    Desktop to %USERPROFILE%\\OneDrive\\Desktop, so `start.bat --shortcut`
    wrote into a folder nobody saw (or failed for want of one), and
    `uninstall.bat --shortcuts` looked in the same wrong place. Both ask the
    shell for the folder now, by the same lines."""
    start_bat = _read(ROOT / "start.bat")
    uninstall_bat = _read(ROOT / "uninstall.bat")
    for name, text in (("start.bat", start_bat), ("uninstall.bat", uninstall_bat)):
        assert "%USERPROFILE%\\Desktop\\MemoryMap AI.lnk" not in text, name
        assert "[Environment]::GetFolderPath('Desktop')" in text, name
        assert 'set "MM_LNK=!MM_DESKTOP!\\Tessellate.lnk"' in text, name
    sub = start_bat.split("\n:desktop_dir", 1)[1].split("exit /b 0", 1)[0]
    assert "GetFolderPath" in sub
    assert sub == uninstall_bat.split("\n:desktop_dir", 1)[1].split("exit /b 0", 1)[0]


def test_a_path_with_an_apostrophe_survives_the_shortcut_powershell():
    """The paths go into PowerShell inside single quotes; C:\\Users\\O'Brien
    ended the string at the apostrophe and no shortcut was made."""
    text = _read(ROOT / "start.bat")
    line = next(line for line in text.splitlines() if "CreateShortcut(" in line)
    assert "'!MM_PS_LNK!'" in line and "'!MM_PS_HOME!start.bat'" in line
    assert "!MM_LNK!'" not in line and "'!MM_HOME!" not in line
    assert 'set "MM_PS_HOME=!MM_HOME:\'=\'\'!"' in text


class TestTheActionFiles:
    """Each action file runs the launcher's own flag, so an action has one
    implementation; read, never run (reinstall deletes `.venv`)."""

    @pytest.mark.parametrize(
        "name,flag",
        [("doctor.sh", "--doctor"), ("doctor.bat", "--doctor"),
         ("reinstall.sh", "--reinstall"), ("reinstall.bat", "--reinstall")],
    )
    def test_it_calls_the_launcher_flag(self, name, flag):
        assert re.search(r"start\.(sh|bat)\"? " + re.escape(flag), _read(ROOT / name))

    @pytest.mark.parametrize("name", ["reinstall.sh", "reinstall.bat"])
    def test_reinstall_asks_first(self, name):
        text = _read(ROOT / name)
        assert "Continue?" in text and "--yes" in text

    @pytest.mark.parametrize("name", ["tools.sh", "tools.bat"])
    def test_the_menu_offers_every_launcher_action(self, name):
        text = _read(ROOT / name)
        for flag in ("--doctor", "--logs", "--shortcut", "--version"):
            assert flag in text, flag
        for script in ("start-desktop", "reinstall", "uninstall"):
            assert script in text, script

    def test_the_menu_quits_on_q(self):
        out = subprocess.run(
            ["bash", str(ROOT / "tools.sh")], input="q\n", capture_output=True, text=True, timeout=30
        )
        assert out.returncode == 0 and "Tessellate tools" in out.stdout

    @pytest.mark.parametrize("name", ACTION_BAT)
    def test_bat_files_are_crlf_on_disk(self, name):
        assert b"\r\n" in (ROOT / name).read_bytes()
