"""Local OCR text extraction (core/ocr.py, ROADMAP.md item 30d).

Never touches a real Tesseract binary or a real image file: every test
mocks `shutil.which` and (where needed) `pytesseract`/`PIL.Image` so this
suite runs identically whether or not Tesseract happens to be installed on
the machine running it, the same reasoning `find_system_python`'s own
tests use for not depending on the real system Python being anything in
particular.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from tessellate.core import ocr


def test_tesseract_available_reflects_shutil_which(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract")
    assert ocr.tesseract_available() is True

    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    assert ocr.tesseract_available() is False


def test_extract_text_returns_empty_and_never_raises_when_the_binary_is_missing(
    monkeypatch, caplog
):
    ocr._log_binary_missing.cache_clear()  # a previous test may have already "logged" it
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    with caplog.at_level("INFO", logger="memorymap.ocr"):
        assert ocr.extract_text(Path("/does/not/exist.png")) == ""
        assert ocr.extract_text(Path("/does/not/exist2.png")) == ""
    # Logged once, not raised, and not once per call, the "once per
    # process, not once per upload" contract this module's own docstring
    # promises.
    assert sum("tesseract" in r.message.lower() for r in caplog.records) == 1


def test_extract_text_returns_the_real_text_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract")

    class _FakeImage:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _FakePytesseract:
        @staticmethod
        def image_to_string(img):
            return "  buy oat milk tuesday  \n"

    fake_image_module = type(
        "M", (), {"open": staticmethod(lambda path: _FakeImage())}
    )
    monkeypatch.setitem(
        sys.modules, "pytesseract", _FakePytesseract()
    )
    monkeypatch.setitem(sys.modules, "PIL", type("P", (), {"Image": fake_image_module}))
    monkeypatch.setitem(sys.modules, "PIL.Image", fake_image_module)

    image_path = tmp_path / "whiteboard.png"
    image_path.write_bytes(b"not a real image, mocked open() ignores this")
    assert ocr.extract_text(image_path) == "buy oat milk tuesday"


def test_extract_text_never_raises_on_a_corrupt_or_unreadable_image(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract")

    class _FakeImageModule:
        @staticmethod
        def open(path):
            raise OSError("cannot identify image file")

    monkeypatch.setitem(sys.modules, "pytesseract", type("P", (), {}))
    monkeypatch.setitem(
        sys.modules, "PIL", type("P", (), {"Image": _FakeImageModule})
    )
    monkeypatch.setitem(sys.modules, "PIL.Image", _FakeImageModule)

    bad = tmp_path / "corrupt.png"
    bad.write_bytes(b"garbage")
    assert ocr.extract_text(bad) == ""


def test_extract_and_store_writes_ocr_text_onto_the_row(app_state, session, monkeypatch, tmp_path):
    from tessellate.core.database import MediaUpload

    upload = MediaUpload(filename="a.png", original_name="a.png")
    session.add(upload)
    session.commit()
    session.refresh(upload)
    upload_id = upload.id
    session.close()

    monkeypatch.setattr(ocr, "extract_text", lambda path: "found text")
    ocr.extract_and_store(upload_id, tmp_path / "a.png")

    from tessellate.core import deps

    with deps.get_db().session() as check:
        reloaded = check.get(MediaUpload, upload_id)
        assert reloaded.ocr_text == "found text"


def test_extract_and_store_does_nothing_when_no_text_was_found(app_state, session, monkeypatch, tmp_path):
    from tessellate.core.database import MediaUpload

    upload = MediaUpload(filename="b.png", original_name="b.png")
    session.add(upload)
    session.commit()
    session.refresh(upload)
    upload_id = upload.id
    session.close()

    monkeypatch.setattr(ocr, "extract_text", lambda path: "")
    ocr.extract_and_store(upload_id, tmp_path / "b.png")

    from tessellate.core import deps

    with deps.get_db().session() as check:
        reloaded = check.get(MediaUpload, upload_id)
        assert reloaded.ocr_text is None


def test_extract_and_store_does_not_blow_up_if_the_upload_was_deleted_first(
    app_state, monkeypatch, tmp_path
):
    """A race is possible: OCR is still running when the row it would write
    to has already been deleted (DELETE /media/{id}). Must not raise."""
    monkeypatch.setattr(ocr, "extract_text", lambda path: "found text")
    ocr.extract_and_store(999999, tmp_path / "gone.png")  # no such row: must not raise


# --- attempt_binary_install: installing the tesseract binary itself,
# asked for directly ("add the option for install assistance ... automate
# it if possible"), every test below mocks subprocess.run and shutil.which,
# so none of this ever shells out to a real package manager. ----------------


def test_attempt_binary_install_short_circuits_when_already_present(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract")
    calls = []
    monkeypatch.setattr(ocr.subprocess, "run", lambda *a, **k: calls.append(a))
    ok, message = ocr.attempt_binary_install()
    assert ok is True
    assert "already installed" in message.lower()
    assert calls == []


def test_attempt_binary_install_reports_no_package_manager_found(monkeypatch):
    monkeypatch.setattr(ocr.sys, "platform", "linux")
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)  # neither tesseract nor any manager
    ok, message = ocr.attempt_binary_install()
    assert ok is False
    assert "package manager" in message.lower()


def test_attempt_binary_install_succeeds_on_windows_via_winget(monkeypatch):
    monkeypatch.setattr(ocr.sys, "platform", "win32")
    # First call (tesseract_available's own check, twice) says missing; once
    # winget "installs" it, later checks say present.
    installed = {"value": False}
    monkeypatch.setattr(
        ocr.shutil, "which", lambda name: (installed["value"] and name == "tesseract") or (name == "winget") or None
    )

    def _fake_run(command, **kwargs):
        assert command[0] == "winget"
        assert "--silent" in command
        installed["value"] = True

        class _Result:
            returncode = 0
            stdout = "Successfully installed"
            stderr = ""

        return _Result()

    monkeypatch.setattr(ocr.subprocess, "run", _fake_run)
    ok, message = ocr.attempt_binary_install()
    assert ok is True
    assert "installed" in message.lower()


def test_attempt_binary_install_never_trusts_exit_code_alone(monkeypatch):
    """A `0` exit code that didn't actually make the binary appear must not
    be reported as success, the same "don't trust a report of stored
    state, verify it" caution this app applies everywhere else."""
    monkeypatch.setattr(ocr.sys, "platform", "darwin")
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/local/bin/brew" if name == "brew" else None)

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(ocr.subprocess, "run", lambda *a, **k: _Result())
    ok, message = ocr.attempt_binary_install()
    assert ok is False
    assert "install it by hand" in message.lower()


def test_attempt_binary_install_handles_a_timeout_without_raising(monkeypatch):
    monkeypatch.setattr(ocr.sys, "platform", "darwin")
    monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/local/bin/brew" if name == "brew" else None)

    def _timeout(*a, **k):
        raise ocr.subprocess.TimeoutExpired(cmd="brew", timeout=90)

    monkeypatch.setattr(ocr.subprocess, "run", _timeout)
    ok, message = ocr.attempt_binary_install()
    assert ok is False
    assert "timed out" in message.lower()


def test_attempt_binary_install_tries_sudo_dash_n_before_giving_up_on_linux(monkeypatch):
    """Root already (a container) skips straight to the bare command; a
    non-root process tries a *non-interactive* sudo first, one that fails
    immediately rather than hanging on a password prompt nothing can
    answer: falling back to the bare command only after that."""
    monkeypatch.setattr(ocr.sys, "platform", "linux")
    monkeypatch.setattr(
        ocr.shutil, "which", lambda name: "/usr/bin/apt-get" if name == "apt-get" else None
    )
    if hasattr(ocr.os, "geteuid"):
        monkeypatch.setattr(ocr.os, "geteuid", lambda: 1000)  # not root

    seen = []

    def _fake_run(command, **kwargs):
        seen.append(command)
        if command[0] == "sudo":
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "sudo: a password is required"})()
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "Permission denied"})()

    monkeypatch.setattr(ocr.subprocess, "run", _fake_run)
    ok, message = ocr.attempt_binary_install()
    assert ok is False
    assert seen[0][0] == "sudo"
    assert seen[0][1] == "-n"
    assert seen[-1][0] == "apt-get"


def test_tesseract_runs_on_one_openmp_thread_unless_told_otherwise(monkeypatch):
    """Measured: 42 s against 0.28 s for one line of text in a four-core
    container with the default OpenMP thread count. The person's own value
    wins; the default is one thread."""
    from tessellate.core import ocr

    monkeypatch.delenv("OMP_THREAD_LIMIT", raising=False)
    ocr._one_thread_for_tesseract()
    assert os.environ["OMP_THREAD_LIMIT"] == "1"
    monkeypatch.setenv("OMP_THREAD_LIMIT", "3")
    ocr._one_thread_for_tesseract()
    assert os.environ["OMP_THREAD_LIMIT"] == "3"


# --- Tesseract on Windows, where PATH is not the whole answer ---------------
#
# Reported directly: "Tesseract installed but not recognised". The Windows
# installers do not reliably put their own directory on PATH, and the
# per-user install mode never does, so `shutil.which` says "not installed"
# about a binary that is sitting right there. These run on every platform
# because the branch is selected by `ocr.sys.platform`, which the suite
# already monkeypatches elsewhere in this file for the winget path.


def _windows_with_tesseract_at(monkeypatch, tmp_path, *parts, env_var="ProgramFiles"):
    """A fake Windows where tesseract.exe exists under `env_var` but PATH
    has never heard of it. Returns the binary's path."""
    root = tmp_path / env_var.replace("(", "_").replace(")", "")
    binary = root.joinpath(*parts) / "tesseract.exe"
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    monkeypatch.setattr(ocr.sys, "platform", "win32")
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    monkeypatch.setenv(env_var, str(root))
    monkeypatch.setenv("PATH", "")
    ocr._probe_windows_tesseract.cache_clear()
    return binary


def test_windows_finds_tesseract_in_program_files_when_path_misses_it(monkeypatch, tmp_path):
    binary = _windows_with_tesseract_at(monkeypatch, tmp_path, "Tesseract-OCR")
    try:
        assert ocr.tesseract_available() is True
        # Adopted, not merely detected: everything that looks at PATH later
        # in this process has to find it too.
        assert str(binary.parent) in os.environ["PATH"].split(os.pathsep)
    finally:
        ocr._probe_windows_tesseract.cache_clear()


def test_windows_finds_a_per_user_install_under_localappdata(monkeypatch, tmp_path):
    """The installer's "just for me" mode, which needs no administrator and
    is therefore the one most people end up in, and the one that never
    touches the machine PATH."""
    _windows_with_tesseract_at(
        monkeypatch, tmp_path, "Programs", "Tesseract-OCR", env_var="LOCALAPPDATA"
    )
    try:
        assert ocr.tesseract_available() is True
    finally:
        ocr._probe_windows_tesseract.cache_clear()


def test_windows_says_no_when_the_binary_really_is_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(ocr.sys, "platform", "win32")
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "empty"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.delenv("ProgramW6432", raising=False)
    ocr._probe_windows_tesseract.cache_clear()
    try:
        assert ocr.tesseract_available() is False
    finally:
        ocr._probe_windows_tesseract.cache_clear()


def test_the_probe_never_runs_off_windows(monkeypatch, tmp_path):
    """A Linux box with a directory that happens to be called Tesseract-OCR
    is not a Tesseract install, and the probe must not claim it is."""
    root = tmp_path / "pf"
    (root / "Tesseract-OCR").mkdir(parents=True)
    (root / "Tesseract-OCR" / "tesseract.exe").write_text("")
    monkeypatch.setattr(ocr.sys, "platform", "linux")
    monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
    monkeypatch.setenv("ProgramFiles", str(root))
    ocr._probe_windows_tesseract.cache_clear()
    try:
        assert ocr.tesseract_available() is False
    finally:
        ocr._probe_windows_tesseract.cache_clear()


def test_adopting_the_binary_twice_adds_one_path_entry(monkeypatch, tmp_path):
    """`tesseract_available` is called from every status poll, so a probe
    that appended to PATH each time would grow it without bound."""
    binary = _windows_with_tesseract_at(monkeypatch, tmp_path, "Tesseract-OCR")
    try:
        for _ in range(5):
            ocr._adopt_tesseract(binary)
        entries = [part for part in os.environ["PATH"].split(os.pathsep) if part]
        assert entries.count(str(binary.parent)) == 1
    finally:
        ocr._probe_windows_tesseract.cache_clear()


def test_a_reading_stored_while_the_background_pass_ran_is_kept(app_state, session, monkeypatch, tmp_path):
    """PR 211 CI (Python 3.13): "Read with RapidOCR" answered with the
    Tesseract text. The upload's background pass checked for stored text
    before its read and wrote after it unconditionally, so a slow pass landed
    on top of the reading (or a hand edit) made in between."""
    from tessellate.core import deps
    from tessellate.core.database import MediaUpload

    upload = MediaUpload(filename="c.png", original_name="c.png")
    session.add(upload)
    session.commit()
    upload_id = upload.id
    session.close()

    def slow_read(path):  # noqa: ANN001, ANN202
        with deps.get_db().session() as meanwhile:
            meanwhile.get(MediaUpload, upload_id).ocr_text = "read by rapid"
            meanwhile.commit()
        return "read by tesseract"

    monkeypatch.setattr(ocr, "extract_text", slow_read)
    ocr.extract_and_store(upload_id, tmp_path / "c.png")
    with deps.get_db().session() as check:
        assert check.get(MediaUpload, upload_id).ocr_text == "read by rapid"
