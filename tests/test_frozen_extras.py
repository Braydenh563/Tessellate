"""The packaged Windows app's optional packages, on the parts that run on
Linux: which Python it borrows, what the wizard's `--install-extras` counts
as a failure, what "Remove" deletes, and whether the Documents box installs
something that can read the documents it promises.

A frozen build has no Python of its own that pip can run. It borrows the
system's (`find_system_python`), installs into a folder in the data
directory with wheels for the bundled interpreter (`frozen_extras_dir`), and
reads that folder at start-up. Each test here is one way that chain broke on
paper while every earlier test was green.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tessellate.core import extras


@pytest.fixture(autouse=True)
def _clean_extras():
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


@pytest.fixture
def frozen(monkeypatch, tmp_path):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    return tmp_path


# --- which Python a packaged build borrows ---------------------------------


def test_the_store_alias_is_not_a_python(frozen, monkeypatch):
    """Windows 10 and 11 put `python.exe` on PATH before Python is installed:
    an App Execution Alias that opens the Store and exits 9009. `which`
    finds it, so the packaged app ran pip through it and reported a pip
    failure instead of the message that says to install Python."""
    monkeypatch.setattr(
        extras.shutil,
        "which",
        lambda name: r"C:\Users\A\AppData\Local\Microsoft\WindowsApps\python.exe"
        if name == "python"
        else None,
    )

    class _Stub:
        returncode = 9009
        stdout = ""

    monkeypatch.setattr(extras.subprocess, "run", lambda *a, **k: _Stub())
    assert extras.find_system_python() is None
    assert extras._pip_base_command() is None


def test_the_py_launcher_finds_a_python_that_is_not_on_path(frozen, monkeypatch):
    """python.org's installer leaves "Add python.exe to PATH" unticked by
    default and installs the `py` launcher instead, so most people who
    installed Python the ordinary way have `py` and no `python`."""
    real = sys.executable
    monkeypatch.setattr(
        extras.shutil, "which", lambda name: r"C:\Windows\py.exe" if name == "py" else None
    )
    seen = []

    class _Done:
        returncode = 0
        stdout = real + "\n"

    def fake_run(command, **kwargs):
        seen.append(command)
        return _Done()

    monkeypatch.setattr(extras.subprocess, "run", fake_run)
    assert extras.find_system_python() == real
    assert seen[0][:2] == [r"C:\Windows\py.exe", "-3"]


def test_a_real_python_on_path_is_used_as_it_reports_itself(frozen, monkeypatch):
    real = sys.executable
    monkeypatch.setattr(extras.shutil, "which", lambda name: real if name == "python" else None)
    # A real interpreter, really run: the probe is what decides.
    assert Path(extras.find_system_python()).resolve() == Path(real).resolve()


def test_a_source_install_never_probes(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)

    def boom(*a, **k):
        raise AssertionError("a source install uses its own interpreter")

    monkeypatch.setattr(extras.subprocess, "run", boom)
    assert extras.find_system_python() == sys.executable


# --- the wizard's --install-extras -----------------------------------------


def test_an_extra_already_installed_is_not_a_failure(monkeypatch):
    """An upgrade runs the wizard again with the same boxes ticked. What is
    already there is done, not failed: the exit code said otherwise."""
    monkeypatch.setattr(extras, "is_installed", lambda extra: True)

    def boom(*a, **k):
        raise AssertionError("nothing should be installed")

    monkeypatch.setattr(extras, "_dispatch", boom)
    assert extras.install_blocking(["voice", "pdfpages"]) == 0


def test_an_unknown_id_is_still_a_failure():
    assert extras.install_blocking(["no-such-extra"]) == 1


def test_a_failed_install_says_why_on_stderr(capsys):
    """The packaged wizard's stderr is the data folder's desktop-stdio.log:
    a failure that only went to the logger left that file empty, so the
    package check (and a support bundle) showed "exited 1" and no reason."""
    assert extras.install_blocking(["no-such-extra"]) == 1
    err = capsys.readouterr().err
    assert "no-such-extra" in err and "not installed" in err


# --- the Documents box -----------------------------------------------------


def test_the_documents_extra_can_read_pdf_word_and_slides():
    """markitdown 0.1 split its converters into optional groups: a bare
    `pip install markitdown` reads HTML and text, and raises on a PDF, a
    .docx or a .pptx (checked against markitdown 0.1.8's own metadata). The
    wizard's box says "Import PDFs, Word files and slides"; the install has
    to carry the three groups that do that."""
    packages = extras.EXTRAS_BY_ID["documents"].packages
    spec = next(p for p in packages if p.startswith("markitdown"))
    groups = set(spec[spec.index("[") + 1 : spec.index("]")].split(","))
    assert {"pdf", "docx", "pptx"} <= groups


# --- Remove, on a packaged build -------------------------------------------


def _fake_dist(target: Path, name: str, files: dict[str, str]) -> None:
    """A wheel as `pip --target` leaves it: the files, and a dist-info whose
    RECORD lists them."""
    dist_info = target / f"{name.replace('-', '_')}-1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n")
    record = []
    for rel, text in files.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        record.append(f"{rel},,")
    record.append(f"{dist_info.name}/METADATA,,")
    record.append(f"{dist_info.name}/RECORD,,")
    (dist_info / "RECORD").write_text("\n".join(record) + "\n")


def test_remove_deletes_from_the_packaged_apps_own_folder(frozen, monkeypatch):
    """`pip uninstall` has no `--target`. On the packaged app it ran against
    the borrowed system Python, which does not have the extra (it is in the
    data folder), so it printed a warning, exited 0, and the card said
    "removed" over a package that still imported. Or it removed the
    person's own copy from their own Python. Neither is the button."""
    target = extras.frozen_extras_dir()
    target.mkdir(parents=True)
    _fake_dist(
        target,
        "faster-whisper",
        {"faster_whisper/__init__.py": "", "faster_whisper/api.py": "", "faster_whisper/assets/silero.onnx": "x"},
    )
    _fake_dist(target, "ctranslate2", {"ctranslate2/__init__.py": ""})
    (target / "faster_whisper" / "__pycache__").mkdir()
    (target / "faster_whisper" / "__pycache__" / "api.cpython-312.pyc").write_text("")

    def no_python(*a, **k):
        raise AssertionError("removing from the bundle's folder needs no Python")

    monkeypatch.setattr(extras.subprocess, "Popen", no_python)
    monkeypatch.setattr(extras, "find_system_python", no_python)

    extras._run_uninstall(extras.EXTRAS_BY_ID["voice"])

    state = extras.current()
    assert state.outcome == "completed", state.step
    assert not (target / "faster_whisper").exists()
    assert not list(target.glob("faster_whisper-*.dist-info"))
    # Only what the entry named: its dependency stays, as on a source install.
    assert (target / "ctranslate2" / "__init__.py").is_file()


def test_remove_never_deletes_outside_the_folder(frozen):
    target = extras.frozen_extras_dir()
    target.mkdir(parents=True)
    outside = frozen / "notes-that-matter.txt"
    outside.write_text("keep")
    _fake_dist(target, "faster-whisper", {"faster_whisper/__init__.py": ""})
    record = next(target.glob("faster_whisper-*.dist-info")) / "RECORD"
    record.write_text(record.read_text() + "../../notes-that-matter.txt,,\n")

    extras._run_uninstall(extras.EXTRAS_BY_ID["voice"])

    assert outside.read_text() == "keep"
    assert not (target / "faster_whisper").exists()


def test_remove_of_something_never_installed_says_so(frozen):
    extras.frozen_extras_dir().mkdir(parents=True)
    extras._run_uninstall(extras.EXTRAS_BY_ID["voice"])
    state = extras.current()
    assert state.outcome == "completed"
    assert "not installed" in state.step
