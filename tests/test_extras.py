"""Installing optional dependencies from Settings.

The security property is the whole design and is what these mostly test: the
request names an *entry in an allowlist*, never a package. `pip install
<whatever the body said>` is arbitrary code execution by design, and no amount
of validating the string afterwards makes it safe.
"""

from __future__ import annotations

import pytest

from tessellate.api import routes_tasks
from tessellate.core import extras


@pytest.fixture(autouse=True)
def _clean_extras():
    """Process-global, like the job registry. Without this one test's install
    state leaks into the next test's assertions."""
    extras.reset_for_tests()
    yield
    extras.reset_for_tests()


def test_the_catalogue_says_what_each_extra_buys(client):
    body = client.get("/extras").json()
    ids = {e["id"] for e in body["extras"]}
    assert {"voice", "desktop", "semantic"} <= ids
    for extra in body["extras"]:
        assert extra["enables"], f"{extra['id']} does not say what it turns on"
        assert extra["size"], f"{extra['id']} does not say how big it is"


def test_an_unknown_extra_is_refused_rather_than_installed(client):
    """The id comes from a URL. An unknown one is a thing to report."""
    body = client.post("/extras/not-a-real-extra/install").json()
    assert body["started"] is False
    assert not extras.current().running


def test_a_package_name_in_the_url_is_not_a_package_name(client):
    """The path selects an allowlist entry; it is never handed to pip. If this
    ever regresses, the failure mode is remote code execution, so it is
    asserted directly rather than left to the shape of the code."""
    for hostile in ["requests", "evil-package", "requests;rm -rf /", "../voice"]:
        response = client.post(f"/extras/{hostile}/install")
        # Either the route refuses it or there is no such route. Both are
        # "nothing was installed", which is the property under test, asserting
        # on the status code alone would make this pass for the wrong reason.
        if response.status_code == 200:
            assert response.json()["started"] is False, hostile
        assert not extras.current().running, hostile


def test_installed_extras_are_detected_by_import_not_by_pip(client):
    """What matters is whether *this* interpreter can use it, a different
    question from whether pip put it somewhere. `fastapi` is certainly
    importable here, so it stands in for an installed extra."""
    fake = extras.Extra(
        id="x",
        label="X",
        enables="e",
        packages=("fastapi",),
        module="fastapi",
        size="0",
    )
    missing = extras.Extra(
        id="y",
        label="Y",
        enables="e",
        packages=("nope",),
        module="a_module_that_is_not_installed_anywhere",
        size="0",
    )
    assert extras.is_installed(fake) is True
    assert extras.is_installed(missing) is False


def test_an_already_installed_extra_is_not_reinstalled(client, monkeypatch):
    monkeypatch.setattr(extras, "is_installed", lambda extra: True)
    started, message = extras.start("voice")
    assert started is False
    assert "already installed" in message


def test_only_one_install_runs_at_a_time(client, monkeypatch):
    """Two pips against one environment is a way to corrupt it."""
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    assert extras.start("voice")[0] is True
    started, message = extras.start("desktop")
    assert started is False
    assert "already running" in message


def test_a_running_install_appears_in_background_tasks(client, monkeypatch):
    """Asked for directly. It rides `/tasks` like every other background job,
    which is what puts it in the status bar and the Tasks panel without either
    of them learning anything new."""
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    extras.start("voice")

    tasks = routes_tasks.collect()
    mine = [t for t in tasks if t["kind"] == "extra"]
    assert mine, [t["kind"] for t in tasks]
    assert "faster-whisper" in mine[0]["label"] or "Voice" in mine[0]["label"]
    # pip reports no fraction worth believing, and a bar that guesses is worse
    # than one that admits it cannot say.
    assert mine[0]["progress"] is None


def _no_dispatch(*args, **kwargs):
    """Queues nothing on the pool. These tests are about the bookkeeping
    around pip, and actually running pip in a test suite would download the
    internet."""


def test_reinstall_is_allowed_where_install_is_not(client, monkeypatch):
    """The escape hatch for the state detection cannot see: `find_spec` answers
    "is it there", not "is it sound". A wheel built for the wrong platform
    imports and does not work, the Windows torch DLL in the README is exactly
    this: and without a reinstall the app's answer would be "already
    installed" forever."""
    monkeypatch.setattr(extras, "is_installed", lambda extra: True)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)

    assert extras.start("voice")[0] is False
    extras.reset_for_tests()
    started, message = extras.start("voice", reinstall=True)
    assert started is True
    assert "Reinstalling" in message


def test_a_reinstall_does_not_trust_the_cache(client, monkeypatch):
    """`--upgrade` would see the version it already has and do nothing, which
    is the one outcome that helps nobody; a cached wheel that is itself corrupt
    would be reinstalled faithfully."""
    seen = {}

    class _Capture:
        def __init__(self, command, **kwargs):
            seen["command"] = command
            self.stdout = []

        def wait(self):
            return 0

    monkeypatch.setattr(extras.subprocess, "Popen", _Capture)
    extras._run_install(extras.EXTRAS_BY_ID["voice"], reinstall=True)
    assert "--force-reinstall" in seen["command"]
    assert "--no-cache-dir" in seen["command"]
    assert "faster-whisper" in seen["command"]


def test_the_pip_constraint_file_has_no_extras(client, monkeypatch):
    """Reported live: every extras install failed with 'pip exited with code
    1', and the real reason (only visible once logging was fixed) was
    `ERROR: Constraints cannot have extras`. `-c` was pointed straight at
    requirements.txt, which pins `uvicorn[standard]` and `fsspec[http]`, 
    pip's constraints parser rejects the whole file over those, not just
    those two lines, so *no* extra could ever install. `_run_install` must
    hand pip a stripped copy, not the real file."""
    seen = {}

    class _Capture:
        def __init__(self, command, **kwargs):
            seen["command"] = command
            # Must read the constraint file *now*: `_run_install`'s `finally`
            # deletes it right after `wait()` returns, before this test gets
            # control back.
            constraint_path = extras.Path(command[command.index("-c") + 1])
            seen["constraint_path"] = constraint_path
            seen["constraint_text"] = constraint_path.read_text()
            self.stdout = []

        def wait(self):
            return 0

    monkeypatch.setattr(extras.subprocess, "Popen", _Capture)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    real_requirements = extras.Path(extras.__file__).resolve().parents[3] / "requirements.txt"
    assert seen["constraint_path"] != real_requirements
    assert "[" not in seen["constraint_text"]
    assert not seen["constraint_path"].exists()  # cleaned up once pip has run


# --- extras nothing calls yet -------------------------------------------------
#
# llama-cpp-python installs a library the chat backend does not know about
# yet. It says so in a caveat *under a working Install button*, which spends
# the user's disk and their time on a feature that does not exist and then
# asks for a restart. Asked for directly: grey it out until it is real.
#
# markitdown used to be in this bucket too, flagged as "nothing calls it
# yet", until §37G built the Import button behind it (routes_import.py).
# `documents` moved to the "ready" tests below rather than being deleted from
# here, so a future session can see it used to be unavailable and why.


def test_an_extra_nothing_calls_yet_says_so(client):
    extras = {e["id"]: e for e in client.get("/extras").json()["extras"]}
    assert extras["localllm"]["unavailable"]


def test_a_ready_extra_carries_no_such_reason(client):
    extras = {e["id"]: e for e in client.get("/extras").json()["extras"]}
    assert extras["voice"]["unavailable"] == ""
    assert extras["desktop"]["unavailable"] == ""
    assert extras["documents"]["unavailable"] == ""


def test_an_unavailable_extra_is_refused_by_the_server_not_only_the_button(client):
    """The greyed-out button is a courtesy; this is the rule. `core/extras.py`
    is the allowlist, so whether something may be installed belongs there and
    not in app.js: a POST straight at the endpoint has to be refused too."""
    body = client.post("/extras/localllm/install").json()
    assert body["started"] is False
    assert "isn't ready" in body["message"]


def test_asking_twice_does_not_make_it_ready(client):
    """`reinstall=true` is the escape hatch for a package that is installed and
    broken. An extra nothing calls cannot be in that state, so the flag must
    not be a way round the refusal."""
    body = client.post("/extras/localllm/install?reinstall=true").json()
    assert body["started"] is False


def test_removal_is_never_blocked(client, monkeypatch):
    """Somebody who installed llama-cpp-python by hand, or before it was
    marked, still needs the way out. Refusing removal would strand them."""
    started = {}
    monkeypatch.setattr(extras, "_dispatch", lambda *a, **k: started.setdefault("go", True))
    body = client.post("/extras/localllm/uninstall").json()
    assert body["started"] is True
    assert started == {"go": True}


# --- reported: remove/reinstall of faster-whisper silently failed on Windows
# once the dictation buttons had been used once this session --------------------


def test_reinstalling_voice_while_its_model_is_loaded_is_refused(monkeypatch):
    """Windows locks the loaded .pyd/DLL exclusively; pip can run and still
    fail to replace it. Refusing up front says why, instead of a cryptic pip
    error nobody reading it would connect to "I used the mic earlier"."""
    from tessellate.ai import voice

    monkeypatch.setattr(voice, "_loaded", ("base", object()))
    started, message = extras.start("voice", reinstall=True)
    assert started is False
    assert "restart" in message.lower()


def test_removing_voice_while_its_model_is_loaded_is_refused(monkeypatch):
    from tessellate.ai import voice

    monkeypatch.setattr(voice, "_loaded", ("base", object()))
    started, message = extras.remove("voice")
    assert started is False
    assert "restart" in message.lower()


def test_voice_actions_are_unblocked_once_nothing_is_loaded(client, monkeypatch):
    """The common case: nobody has recorded anything yet, or the process is
    fresh: must not be caught by the same guard.

    `_dispatch` is mocked like every other test that reaches `remove()`
    - without it this spawns a *real* background thread that runs real pip
    uninstall against the live environment. Found live: it outlived this test,
    and a later, unrelated test in the OCR extra's own install path picked up
    its real "WARNING: Skipping faster-whisper as it is not installed." output
    through the shared `_state` global, failing on an assertion that had
    nothing to do with faster-whisper at all."""
    from tessellate.ai import voice

    monkeypatch.setattr(voice, "_loaded", None)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    started, message = extras.remove("voice")
    assert started is True


def test_the_guard_leaves_other_extras_alone(monkeypatch):
    """Only voice caches a loaded native model across requests; nothing about
    another extra should ever be refused for this reason.

    `_dispatch` is mocked like every other test that reaches `start()`
    - without it this spawns a *real* background thread that runs real pip
    against the real network (reported: it raced a later, unrelated test in
    `test_tasks.py` for control of the shared `taskhistory` singleton and
    intermittently made that one fail depending on how long pip took)."""
    from tessellate.ai import voice

    monkeypatch.setattr(voice, "_loaded", ("base", object()))
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    started, message = extras.start("desktop", reinstall=True)
    assert started is True


# --- reported: a failed install showed "pip exited with code 1. The log
# above says why." in the Background tasks history card, with no log anywhere
# near it (grep the module docstring's numbered note in `core/extras.py` for
# the full story) --------------------------------------------------------------


class _FailingPip:
    """Stands in for a `pip install` that dies with a realistic transcript:
    boilerplate, the real error, and pip's own parting nag, in that order,
    which is the order real pip output comes in and exactly the shape that
    breaks a naive "take the last line" reading."""

    def __init__(self, command, **kwargs):
        self.stdout = [
            "Collecting faster-whisper\n",
            "  Downloading faster_whisper-1.0.0-py3-none-any.whl (2.0 kB)\n",
            "ERROR: Could not find a version that satisfies the requirement "
            + "faster-whisper (from versions: none)\n",
            "ERROR: No matching distribution found for faster-whisper\n",
            "[notice] A new release of pip is available: 24.0 -> 26.2.1\n",
            "[notice] To update, run: python.exe -m pip install --upgrade pip\n",
        ]

    def wait(self):
        return 1


def test_a_failed_install_names_the_real_error_not_pips_update_nag(client, monkeypatch):
    """The message must be self-contained: it is read from the Background
    tasks history card, which has no log fold anywhere near it."""
    monkeypatch.setattr(extras.subprocess, "Popen", _FailingPip)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    state = extras.current()
    assert state.outcome == "failed"
    assert "The log above says why" not in state.step
    assert "No matching distribution found for faster-whisper" in state.step
    # Not pip's own nag, which is always the literal last line of real output.
    assert "upgrade pip" not in state.step


def test_a_failed_install_reason_reaches_the_history_card(client, monkeypatch):
    """`taskhistory` is what the Background tasks "Recently finished" card
    reads: it must carry the real reason itself, not a pointer to a log the
    card never renders."""
    from tessellate.core import taskhistory

    monkeypatch.setattr(extras.subprocess, "Popen", _FailingPip)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    entries = taskhistory.recent()
    assert entries, "the finished install never recorded history"
    assert entries[0]["outcome"] == "failed"
    assert "The log above says why" not in entries[0]["detail"]
    assert "No matching distribution found for faster-whisper" in entries[0]["detail"]


def test_a_failed_install_reaches_settings_logs(client, monkeypatch):
    """The bug in the earlier fix, precisely: `_run_uninstall` routed pip's
    output through `logging` (which backs Settings, Logs, `core/logbuffer`)
    and `_run_install` did not, so a failed *install*, the case actually
    reported: still never showed up there no matter what the panel said."""
    from tessellate.core import logbuffer

    before = logbuffer.latest_seq()
    monkeypatch.setattr(extras.subprocess, "Popen", _FailingPip)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    new_records = logbuffer.since(before)
    ours = [r for r in new_records if r["logger"] == "tessellate.extras"]
    assert ours, "pip's failure never reached the memorymap.extras logger"
    assert ours[-1]["level"] == "ERROR"
    assert "No matching distribution found for faster-whisper" in ours[-1]["message"]


def test_a_successful_install_also_reaches_settings_logs(client, monkeypatch):
    """The success path needs the same wiring, `_run_uninstall` logged both
    outcomes, `_run_install` logged neither."""
    from tessellate.core import logbuffer

    class _Capture:
        def __init__(self, command, **kwargs):
            self.stdout = ["Successfully installed faster-whisper-1.0.0\n"]

        def wait(self):
            return 0

    before = logbuffer.latest_seq()
    monkeypatch.setattr(extras.subprocess, "Popen", _Capture)
    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    ours = [r for r in logbuffer.since(before) if r["logger"] == "tessellate.extras"]
    assert ours, "a successful install never reached Settings -> Logs either"
    assert ours[-1]["level"] == "INFO"


def test_pip_reason_prefers_a_named_error_over_the_literal_last_line(client):
    """Direct unit coverage for the helper itself: pip prints its update nag
    last on almost every run, so the naive "last line" reading would report
    that instead of the failure, see `search/searxng_manager._reason`,
    which this mirrors and which was fixed for the exact same trap."""
    log = [
        "Collecting sentence-transformers",
        "ERROR: Could not build wheels for tokenizers",
        "[notice] A new release of pip is available: 24.0 -> 26.2.1",
        "[notice] To update, run: python.exe -m pip install --upgrade pip",
    ]
    reason = extras._pip_reason(log, "pip exited with code 1")
    assert "Could not build wheels for tokenizers" in reason
    assert "upgrade pip" not in reason


def test_pip_reason_falls_back_to_the_prefix_when_nothing_is_useful(client):
    """All boilerplate, nothing to add, say the prefix alone rather than
    quoting pip's own update nag as if it were the reason."""
    log = [
        "[notice] A new release of pip is available: 24.0 -> 26.2.1",
        "[notice] To update, run: python.exe -m pip install --upgrade pip",
    ]
    assert extras._pip_reason(log, "pip exited with code 1") == "pip exited with code 1"


# --- a real support-bundle report: "pip exited with code 2: memorymap:
# error: unrecognized arguments: -m pip install ..." from the packaged
# Windows app. Root cause: `sys.executable -m pip` is right for a source
# install but sys.executable in a frozen (PyInstaller) build is the app's
# own .exe, so that command re-launches *the app* with pip's own arguments,
# which its argparse (only --desktop/--reset-password) rejects. This had
# been reported twice before as an unexplained "pip exited with code 1/2,
# no error text visible", there never was any real pip output, because pip
# was never actually run. -----------------------------------------------


def test_find_system_python_is_sys_executable_when_not_frozen(monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", False, raising=False)
    assert extras.find_system_python() == extras.sys.executable


def test_find_system_python_frozen_uses_path_lookup(monkeypatch):
    """The general helper `_pip_base_command` and searxng_install.py's own
    venv-creation call both build on, same real bug, two call sites, one
    fix. `python3` is only tried when `python` isn't found."""
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        extras.shutil, "which", lambda name: "/usr/bin/python3" if name == "python3" else None
    )
    # Each candidate is also run, to tell a Python from the Store's alias
    # (tests/test_frozen_extras.py); here every candidate is a real one.
    monkeypatch.setattr(extras, "_interpreter_behind", lambda command: command[0])
    assert extras.find_system_python() == "/usr/bin/python3"


def test_pip_base_command_uses_sys_executable_when_not_frozen(monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", False, raising=False)
    assert extras._pip_base_command() == [extras.sys.executable, "-m", "pip"]


def test_pip_base_command_finds_a_system_python_when_frozen(monkeypatch):
    """INSTALL.md documents Settings -> Packages as the no-terminal,
    no-Python-required way in from the Windows installer, so a frozen build
    still has to work when a real Python happens to be on PATH, refusing
    outright would break that promise, not just tighten an error message."""
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        extras.shutil, "which", lambda name: r"C:\Python312\python.exe" if name == "python" else None
    )
    monkeypatch.setattr(extras, "_interpreter_behind", lambda command: command[0])
    assert extras._pip_base_command() == [r"C:\Python312\python.exe", "-m", "pip"]


def test_pip_base_command_returns_none_when_frozen_and_no_python_found(monkeypatch):
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    monkeypatch.setattr(extras.shutil, "which", lambda name: None)
    assert extras._pip_base_command() is None


def test_install_gives_an_actionable_message_instead_of_the_argparse_crash(
    client, monkeypatch
):
    """The exact scenario from the real report: frozen, no system Python.
    Before this fix, `_run_install` would have built the broken command and
    handed it to subprocess.Popen (the mock below would fail the test with
    the wrong call), producing the "unrecognized arguments" crash instead of
    this message."""
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    monkeypatch.setattr(extras.shutil, "which", lambda name: None)

    def _unexpected_popen(*args, **kwargs):
        raise AssertionError("pip must not be invoked when no interpreter was found")

    monkeypatch.setattr(extras.subprocess, "Popen", _unexpected_popen)

    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    state = extras.current()
    assert state.outcome == "failed"
    assert state.step == extras.NO_PYTHON_FOUND_MESSAGE
    assert not state.running


def test_uninstall_on_a_packaged_build_needs_no_python(client, monkeypatch):
    """Was "gives the same actionable message". A packaged build's extras
    live in its own folder, which `pip uninstall` cannot reach (it has no
    `--target`), so removal reads that folder's own metadata instead and no
    Python is asked for at all (tests/test_frozen_extras.py)."""
    monkeypatch.setattr(extras.sys, "frozen", True, raising=False)
    monkeypatch.setattr(extras.shutil, "which", lambda name: None)

    def _unexpected_popen(*args, **kwargs):
        raise AssertionError("pip must not be invoked to remove a packaged extra")

    monkeypatch.setattr(extras.subprocess, "Popen", _unexpected_popen)

    extras._run_uninstall(extras.EXTRAS_BY_ID["voice"])

    state = extras.current()
    assert state.outcome == "completed"
    assert state.step != extras.NO_PYTHON_FOUND_MESSAGE


class _SucceedingPip:
    """A `pip install` that exits 0 with a boring, realistic transcript."""

    def __init__(self, command, **kwargs):
        self.stdout = [
            "Collecting pytesseract\n",
            "Successfully installed pytesseract-0.3.13 Pillow-12.3.0\n",
        ]

    def wait(self):
        return 0


# --- the "ocr" extra's own system-binary half, asked for directly ("add the
# option for install assistance for the tesseract program installation,
# automate it if possible") -------------------------------------------------


def test_a_successful_ocr_install_also_attempts_the_tesseract_binary(client, monkeypatch):
    monkeypatch.setattr(extras.subprocess, "Popen", _SucceedingPip)
    calls = []

    def _fake_attempt(timeout=None):
        calls.append(timeout)
        return True, "Tesseract installed."

    monkeypatch.setattr(extras.ocr, "attempt_binary_install", _fake_attempt)
    extras._run_install(extras.EXTRAS_BY_ID["ocr"])

    state = extras.current()
    assert state.outcome == "completed"
    assert len(calls) == 1
    assert "Tesseract installed." in state.step
    assert "Tesseract installed." in state.log[-1]


def test_a_failed_tesseract_binary_attempt_does_not_fail_the_whole_ocr_install(
    client, monkeypatch
):
    """The pip packages genuinely installed and are genuinely useful on
    their own (ocr.py degrades cleanly without the binary), a failed
    *binary* attempt must not turn a real, working pip install into a
    reported failure."""
    monkeypatch.setattr(extras.subprocess, "Popen", _SucceedingPip)
    monkeypatch.setattr(
        extras.ocr,
        "attempt_binary_install",
        lambda timeout=None: (False, "Couldn't install Tesseract automatically."),
    )
    extras._run_install(extras.EXTRAS_BY_ID["ocr"])

    state = extras.current()
    assert state.outcome == "completed"
    assert "Couldn't install Tesseract automatically." in state.step


def test_other_extras_never_touch_the_tesseract_binary_attempt(client, monkeypatch):
    monkeypatch.setattr(extras.subprocess, "Popen", _SucceedingPip)
    calls = []
    monkeypatch.setattr(
        extras.ocr, "attempt_binary_install", lambda timeout=None: calls.append(1) or (True, "")
    )
    extras._run_install(extras.EXTRAS_BY_ID["voice"])

    assert calls == []
    assert extras.current().outcome == "completed"


def test_no_extra_can_uninstall_the_apps_own_base_dependencies(session):
    """A "Base Requirements (requirements.txt)" extra was added with
    `packages=("-r", "requirements.txt")` and `module="fastapi"`. Since
    fastapi is always importable (the app runs on it), `is_installed()` was
    permanently True, so the UI only ever offered Reinstall/Remove, and
    Remove ran `pip uninstall -y -r requirements.txt`, stripping fastapi,
    uvicorn, SQLAlchemy and every other base dependency from the interpreter
    the app itself is running in. No extra's package list may equal (or
    contain) the project's own requirements file."""
    for extra in extras.EXTRAS:
        assert "-r" not in extra.packages, f"{extra.id} installs from a requirements file"


def test_the_word_exporter_is_retired(client):
    """Word files are written in the browser (documents-word.js), so the
    python-docx extra and its 501 route went (Brief 42): no row offers a
    package nothing calls, and the old route is gone rather than answering."""
    assert "docx" not in extras.EXTRAS_BY_ID
    assert all("docx" not in bundle.extras for bundle in extras.BUNDLES)
    made = client.post("/documents", json={"title": "Word export", "content": "# Hi\n"})
    assert client.get(f"/documents/{made.json()['id']}/export.docx").status_code in (404, 405)


# --- a packaged (frozen) build installs where it can import from ------------------


def test_a_frozen_build_installs_extras_into_its_own_folder(monkeypatch, tmp_path):
    """Owner's packaged-app log: `No module named 'sentence_transformers'`
    after an install that reported success. pip had installed into the system
    Python's site-packages, which a PyInstaller build never reads. A frozen
    build targets a folder in the data directory instead, with wheels for its
    own interpreter, and puts that folder on `sys.path`."""
    import sys

    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    target = extras.frozen_extras_dir()
    assert target == (tmp_path / "python-extras" / f"cp{sys.version_info.major}{sys.version_info.minor}").resolve()

    args = extras._frozen_target_args()
    assert args[args.index("--target") + 1] == str(target)
    assert "--only-binary=:all:" in args
    assert args[args.index("--python-version") + 1] == f"{sys.version_info.major}.{sys.version_info.minor}"

    monkeypatch.setattr(sys, "path", list(sys.path))
    extras.activate_frozen_extras()
    assert sys.path[-1] == str(target)
    extras.activate_frozen_extras()
    assert sys.path.count(str(target)) == 1


def test_a_packaged_linux_build_asks_pip_for_the_wheels_that_exist():
    """`linux_x86_64` is no published wheel's tag, so pip found no lxml for
    the packaged Linux app's `--install-extras docx`; the manylinux tags the
    machine's glibc runs are asked for too. Windows' tag is used as it is."""
    linux = extras._pip_platforms("linux_x86_64", glibc="2.31")
    assert linux[0] == "manylinux_2_31_x86_64"
    assert "manylinux_2_17_x86_64" in linux and "manylinux_2_16_x86_64" not in linux
    assert {"manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"} <= set(linux)
    assert linux[-1] == "linux_x86_64"
    windows = extras._pip_platforms("win_amd64")
    assert windows == ["win_amd64"]
    odd = extras._pip_platforms("linux_aarch64", glibc="unknown")
    assert odd == ["linux_aarch64"]


def test_a_packaged_build_constrains_extras_with_its_bundled_requirements(tmp_path, monkeypatch):
    """`parents[3]` is outside the bundle in a frozen build, so packaged
    installs ran unconstrained; the specs bundle requirements.txt at the
    root and this reads it from there."""
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    frozen_path = extras._requirements_path()
    assert frozen_path == tmp_path / "requirements.txt"
    monkeypatch.delattr(sys, "frozen")
    source_path = extras._requirements_path()
    assert source_path.is_file()
    root = extras.Path(extras.__file__).resolve().parents[3]
    for spec in ("windows", "linux"):
        text = (root / "packaging" / spec / "tessellate.spec").read_text(encoding="utf-8")
        assert '(str(REPO_ROOT / "requirements.txt"), "."),' in text, spec


def test_a_source_install_is_untouched(monkeypatch):
    import sys

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert extras.frozen_extras_dir() is None
    assert extras._frozen_target_args() == []


def test_the_installer_page_runs_the_apps_own_installer():
    """The wizard's optional-packages page and Settings, Packages are one
    code path: installer.iss calls the exe with extras ids, never a separate
    script that installs somewhere else. Since 2026-10-07 Setup hands the ids
    to the app (pending-extras.txt), which installs them through the same
    `extras.start_bulk` as Settings, rather than freezing its own window."""
    from pathlib import Path

    iss = (Path(__file__).resolve().parents[1] / "packaging" / "windows" / "installer.iss").read_text(encoding="utf-8")
    assert "pending-extras.txt" in iss and "GetSelectedExtras('')" in iss
    assert "waituntilterminated runasoriginaluser; Check: HasSelectedExtras" not in iss
    assert "install-extras.ps1" not in iss
    import re

    #: Every id the page can hand over, whether a box sends one or several
    #: ("documents,pdfpages," since Brief 42), is a real extra.
    sent = [
        extra_id
        for group in re.findall(r"Packages \+ '([a-z,]+)'", iss)
        for extra_id in group.split(",")
        if extra_id
    ]
    assert {"semantic", "voice", "documents", "pdfpages"} <= set(sent)
    for extra_id in sent:
        assert extra_id in extras.EXTRAS_BY_ID


def test_a_cancelled_install_leaves_nothing_behind(client, monkeypatch, tmp_path):
    """The owner: "make sure the cancelled install doesnt leave it half
    installed and taking up space". pip installs a requirement's
    dependencies one by one, so a stop after torch landed used to leave it;
    its temporary folders and its download cache were left too."""
    target = tmp_path / "extras"
    (target / "already_here").mkdir(parents=True)
    monkeypatch.setattr(extras, "frozen_extras_dir", lambda: target)
    seen = {}

    class _StoppedPip:
        def __init__(self, command, **kwargs):
            seen["command"] = command
            seen["tmp"] = extras.Path(kwargs["env"]["TMPDIR"])
            (seen["tmp"] / "pip-unpack-x").mkdir()
            # Two dependencies already in place when Stop is pressed.
            (target / "torch").mkdir()
            (target / "torch-2.0.dist-info").mkdir()
            extras._state.cancelled = True
            self.stdout = []

        def wait(self):
            return -15

    monkeypatch.setattr(extras.subprocess, "Popen", _StoppedPip)
    extras._run_install(extras.EXTRAS_BY_ID["semantic"], reinstall=False)
    assert extras._state.outcome == "cancelled"
    assert sorted(p.name for p in target.iterdir()) == ["already_here"]
    assert not seen["tmp"].exists()
    assert "--no-cache-dir" in seen["command"]


def test_packages_picked_in_setup_install_on_first_launch(client, monkeypatch, app_state):
    from pathlib import Path

    from tessellate.api import app as app_module

    started = []
    monkeypatch.setattr(extras, "start_bulk", lambda action, ids=None, bundle="": (started.append((action, ids)), (True, "ok"))[1])
    pending = Path(app_state.data_dir) / "pending-extras.txt"
    pending.write_text("semantic,documents", encoding="utf-8")
    app_module._install_pending_extras()
    assert started == [("install", ["semantic", "documents"])]
    assert not pending.exists()


def test_a_pick_from_setup_is_kept_when_another_install_is_running(client, monkeypatch, app_state):
    """Brief 101c: the list was deleted before `start_bulk` accepted it, so a
    launch with an install already in hand lost what Setup was asked for."""
    from pathlib import Path

    from tessellate.api import app as app_module

    monkeypatch.setattr(extras, "start_bulk", lambda action, ids=None, bundle="": (False, "Another install is already running."))
    pending = Path(app_state.data_dir) / "pending-extras.txt"
    pending.write_text("semantic", encoding="utf-8")
    app_module._install_pending_extras()
    assert pending.read_text(encoding="utf-8") == "semantic"


def test_a_pick_from_setup_that_names_only_retired_packages_is_cleared(client, monkeypatch, app_state):
    from pathlib import Path

    from tessellate.api import app as app_module

    pending = Path(app_state.data_dir) / "pending-extras.txt"
    pending.write_text("docx", encoding="utf-8")
    app_module._install_pending_extras()
    assert not pending.exists()


def test_the_first_launch_install_is_an_activity_row_with_progress_and_stop(client, monkeypatch):
    """The owner (2026-10-07): no indicator, cannot minimise or close. The
    bulk job is a row in `/tasks` with a fraction, its packages and Stop."""
    monkeypatch.setattr(extras, "_dispatch", lambda *a, **k: None)
    started, _ = extras.start_bulk("install", ["semantic", "voice"])
    assert started is True
    try:
        job = next(t for t in client.get("/tasks").json()["tasks"] if t["kind"] == "extra")
        assert job["label"] == "Installing 2 packages"
        assert job["progress"] == 0 and len(job["steps"]) == 2
        assert job["cancellable"] is True
    finally:
        extras.cancel()
        extras._bulk.running = False
