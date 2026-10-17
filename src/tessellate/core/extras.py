"""Optional extras, installed from inside the app.

Asked for directly: *"I want a way to install optional extra dependencies like
faster whisper and other things like maybe markitdown, llama.cpp or smth in the
settings."*

Every one of these is a feature the app already has a button for and cannot
run: the dictation buttons need `faster-whisper`, `python -m tessellate
--desktop` needs `pywebview`, semantic search falls back to keywords without
`sentence-transformers`. Until now the only way to turn one on was a terminal
and a README, which for a local-first app aimed at somebody who is not a
developer is the same as not having the feature.

Three properties this deliberately has:

- **An allowlist, never a free-text package name.** The name arrives from an
  HTTP request. `pip install <whatever the body said>` is arbitrary code
  execution by design, and no amount of validating the string afterwards makes
  that safe: so the request selects an *entry from this file* and the package
  spec is never anything the client sent.
- **It reports the truth about a restart.** A package installed into a running
  interpreter is not importable by it in any way worth relying on, so every
  entry says so rather than pretending the feature is now on.
- **It runs as a background job like everything else**, which means the status
  bar and Settings → Background tasks show it without either of them learning
  anything new: see `routes_tasks.py`.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import shutil
import subprocess  # noqa: S404  # fixed args, no shell; see _install below
import sys
import sysconfig
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from tessellate.core import extra_downloads, jobs, ocr
from tessellate.core.extra_downloads import Download
from tessellate.core.subproc import NO_WINDOW

#: Reported: a failed install showed "pip exited with code 1. The log above
#: says why." in the Background tasks "Recently finished" history card, with
#: no log anywhere near it. Two separate bugs turned out to be behind that one
#: screenshot:
#:
#: 1. "The log above" was true of exactly one screen, Settings → Extras,
#:    which keeps `_state.log` on screen (`extras-log-wrap`) after the install
#:    stops. The history card renders `taskhistory.record`'s `detail` string
#:    alone, with no log ever attached to it, so the same sentence pointed at
#:    nothing there. Fixed below by folding the actual pip line into the
#:    message itself (`_pip_reason`), so it is self-contained wherever it is
#:    read: the same fix `search/searxng_manager._reason` already used for
#:    its own installer, mirrored here rather than reinvented.
#: 2. A first attempt at this routed pip's output through `logging` (see
#:    `core/logbuffer.py`, which backs Settings → Logs), but only in
#:    `_run_uninstall`'s `finally` block. `_run_install`, the path the report
#:    was actually about, never called `_logger` at all, so a failed install
#:    still never reached Settings → Logs no matter what the panel said.
#:    Never caught because nobody had reproduced a real failure end-to-end
#:    since the change: reproducing one (`tests/test_extras.py`) is what
#:    found it. Both worker functions call `_logger` now.
_logger = logging.getLogger("tessellate.extras")

# Lines that are never the reason something failed, however last they are.
#
# Pip's parting "[notice] To update, run: ...python.exe -m pip install
# --upgrade pip" is printed on almost every run and is always the last line, 
# taking the last line unconditionally would report that instead of the
# actual failure. Same list, same reasoning, as
# `search/searxng_manager._NOT_A_REASON`.
_NOT_A_REASON = (
    "[notice]",
    "to update, run",
    "you should consider upgrading",
    "warning: you are using pip version",
)


#: What pip (through urllib3 and the resolver) prints when it cannot reach
#: the package index at all: no route, no name lookup, nothing listening.
_OFFLINE_MARKERS = (
    "newconnectionerror",
    "failed to establish a new connection",
    "temporary failure in name resolution",
    "name or service not known",
    "getaddrinfo failed",
    "network is unreachable",
)

PIP_OFFLINE_MESSAGE = "Couldn't reach PyPI to download it. Check the internet connection, then try again."


def _pip_reason(log: list[str], prefix: str) -> str:
    """`prefix`, plus the most useful line pip actually printed.

    Prefers a line that names an error, falls back to the last line that
    isn't boilerplate, and falls back to `prefix` alone rather than guessing.
    Mirrors `search/searxng_manager._reason`, which solved the same "the last
    line is pip's update nag, not the failure" problem for the SearXNG
    installer; extracted here rather than imported because the source is a
    line list already split into `_state.log`, not a `CompletedProcess`.

    **Offline is said as offline.** Without a network pip retries, then ends
    on "Could not find a version that satisfies the requirement", which reads
    as a package that does not exist; its retry lines name the real cause, so
    those win, as one plain sentence (INBOX 595: a bulk install offline would
    otherwise print that misleading line under every row).
    """
    if any(marker in line.lower() for line in log for marker in _OFFLINE_MARKERS):
        return PIP_OFFLINE_MESSAGE
    useful = [
        line for line in log if not any(marker in line.lower() for marker in _NOT_A_REASON)
    ]
    if not useful:
        return prefix
    named = [
        line
        for line in useful
        if line.lower().startswith(("error", "fatal", "exception")) or "error:" in line.lower()
    ]
    return f"{prefix}: {(named or useful)[-1]}"


def find_system_python() -> str | None:
    """A real Python interpreter to hand to `subprocess`, or `None` if
    there isn't one.

    `sys.executable` is right for this in a normal venv/source install, but
    wrong in a *frozen* build (`sys.frozen`, set by PyInstaller):
    `sys.executable` there is the packaged app's own .exe, not a Python
    interpreter, so `[sys.executable, "-m", X, ...]` actually re-launches
    the app with `-m X ...` as if they were *its* own command-line flags.
    `__main__.py`'s argparse (which only knows `--desktop`/`--reset-
    password`) rejects them: confirmed from a real Windows installer
    user's support bundle: `pip install` came back as "unrecognized
    arguments: -m pip install ...", the real answer to two earlier
    "pip exited with code 1/2, no visible output" mysteries, because there
    was never any real pip output, pip was never actually run. The same
    shape reaches `venv` creation too (`search/searxng_install.py`), not
    just pip, which is why this is a general helper rather than living
    inside `_pip_base_command` alone.

    Two callers document why failing outright in frozen mode isn't
    acceptable here: INSTALL.md promises Settings → Packages works with "no
    terminal or Python install required" from the Windows installer, and
    Managed SearXNG's from-source install is offered from that same
    packaged build. So this looks for a real Python already on PATH first
    (common: many people installing an AI-adjacent app like this already
    have one from something else) rather than refusing unconditionally.
    `None` means genuinely none was found, every caller turns that into an
    honest, actionable message instead of the argparse crash.
    """
    if not getattr(sys, "frozen", False):
        return sys.executable
    for command in _python_candidates():
        real = _interpreter_behind(command)
        if real:
            return real
    return None


def _python_candidates() -> list[list[str]]:
    """Every command that might start a Python, in the order to try them.

    `py -3` last and not least: python.org's Windows installer leaves "Add
    python.exe to PATH" unticked by default and installs the `py` launcher
    instead, so the ordinary way of installing Python leaves `python` off
    PATH and `py` on it.
    """
    found = []
    for name in ("python", "python3"):
        path = shutil.which(name)
        if path:
            found.append([path])
    launcher = shutil.which("py")
    if launcher:
        found.append([launcher, "-3"])
    return found


#: Asked of each candidate: prints the interpreter's own path, or nothing for
#: a Python too old to run a current pip.
_PROBE = "import sys; print(sys.executable if sys.version_info >= (3, 8) else '')"


def _interpreter_behind(command: list[str]) -> str | None:
    """The real interpreter a command starts, or None when it starts none.

    **Run, not just found.** Windows 10 and 11 put a `python.exe` on PATH
    before any Python is installed: an App Execution Alias in
    `WindowsApps` that opens the Store and exits 9009. `which` finds it like
    any other file, so the packaged app used to hand it to pip and report a
    pip failure instead of `NO_PYTHON_FOUND_MESSAGE`. And the `py` launcher
    is not an interpreter to pass `-m pip` to on its own terms, so what comes
    back is the path the interpreter reports for itself.
    """
    try:
        done = subprocess.run(  # noqa: S603  # fixed args, no shell
            [*command, "-c", _PROBE],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    lines = (done.stdout or "").strip().splitlines()
    path = lines[-1].strip() if lines else ""
    return path if path and os.path.isfile(path) else None


def frozen_extras_dir() -> Path | None:
    """Where a packaged (frozen) build keeps the extras it installs, or
    `None` outside one.

    **Why a packaged build needs its own folder.** `find_system_python`
    lets pip run, but pip then installs into *that* Python's site-packages,
    which a PyInstaller build never looks in: its `sys.path` is its own
    bundle. So on the Windows installer every extra "installed" and none
    ever imported (owner's packaged-app log: `ModuleNotFoundError: No module
    named 'sentence_transformers'` after the auto-install had run). The
    folder sits in the data directory, beside the notes, and is named for
    the bundled interpreter's version, because a compiled wheel is only
    good for the Python it was built for.
    """
    if not getattr(sys, "frozen", False):
        return None
    from tessellate.core.config import ConfigManager

    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    return ConfigManager().data_dir / "python-extras" / tag


def activate_frozen_extras() -> None:
    """Put `frozen_extras_dir()` on `sys.path`, last, so the bundle's own
    copy of a shared library (numpy, say) still wins over the one an extra
    pulled in. Called at start-up and again when an install finishes, so a
    new extra is importable without a restart."""
    target = frozen_extras_dir()
    if target is None:
        return
    target.mkdir(parents=True, exist_ok=True)
    if str(target) not in sys.path:
        sys.path.append(str(target))
    importlib.invalidate_caches()


def _frozen_target_args() -> list[str]:
    """pip's arguments for installing into `frozen_extras_dir()`: binary
    wheels built for the *bundled* interpreter and platform, whatever
    version the system Python that runs pip happens to be. `--only-binary`
    is what pip requires before it will honour `--python-version`, and it is
    right here anyway: a packaged build has no compiler to build a source
    distribution with."""
    target = frozen_extras_dir()
    if target is None:
        return []
    platforms = _pip_platforms(sysconfig.get_platform().replace("-", "_").replace(".", "_"))
    return [
        "--target", str(target),
        "--upgrade",
        "--only-binary=:all:",
        "--implementation", "cp",
        "--python-version", f"{sys.version_info.major}.{sys.version_info.minor}",
        *(arg for platform in platforms for arg in ("--platform", platform)),
    ]


def _pip_platforms(platform: str, glibc: str | None = None) -> list[str]:
    """The wheel platform tags this interpreter runs, for pip's `--platform`.

    **On Linux the interpreter's own tag matches no wheel anyone publishes.**
    `sysconfig` says `linux_x86_64`, and PyPI's compiled wheels are tagged
    `manylinux_2_17_x86_64` and the like, which pip does not derive from it
    when `--platform` is given. So on the packaged Linux app every extra
    with a compiled wheel failed to resolve: `--install-extras docx` ended
    in "ResolutionImpossible" because no lxml wheel matched (measured on a
    Linux build). Windows (`win_amd64`) and macOS tags are used as they are.
    The manylinux tags run from this machine's glibc down to 2.17, the
    oldest any current wheel targets, plus their legacy aliases.
    """
    if not platform.startswith("linux_"):
        return [platform]
    arch = platform[len("linux_"):]
    if glibc is None:
        import platform as _platform

        libc, glibc = _platform.libc_ver()
        if libc != "glibc":
            return [platform]
    try:
        major, minor = (int(part) for part in glibc.split(".")[:2])
    except ValueError:
        return [platform]
    tags = [f"manylinux_{major}_{m}_{arch}" for m in range(minor, 16, -1)] if major == 2 else []
    if major == 2 and minor >= 17:
        tags.append(f"manylinux2014_{arch}")
    if major == 2 and minor >= 12:
        tags.append(f"manylinux2010_{arch}")
    if major == 2 and minor >= 5:
        tags.append(f"manylinux1_{arch}")
    return [*tags, platform]


def _pip_base_command() -> list[str] | None:
    """`[python, "-m", "pip"]`, or `None` if `find_system_python` found no
    real interpreter to run it with."""
    python = find_system_python()
    return [python, "-m", "pip"] if python else None


#: Shown when `_pip_base_command()` returns `None`, frozen, and no system
#: Python found. Names the actual fix (not just "something went wrong"),
#: since "install Python" is not the answer most error messages in this
#: no-terminal-required app would ever need to give.
NO_PYTHON_FOUND_MESSAGE = (
    "No Python found on this computer, and the packaged app needs one to "
    "download a package. Install Python from python.org (any recent version, "
    "the default options are fine), then try again."
)


@dataclass(frozen=True)
class Extra:
    """One optional dependency, and the honest description of what it buys."""

    #: Stable id used by the API. Never a package name from the client.
    id: str
    label: str
    #: What turns on when it is installed, in the user's terms.
    enables: str
    #: Exactly what goes to pip. A tuple because some extras are several
    #: packages that are useless apart.
    packages: tuple[str, ...]
    #: The module to import to find out whether it is already there. Import
    #: rather than `pip show`: what matters is whether *this* interpreter can
    #: use it, which is a different question from whether pip put it somewhere.
    module: str
    #: Rough download size, so nobody starts a 2 GB install by accident.
    size: str
    #: Said on the card, before the button is pressed.
    caveat: str = ""
    #: Why this cannot be installed *yet*, or "" when it can be.
    #:
    #: Two of these extras install a library the app does not call anywhere:
    #: markitdown has no import button behind it and llama-cpp-python is not
    #: wired into the chat backend. Both said so in their caveat and both still
    #: offered a working Install, which spends the user's disk and their time
    #: on a feature that does not exist, and then asks them to restart for it.
    #: A caveat under an enabled button is a warning people click past; a
    #: disabled button with the reason beside it is the same sentence made
    #: true.
    #:
    #: It is enforced in `start()` as well as drawn in the interface. The
    #: greyed-out button is a courtesy, the refusal is the rule, this file is
    #: the allowlist, so "installable" belongs here and not in `app.js`.
    #: Removal is deliberately *not* blocked: an extra installed before it was
    #: marked unavailable, or installed by hand, still needs its way out.
    unavailable: str = ""
    #: "pip" (the packages above, through pip) or "download" (the pinned
    #: files below, checked and unpacked into the data dir by
    #: `core/extra_downloads.py`). A download entry's `packages` is its
    #: name and version for the card, never anything handed to pip, and its
    #: `module` is empty: whether it is installed is a look at its folder.
    kind: str = "pip"
    downloads: tuple[extra_downloads.Download, ...] = ()
    #: The pinned release, recorded in the marker so a bump reinstalls.
    version: str = ""
    #: The licence of what is downloaded, said on the card.
    licence: str = ""
    #: The name in a progress line ("Downloading Pyodide: 3.1 of 6.8 MB").
    short_label: str = ""


#: The allowlist. Adding an entry here is the only way to make something
#: installable, which is the point.
EXTRAS: tuple[Extra, ...] = (
    Extra(
        id="pdfpages",
        label="Read scanned PDFs (pypdfium2)",
        enables="Turns the pages of a scanned PDF into images so your vision "
        "model can read them. Without it a PDF with no text layer can only be "
        "reported as a scan, not opened.",
        packages=("pypdfium2", "Pillow"),
        module="pypdfium2",
        size="~16 MB",
        caveat="Reading the pages still needs a vision or OCR model, see "
        "Settings → Models. This only supplies the images.",
    ),
    Extra(
        id="voice",
        label="Voice notes (faster-whisper)",
        enables="The dictation buttons: speak a note or a question and have it typed "
        "out, transcribed on this machine. Recordings are kept without it, "
        "and it transcribes them too.",
        packages=("faster-whisper",),
        module="faster_whisper",
        size="~50 MB, plus a model on first use",
    ),
    Extra(
        id="desktop",
        label="Desktop window (pywebview)",
        # Copy a reader of Settings sees: no command line (a stray ", `python
        # -m tessellate --desktop`" printed its backticks raw on the card).
        enables="Runs Tessellate in its own app window instead of a browser tab. "
        "On Windows it also adds a tray icon (open, view logs, restart, quit), "
        "so closing the window keeps the app running; elsewhere closing the "
        "window quits.",
        # pystray + Pillow are the tray icon; bundled with the same button
        # because a desktop window with no tray is the "always-open terminal"
        # complaint this was built to fix (see __main__._start_tray). Neither
        # blocks the window if missing, `_start_tray` just returns None and
        # the window closes for real, same as before the tray existed.
        packages=("pywebview", "pystray", "Pillow"),
        module="webview",
        size="~5 MB",
    ),
    Extra(
        id="semantic",
        label="Search by meaning (sentence-transformers)",
        enables="Searching for what you meant rather than the words you used. "
        "Without it, search falls back to keywords and everything else works.",
        packages=("sentence-transformers",),
        module="sentence_transformers",
        size="~2 GB: it pulls in PyTorch",
        caveat="The big one. On Windows this needs the CPU build of torch; see "
        "the README's troubleshooting section if the install fails with "
        "a DLL error.",
    ),
    Extra(
        id="documents",
        label="Import documents (markitdown)",
        enables="Turns PDFs, Word files and slides into notes: the "
        "Import a document button in Settings, Import & export.",
        # The three converter groups, not bare markitdown: since 0.1 a plain
        # `pip install markitdown` reads HTML and text and raises on exactly
        # the PDFs, Word files and slides this card (and the installer's
        # Documents box) promises. `xlsx`, `outlook` and the rest are left
        # out: nothing here offers them, and `all` pulls in Azure clients.
        packages=("markitdown[pdf,docx,pptx]",),
        module="markitdown",
        size="~20 MB",
    ),
    Extra(
        id="ocr",
        label="Search inside images (Tesseract OCR)",
        enables="Text found in an uploaded image (a whiteboard photo, a "
        "scanned page) becomes searchable in the Library's images, so a search "
        "for a word on that whiteboard finds the photo. The OCR workspace can "
        "also read a page with it, in the language you choose here.",
        packages=("pytesseract", "Pillow"),
        module="pytesseract",
        size="~10 MB",
        caveat="Also needs the separate 'tesseract' program on this computer, "
        "pip can't install that part, since it isn't a Python package. This "
        "button tries to install it automatically too (winget/brew/apt/dnf/"
        "pacman, whichever this system has); if that doesn't work, install it "
        "by hand (see INSTALL.md). Without it, uploads still work, they just "
        "get no searchable text.",
    ),
    #: **RapidOCR (WORLD_CLASS_PLAN row 31 item 97).** The owner asked for an
    #: OCR alternative to pytesseract. PaddleOCR's models on onnxruntime,
    #: pip-installable whole (no system program to fetch, the half of
    #: Tesseract that fails most), Apache-2.0. Optional on the person's own
    #: press like every row here, never a dependency.
    #: Tesseract stays the reader whenever it is ready (`ocr.engine`). In the
    #: Vision bundle beside it, deliberately: Tesseract's system program is
    #: the half an install most often fails to fetch (no winget, no admin), and
    #: a bundle whose promise is "read the text in pictures" should keep it on
    #: a machine where that half fails, at the cost of 60 MB that sits unused
    #: where Tesseract installs cleanly.
    #: The 1.x package name, whose `RapidOCR` call `ocr._rapidocr_lines` reads
    #: (it reads the 2.x `rapidocr` package's result shape too).
    Extra(
        id="rapidocr",
        label="Read images without Tesseract (RapidOCR)",
        enables="A second local reader for pictures and scanned pages, with "
        "nothing else to install: their text becomes searchable and the OCR "
        "workspace can read a page with it. Used when Tesseract isn't ready; "
        "Tesseract stays the reader whenever it is.",
        packages=("rapidocr_onnxruntime",),
        module="rapidocr_onnxruntime",
        size="~60 MB",
        caveat="Its models read English and Chinese; the language chosen for "
        "Tesseract doesn't apply to it.",
    ),
    #: **Pyodide (INBOX 404).** The owner, 2026-09-24: "Run Python files: yes,
    #: as an opt-in extra". CPython compiled to WebAssembly, run by Run on a
    #: .py document inside the same sandbox as JavaScript, from these files
    #: served by `api/run_sandbox.py`. `pyodide-core` is the smallest release
    #: archive: the runtime and the standard library, no third-party
    #: packages, so `import numpy` says it is not there rather than
    #: downloading it. Only the six files the runtime loads are kept (the
    #: archive also carries a Node launcher and a python.exe nothing here
    #: runs). Licence: MPL-2.0 (its package.json), CPython's own under the
    #: PSF licence.
    #:
    #: **To bump:** take the newest non-prerelease tag from
    #: github.com/pyodide/pyodide/releases, download
    #: `pyodide-core-<tag>.tar.bz2`, and write its tag, size and
    #: `sha256sum` here; `tar tjf` it to check the six member names still
    #: exist. The marker records the version, so an installed older copy
    #: shows as not installed and Install fetches the new one.
    Extra(
        id="pyodide",
        label="Run Python files (Pyodide)",
        short_label="Pyodide",
        enables="Run on a .py document: the script runs in the same sandbox as "
        "JavaScript, with no network and none of your notes, and its print "
        "output and errors come back in the Output panel with a link to each "
        "line. Works offline once installed.",
        packages=("pyodide-core 314.0.7",),
        module="",
        size="~7 MB download, 14 MB on disk",
        caveat="The standard library only: packages such as numpy are not "
        "included. input() reads its lines from the Input box in the Output panel.",
        kind="download",
        version="314.0.7",
        licence="MPL-2.0",
        downloads=(
            Download(
                url="https://github.com/pyodide/pyodide/releases/download/314.0.7/"
                "pyodide-core-314.0.7.tar.bz2",
                sha256="2abdcc2e35208af406e07724cffa85bc582ced97e9028383ecf5462541393f95",
                size=6757104,
                unpack="tar",
                members=tuple(
                    (f"pyodide/{name}", name)
                    for name in (
                        "pyodide.mjs",
                        "pyodide.asm.mjs",
                        "pyodide.asm.wasm",
                        "python_stdlib.zip",
                        "pyodide-lock.json",
                        "package.json",
                    )
                ),
            ),
        ),
    ),
    #: **needle (INBOX 302).** The owner, 2026-09-24: "Yes, as an extra"
    #: (opt-in, telemetry forced off). A 121M-parameter tool-calling model
    #: from Cactus Compute: `ai/needle_provider.py` drives its engine through
    #: `ctypes`, and the agent uses it to pick tools when no Ollama or
    #: OpenAI-compatible backend answers. It writes no prose.
    #:
    #: Licence **Apache-2.0**, checked 2026-09-24 for both halves: the
    #: LICENSE file at the pinned commit (downloaded with the rest, below)
    #: and the Hugging Face card's `license: apache-2.0`. The engine is the
    #: `libneedle3` library out of the per-platform wheels the model repo
    #: publishes under `python/` (the Python package itself is not used);
    #: every URL is pinned to commit b274efc, so the files cannot move under
    #: the hashes. Engine 3.0.1 is the newest published there; needle's
    #: fetcher names 3.0.2, which the repo does not carry.
    #:
    #: **To bump:** `curl https://huggingface.co/api/models/Cactus-Compute/
    #: needle3/tree/main/python` lists each wheel with its `lfs.oid`, which
    #: is its sha256; take the new commit from `/api/models/Cactus-Compute/
    #: needle3` (`sha`) and the weights' hash from the root listing.
    Extra(
        id="needle",
        label="Tool calling without Ollama (needle)",
        short_label="needle",
        enables="A small built-in model the assistant uses to pick and fill "
        "tools (make a note, set a reminder, search) when no Ollama or other "
        "model server is running. It runs tools; it does not write replies.",
        packages=("needle 3.0.1",),
        module="",
        size="~36 MB",
        caveat="Runs offline, inside the app. needle's own tools send usage "
        "data by default; Tessellate uses only its engine, checks at install "
        "that it imports no network calls, and switches that setting off "
        "anyway. Nothing for you to do.",
        kind="download",
        version="3.0.1",
        licence="Apache-2.0",
        downloads=(
            *(
                Download(
                    url="https://huggingface.co/Cactus-Compute/needle3/resolve/"
                    "b274efcb211a9eef48c9a88da4b43bd569696a39/python/"
                    f"cactus_needle-3.0.1-py3-none-{tag}.whl",
                    sha256=sha,
                    size=size,
                    unpack="zip",
                    members=((f"needle/libneedle3.{ext}", f"libneedle3.{ext}"),),
                    platform=key,
                    inspect_imports=True,
                )
                for key, tag, ext, sha, size in (
                    ("linux-x86_64", "manylinux2014_x86_64", "so",
                     "05770ef9a85686583968ea15f62f9ad44217e078efdaa99559d3208bb8a369b0", 536871),
                    ("linux-aarch64", "manylinux2014_aarch64", "so",
                     "fc0c550b64627ed20101d1ac6de736bf0d15fb592d649f24bacba4e7340fc3df", 517746),
                    ("linux-x86_64-musl", "musllinux_1_2_x86_64", "so",
                     "1b2f5f560fcf8d2033c0ade7ea48d8f2f228cb17f53331bf844fcceb955440e0", 537929),
                    ("linux-aarch64-musl", "musllinux_1_2_aarch64", "so",
                     "ec307274ed14d8a11be448e1546d3a330704a8d76a96a2f99de12ca14ed8ee64", 517367),
                    ("macos-arm64", "macosx_11_0_arm64", "dylib",
                     "161c3aacfb6e54443925b389a69eb58a1861e60af19bbdf8f39d89992c5d7436", 387232),
                    ("macos-x86_64", "macosx_11_0_x86_64", "dylib",
                     "941883e51fb2530706f1a115a0ea0062bb37501edaad8a6f08b85e12c4f5ca76", 431615),
                    ("windows-x86_64", "win_amd64", "dll",
                     "7d4467726814ab18d9ce32a8a5cc23d1198a2c0557c613a00bef738121903e2f", 553581),
                    ("windows-arm64", "win_arm64", "dll",
                     "dfa6f8c15ca979bbe7c3e0579efdd8bf7b7afc75355e063cd00e6ac7732c9896", 493234),
                )
            ),
            Download(
                url="https://huggingface.co/Cactus-Compute/needle3/resolve/"
                "b274efcb211a9eef48c9a88da4b43bd569696a39/needle3.cact",
                sha256="c9d915eca282ed42d1a09b143b592adb4cc6744ffe2d294adf5cfc5548170c38",
                size=35335380,
                unpack="file",
                members=(("", "needle3.cact"),),
            ),
            Download(
                url="https://huggingface.co/Cactus-Compute/needle3/resolve/"
                "b274efcb211a9eef48c9a88da4b43bd569696a39/LICENSE",
                sha256="cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
                size=11358,
                unpack="file",
                members=(("", "LICENSE"),),
            ),
        ),
    ),
    #: **The offline translator (WORLD_CLASS 28.5 row 10, Brief 83).** The
    #: owner, 2026-10-10: "What about ai free translations?" Bergamot, the
    #: engine behind Firefox's translations (marian-nmt compiled to
    #: WebAssembly), and one language pair, English to Spanish. The engine
    #: runs in a Web Worker in the page (`frontend/js/translate-worker.js`)
    #: under the app's own policy, which already allows WebAssembly for the
    #: grammar checker; these files are served from the data dir by
    #: `api/routes_translate.py`, never from the repository.
    #:
    #: Licences, read 2026-10-10: the engine is MPL-2.0 (the repository's
    #: LICENSE, downloaded with it, and the npm package's `license`); the
    #: model files are MPL-2.0 (`mozilla/translations` README). The WASM
    #: carries marian-nmt and intgemm (MIT), sentencepiece, ruy and
    #: ssplit-cpp (Apache-2.0); docs/THIRD_PARTY.md lists them.
    #:
    #: Measured (Brief 83, Node 22 and Chromium): a 94-word paragraph in
    #: 340 to 550 ms on one thread; the first call pays about 1.4 s to load.
    #:
    #: **To bump:** the engine is `@browsermt/bergamot-translator` on npm
    #: (`npm view @browsermt/bergamot-translator dist`, then `sha256sum` the
    #: tarball); a model's three files and their sizes are in the registry
    #: at `mozilla/translations`' `db/models.json`. A new pair is a new
    #: entry here and a row in `ai/translate.PAIRS`.
    Extra(
        id="translate",
        label="Translate offline (Bergamot, English to Spanish)",
        short_label="the translator",
        enables="Translate this, in the command palette: a passage of a note, "
        "a document or a reading turned into Spanish on this computer in "
        "about a second, with no model and nothing sent anywhere.",
        packages=("bergamot-translator 0.4.9", "en-es model"),
        module="",
        size="~27 MB download, 42 MB on disk",
        caveat="A small on-device model: good for the gist and a first draft, "
        "not for legal or medical text. English to Spanish only for now.",
        kind="download",
        version="0.4.9-enes-1",
        licence="MPL-2.0",
        downloads=(
            Download(
                url="https://registry.npmjs.org/@browsermt/bergamot-translator/-/"
                "bergamot-translator-0.4.9.tgz",
                sha256="9011be93222d839d7448ffdf00549d53ce8f541fd782ffc79779d1756397c41f",
                size=1852075,
                unpack="tar",
                members=tuple(
                    (f"package/worker/{name}", name)
                    for name in ("bergamot-translator-worker.js", "bergamot-translator-worker.wasm")
                ),
            ),
            Download(
                url="https://raw.githubusercontent.com/browsermt/bergamot-translator/v0.4.5/LICENSE",
                sha256="1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5",
                size=16725,
                unpack="file",
                members=(("", "LICENSE"),),
            ),
            *(
                Download(
                    url="https://storage.googleapis.com/moz-fx-translations-data--303e-prod-"
                    "translations-data/models/en-es/retrain_hr_fix_names_CUAEXUHoQum_cFqh-"
                    f"ZAryw/exported/{name}.gz",
                    sha256=sha,
                    size=size,
                    unpack="gzip",
                    members=(("", name),),
                )
                for name, sha, size in (
                    ("model.enes.intgemm.alphas.bin",
                     "fe4025fde24a4d5f80533cfb7acd53d0eb7f194dfc2d8f427f0d4563cfb6ac06", 22698792),
                    ("lex.50.50.enes.s2t.bin",
                     "37a067966f28ff0ba430fddb7412bc5b07afa2cd2fd5a46d9ad74045a1a06380", 2265250),
                    ("vocab.enes.spm",
                     "ae2760c04bc6eb5362b16e5c2f145c376bb04bac421c33ba3c0766805e6f03b3", 409312),
                )
            ),
        ),
    ),
    Extra(
        id="localllm",
        label="Built-in model runner (llama-cpp-python)",
        enables="Runs a GGUF model in this process, for machines where "
        "installing Ollama is not an option.",
        packages=("llama-cpp-python",),
        module="llama_cpp",
        size="~30 MB, and it compiles on some platforms",
        # Was "Not wired into the chat backend yet", false, and misleading
        # in the specific way that costs the most: it reads as "llama.cpp
        # is unsupported," when the supported route (`llama-server`, which
        # speaks the same API `ai/openai_client.py` already does) needs no
        # extra here at all. What actually isn't built is *this* extra
        # specifically: running a GGUF in-process, inside this app, rather
        # than as a separate server you point the app at. See the Models
        # screen's provider picker for the llama-server recipe.
        unavailable="llama.cpp itself is already supported, run "
        "llama-server and point Settings → Models at it as an "
        "OpenAI-compatible backend, no install here needed. This extra is "
        "specifically for running a GGUF in-process instead of as a "
        "separate server, which isn't built: it means shipping a compiled "
        "wheel per platform and accelerator (CUDA/ROCm/Metal/CPU) and "
        "owning model load/unload, for a capability llama-server already "
        "gives you today.",
    ),
    #: **Live captions (WORLD_CLASS_PLAN 28.5 row 9, Brief 82).** whisper.cpp's
    #: `whisper-server` (MIT), a separate executable, never a Python import.
    #: The captions code in `ai/captions.py` already speaks to it through
    #: `TESSELLATE_CAPTIONS_URL`; what is missing is the pinned download. A
    #: `Download` needs a URL, a sha256 and a byte size read from a release
    #: asset, and the release page was not readable when this was written
    #: (caption82-1010.md), so a guessed pin would be a fabricated checksum.
    #: Listed so Settings, Packages names the feature and says what is left.
    #: Not `kind="download"` until then: a download row is a pinned version
    #: and files (test_extras_download.py), and this one has neither.
    Extra(
        id="captions",
        label="Live captions (whisper.cpp)",
        short_label="Live captions",
        enables="Live captions over any screen: what the microphone hears, "
        "written as you speak and saved as a note, on this computer.",
        packages=("whisper.cpp server",),
        module="",
        size="~35 MB for the helper and the tiny.en model",
        licence="MIT",
        unavailable="The helper isn't packaged for one-click install yet. To "
        "try captions now, run whisper.cpp's whisper-server on this computer "
        "and start Tessellate with TESSELLATE_CAPTIONS_URL set to its address "
        "(for example http://127.0.0.1:8080).",
    ),
)


def _extra_size(extra_id: str) -> str:
    found = next((extra for extra in EXTRAS if extra.id == extra_id), None)
    return (found.size or "").lstrip("~") if found else ""


#: The OCR workspace's offer says each install's size from this table
#: (`ocr.engine_state`); ocr.py cannot import this module (the cycle lint).
ocr.extra_size = _extra_size

def download_mb(extra: "Extra") -> int:
    """The `size` text ("~2 GB: ...", "~16 MB") as megabytes, for one sentence
    that says how much a first setup downloads; 0 when it cannot be read."""
    found = re.match(r"~?\s*([\d.]+)\s*(GB|MB)", extra.size)
    if not found:
        return 0
    value = float(found.group(1)) * (1000 if found.group(2) == "GB" else 1)
    return int(round(value))


EXTRAS_BY_ID = {extra.id: extra for extra in EXTRAS}


@dataclass(frozen=True)
class Bundle:
    """A named group of extras that one kind of work needs together.

    INBOX 595, the owner: "should we bundle multiple packages together for
    bulk download if various features need multiple libraries". A bundle is
    only a list of ids from the allowlist above, so it can never name a
    package the allowlist does not: installing one is installing each of its
    entries in turn, with each entry's own guards (`start_bulk`).
    """

    id: str
    label: str
    #: One sentence, said under the bundle's name.
    about: str
    extras: tuple[str, ...]


#: Defined once, here; `GET /extras` carries them and the Packages screen
#: draws them. An entry may be in more than one (pdfpages reads scans for
#: both Documents and Vision), and every entry is in at least one
#: (`tests/test_extras_bundles.py`), so nothing is reachable only by hand.
BUNDLES: tuple[Bundle, ...] = (
    Bundle(
        id="documents",
        label="Documents",
        about="Import PDFs, Word files and slides, and read scanned PDFs.",
        extras=("documents", "pdfpages"),
    ),
    Bundle(
        id="vision",
        label="Vision",
        about="Read the text in pictures and in scanned pages.",
        extras=("ocr", "rapidocr", "pdfpages"),
    ),
    Bundle(
        id="ai",
        label="AI",
        about="Search by meaning, and tool calling and models without a separate runner.",
        extras=("semantic", "needle", "localllm"),
    ),
    Bundle(
        id="voice",
        label="Voice",
        about="Dictate notes and questions, transcribed on this computer.",
        extras=("voice",),
    ),
    Bundle(
        id="captions",
        label="Live captions",
        about="Captions over any screen as you speak, written on this computer.",
        extras=("captions",),
    ),
    Bundle(
        id="desktop",
        label="Desktop",
        about="Tessellate in its own window, with a tray icon on Windows.",
        extras=("desktop",),
    ),
    Bundle(
        id="languages",
        label="Languages",
        about="Translate a passage into Spanish on this computer, with no model.",
        extras=("translate",),
    ),
    Bundle(
        id="code",
        label="Code",
        about="Run Python files inside the app, offline.",
        extras=("pyodide",),
    ),
)

BUNDLES_BY_ID = {bundle.id: bundle for bundle in BUNDLES}


@dataclass
class InstallState:
    """What one install is doing, for `/tasks` and the panel."""

    running: bool = False
    extra_id: str = ""
    step: str = ""
    log: list[str] = field(default_factory=list)
    started: float = 0.0
    outcome: str = ""  # "" while running, then completed | failed
    #: The live pip process, so `cancel()` below can actually stop it. Asked
    #: for directly: "allow the quitting/killing of background tasks as well".
    #: pip has no cooperative stop, it is a subprocess spending minutes
    #: building a wheel: so the only honest way to quit one is to terminate
    #: it, which is what a user pressing Quit is asking for. Kept off the wire:
    #: `status()` and `/tasks` build their own dicts and never touch this.
    process: object | None = None
    #: True once someone asked for it to stop, so the failure that follows is
    #: reported as a cancellation rather than as pip having gone wrong.
    cancelled: bool = False
    #: True when the app began this install itself (search by meaning found
    #: its package missing) rather than a person pressing Install, so the
    #: interface can say so and offer "Don't install" (routes_tasks, `auto`).
    auto: bool = False


#: One at a time, process-wide. Two pips against one environment is a way to
#: corrupt it, and there is no reason to want it.
_state = InstallState()
_lock = threading.Lock()

#: Bounded, like the SearXNG installer's log: this is a progress indicator, not
#: a build record, and pip on a large wheel prints a great deal.
MAX_LOG_LINES = 200

#: What a bulk action can do. Reinstall is pip's `--force-reinstall` through
#: the same runner as a single Reinstall (`_run_install`), not an uninstall
#: and an install: one pip call that replaces the files in place leaves the
#: package usable if it is stopped half way, where a removal followed by a
#: failed download leaves nothing.
BULK_ACTIONS = ("install", "uninstall", "reinstall")
_BULK_VERBS = {
    "install": ("Installing", "Installed"),
    "uninstall": ("Removing", "Removed"),
    "reinstall": ("Reinstalling", "Reinstalled"),
}


@dataclass
class BulkState:
    """A bulk action: several extras, one after another, as one pool job.

    `_state` above still describes the package in hand, so `/tasks`, the log
    and Quit work on a bulk exactly as on a single install; this adds the
    list, each entry's outcome and sentence, and whether the rest should run.
    """

    running: bool = False
    action: str = ""
    bundle: str = ""
    #: `{"id", "label", "outcome", "message"}` per extra, in the order asked.
    #: outcome: queued, running, completed, failed, skipped or cancelled.
    items: list[dict] = field(default_factory=list)
    started: float = 0.0
    #: Set by `cancel()`: the package in hand stops and the rest never start.
    cancelled: bool = False
    #: When it is over: completed, failed (one or more did) or cancelled.
    outcome: str = ""
    message: str = ""


_bulk = BulkState()

#: An installed extra's version and its own files' size, by id. Reading
#: package metadata walks `sys.path`, and the Packages screen polls while
#: anything runs, so it is read once and forgotten whenever an install or a
#: removal ends (`_forget_footprints`).
_footprints: dict[str, tuple[str, int | None]] = {}


def is_installed(extra: Extra) -> bool:
    """Can this interpreter import it *right now*?

    `find_spec` rather than a real import: importing torch to answer a status
    question would cost seconds and a great deal of memory on a screen the user
    is only looking at.

    A download extra has no module: it is installed when its folder holds
    the pinned version (`extra_downloads.is_installed`), a disk look.
    """
    if extra.kind == "download":
        return extra_downloads.is_installed(extra)
    try:
        found = importlib.util.find_spec(extra.module) is not None
    except (ImportError, ValueError):
        # A half-installed package can raise here rather than returning None.
        # "Not usable" is the honest answer either way.
        return False
    #: **OCR is two halves, and the row said "Installed" for one** (INBOX 443
    #: (3)). `pytesseract` importing proves the Python wrapper, not the
    #: `tesseract` program, so the Packages row showed a green tick on a
    #: machine whose Library reads nothing. Installed means it can read, which
    #: is also what lets the Install button run again to fetch the program.
    if extra.id == "ocr":
        return found and ocr.tesseract_available()
    return found


def status() -> list[dict]:
    """Every extra, with whether it is installed and whether it is installing,
    and once installed its version and the size of its own files."""
    rows = []
    for extra in EXTRAS:
        row = _status_row(extra)
        version, disk = footprint(extra) if row["installed"] else ("", None)
        row["version"] = version
        row["disk_bytes"] = disk
        row["bundles"] = [bundle.id for bundle in BUNDLES if extra.id in bundle.extras]
        #: Waiting its turn in a bulk action, so the row can say so rather
        #: than offering an Install that would be refused.
        row["queued"] = _bulk.running and any(
            item["id"] == extra.id and item["outcome"] == "queued" for item in _bulk.items
        )
        rows.append(row)
    return rows


def _status_row(extra: Extra) -> dict:
    return {
        "id": extra.id,
        "label": extra.label,
        "enables": extra.enables,
        "size": extra.size,
        #: The OCR caveat explains how the program gets installed; once it
        #: can read, it is noise under a green "Installed".
        "caveat": "" if extra.id == "ocr" and is_installed(extra) else extra.caveat,
        "unavailable": unavailable_reason(extra),
        #: Whether Settings may offer Remove: a packaged build is its own
        #: desktop window, so that one is kept (INBOX 904 B27).
        "removable": not removal_locked(extra),
        "locked": removal_locked(extra),
        "packages": list(extra.packages),
        "kind": extra.kind,
        "licence": extra.licence,
        #: Where a download comes from, for the confirm dialog ("pypi.org"
        #: for pip, which is what pip reaches by default).
        "source": extra_downloads.source(extra) if extra.kind == "download" else "pypi.org",
        "installed": is_installed(extra),
        "installing": _state.running and _state.extra_id == extra.id,
        "step": _state.step if _state.running and _state.extra_id == extra.id else "",
    }


def bundles() -> list[dict]:
    """The bundles, for `GET /extras`."""
    return [
        {"id": bundle.id, "label": bundle.label, "about": bundle.about, "extras": list(bundle.extras)}
        for bundle in BUNDLES
    ]


def footprint(extra: Extra) -> tuple[str, int | None]:
    """(version, bytes on disk) of an installed extra, or ("", None).

    A pip extra is read from its packages' own metadata: the version of the
    first package it names (the one the label is about), and the size its
    RECORD files list for every package it names, never their dependencies,
    the same line `_run_uninstall` draws: sentence-transformers is a few
    megabytes, and the PyTorch it pulled in belongs to whoever else uses it.
    A packaged build reads its own folder (`frozen_extras_dir`). A download
    extra is its pinned version and its folder.
    """
    cached = _footprints.get(extra.id)
    if cached is not None:
        return cached
    try:
        found = _read_footprint(extra)
    except Exception:  # noqa: BLE001  # a status row must never fail on odd metadata
        _logger.debug("couldn't read the footprint of %s", extra.id, exc_info=True)
        found = ("", None)
    _footprints[extra.id] = found
    return found


def _read_footprint(extra: Extra) -> tuple[str, int | None]:
    if extra.kind == "download":
        folder = extra_downloads.folder(extra)
        if not folder.is_dir():
            return "", None
        total = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
        return extra.version, total
    from importlib import metadata

    target = frozen_extras_dir()
    wanted = [_canonical(_requirement_name(package)) for package in extra.packages]
    found: dict[str, metadata.Distribution] = {}
    if target is not None:
        for dist in metadata.distributions(path=[str(target)]):
            name = _canonical(str(dist.metadata.get("Name") or ""))
            if name in wanted:
                found.setdefault(name, dist)
    else:
        for name in wanted:
            try:
                found[name] = metadata.distribution(name)
            except metadata.PackageNotFoundError:
                continue
    if not found:
        return "", None
    first = found.get(wanted[0]) or next(iter(found.values()))
    total = sum(entry.size or 0 for dist in found.values() for entry in (dist.files or []))
    return str(first.version or ""), total or None


def installed_bytes() -> int:
    """What the installed extras weigh together, from their own files only
    (the same line `footprint` draws), for the storage breakdown. Reads the
    cache the Packages screen fills, so it costs one metadata walk the first
    time and nothing after."""
    total = 0
    for extra in EXTRAS:
        try:
            if is_installed(extra):
                total += footprint(extra)[1] or 0
        except Exception:  # noqa: BLE001  # a number for a bar must never fail the page
            _logger.debug("couldn't weigh %s", extra.id, exc_info=True)
    return total


def _forget_footprints() -> None:
    _footprints.clear()


def bulk_status() -> dict:
    """The bulk action in hand or the last one, for `GET /extras`."""
    done = sum(1 for item in _bulk.items if item["outcome"] not in ("queued", "running"))
    return {
        "running": _bulk.running,
        "action": _bulk.action,
        "bundle": _bulk.bundle,
        "items": [dict(item) for item in _bulk.items],
        "done": done,
        "total": len(_bulk.items),
        "outcome": _bulk.outcome,
        "message": _bulk.message,
    }


def bulk() -> BulkState:
    return _bulk


def removal_locked(extra: Extra) -> str:
    """Why this extra cannot be removed here, or "".

    The packaged app (`sys.frozen`) is its own desktop window: "I shouldn't be
    able to uninstall the desktop view in the packaged windows app" (INBOX 904
    B27). Removing pywebview there leaves an app with no way to open. A source
    install runs in a browser tab and may take it out.
    """
    if extra.id == "desktop" and getattr(sys, "frozen", False):
        return "The desktop window is how the packaged app opens, so it stays. Reinstall it if it misbehaves."
    return ""


def unavailable_reason(extra: Extra) -> str:
    """Why this cannot be installed here, or "": the entry's own reason, or
    for a download extra with per-platform files, none built for this
    computer (`extra_downloads.platform_reason`)."""
    if extra.unavailable:
        return extra.unavailable
    if extra.kind == "download":
        return extra_downloads.platform_reason(extra)
    return ""


def current() -> InstallState:
    return _state


def cancel() -> tuple[bool, str]:
    """Stop the running pip, if there is one. Returns (stopped, message).

    **Terminate, not a flag.** Everything else in this app that can be quit
    checks a cooperative `cancel_requested` between steps, because everything
    else is a loop this app wrote. pip is not: it is a child process that may
    be five minutes into compiling a wheel and will not look at anything we
    set. `terminate()` is the only stop that stops it, and it is what someone
    who pressed Quit meant.

    Not left half-installed: pip writes each package through a staging
    directory, but a requirement's dependencies land one by one, so
    `_run_install` rolls back whatever is new once pip has exited
    (`_roll_back`) and removes pip's temporary folder. The extras panel
    re-reads `is_installed` on its next poll and says "not installed".
    """
    if _bulk.running:
        #: A bulk action stops whole: the package in hand the way a single
        #: one stops (below), and none of the rest starts (`_run_bulk`).
        #: Between two packages nothing is running yet, and the flag alone
        #: is the stop.
        _bulk.cancelled = True
        if not _state.running:
            return True, "Stopping before the next package."
    process = _state.process
    extra = EXTRAS_BY_ID.get(_state.extra_id)
    if _state.running and extra is not None and extra.kind == "download":
        # A download is this app's own loop, so it is stopped the cooperative
        # way: `extra_downloads._fetch` checks the flag between chunks, and the
        # staging folder goes with it.
        _state.cancelled = True
        _state.step = "Stopping…"
        return True, "Stopping the download."
    if not _state.running or process is None:
        if _bulk.running:
            return True, "Stopping before the next package."
        return False, "Nothing is installing."
    _state.cancelled = True
    _state.step = "Stopping…"
    try:
        process.terminate()
    except Exception as exc:  # noqa: BLE001  # an already-dead child is a win
        _logger.debug("couldn't terminate pip: %s", exc)
    return True, "Stopping the install."


def _requirement_name(spec: str) -> str:
    """`markitdown[pdf,docx]>=0.1` -> `markitdown`: the project a requirement
    names, which is what an uninstall takes."""
    return re.split(r"[\[<>=!~;\s]", spec, maxsplit=1)[0]


def _canonical(name: str) -> str:
    """PEP 503's normal form, so `python-docx` finds `python_docx`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _remove_from_frozen_target(extra: Extra, target: Path) -> None:
    """Remove an extra from a packaged build's own folder, without pip.

    **Why not pip.** `pip uninstall` has no `--target`: it removes from the
    site-packages of the Python running it. On the packaged app that is the
    borrowed system Python (`find_system_python`), which does not have the
    extra, because `_frozen_target_args` put it in the data folder instead.
    So it warned, exited 0, and the card said "removed" over a package that
    still imported; or, for someone who had the same package in their own
    Python, it removed *that* one. The folder's own metadata says exactly
    what each wheel put there (its RECORD), so this deletes that list and
    nothing else, and needs no Python at all.

    Only files inside `target` are touched, whatever a RECORD says, and only
    the projects the entry names, never their dependencies: the same rule
    `_run_uninstall` states for pip.
    """
    from importlib import metadata

    root = target.resolve()
    wanted = {_canonical(_requirement_name(package)) for package in extra.packages}
    removed: list[str] = []
    stuck: list[str] = []
    touched_dirs: set[Path] = set()
    for dist in metadata.distributions(path=[str(root)]):
        name = str(dist.metadata.get("Name") or "")
        if _canonical(name) not in wanted:
            continue
        _state.step = f"Removing {name}"
        for entry in dist.files or []:
            path = Path(str(dist.locate_file(entry))).resolve()
            if root not in path.parents or not path.is_file():
                continue
            try:
                path.unlink()
                touched_dirs.add(path.parent)
            except OSError:
                stuck.append(str(path.relative_to(root)))
        info_dir = getattr(dist, "_path", None)
        if info_dir is not None and root in Path(info_dir).resolve().parents:
            shutil.rmtree(info_dir, ignore_errors=True)
        removed.append(name)
    # A package's folder is left holding the `__pycache__` Python wrote after
    # the install, which no RECORD lists. Deepest first, up to the root.
    for folder in sorted(touched_dirs, key=lambda p: len(p.parts), reverse=True):
        while folder != root and root in folder.parents and folder.is_dir():
            leftovers = [child for child in folder.iterdir() if child.name != "__pycache__"]
            if leftovers:
                break
            shutil.rmtree(folder, ignore_errors=True)
            folder = folder.parent
    _state.log.extend(f"Removed {name}" for name in removed)
    if stuck:
        _state.log.extend(f"In use: {path}" for path in stuck[:20])
        _state.outcome = "failed"
        _state.step = (
            f"Some of {extra.label} is still in use. Restart Tessellate and "
            "remove it again: Windows keeps files that are open."
        )
    elif removed:
        _state.outcome = "completed"
        _state.step = f"{extra.label} removed: restart Tessellate to free it."
    else:
        _state.outcome = "completed"
        _state.step = f"{extra.label} was not installed, so there was nothing to remove."


def _run_uninstall(extra: Extra) -> None:
    """pip uninstall, with the same bookkeeping the install has.

    Only the packages this entry named, never their dependencies: removing
    `sentence-transformers` leaves torch behind, which is right, it is 2 GB
    that something else may be using, and a button labelled "uninstall one
    thing" must not quietly take five.
    """
    try:
        target = frozen_extras_dir()
        if target is not None:
            _remove_from_frozen_target(extra, target)
            return
        pip_base = _pip_base_command()
        if pip_base is None:
            _state.outcome = "failed"
            _state.step = NO_PYTHON_FOUND_MESSAGE
            return
        command = [
            *pip_base,
            "uninstall",
            "-y",
            "--disable-pip-version-check",
            *(_requirement_name(package) for package in extra.packages),
        ]
        _state.step = f"pip uninstall {' '.join(extra.packages)}"
        process = subprocess.Popen(  # noqa: S603  # fixed args from the allowlist, no shell
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=NO_WINDOW,
        )
        _state.process = process
        for line in process.stdout or []:
            line = line.rstrip()
            if not line:
                continue
            _state.log.append(line)
            del _state.log[:-MAX_LOG_LINES]
            _state.step = line[:120]
        code = process.wait()
        _state.outcome = "completed" if code == 0 else "failed"
        _state.step = (
            f"{extra.label} removed: restart Tessellate to free it."
            if code == 0
            else _pip_reason(_state.log, f"pip exited with code {code}")
        )
    except (OSError, subprocess.SubprocessError):
        # The exception text can carry a filesystem path or other local detail,
        # and `_state.step` goes straight to the browser via `/extras` and
        # `/tasks`. Flagged by CodeQL as `py/stack-trace-exposure`, same shape
        # as `embedmodels.remove`. Full detail goes to the log, which only the
        # owner of the machine reads; the caller gets the fact, not the internals.
        _logger.exception("Couldn't run pip to remove %s", extra.label)
        _state.outcome = "failed"
        _state.step = "Couldn't run pip: see Settings → Logs for why."
    finally:
        _state.process = None
        if _state.cancelled:
            # Terminating pip mid-download makes it exit non-zero, which the
            # branches above have already written up as a failure. It wasn't
            # one, someone pressed Quit, and a task history full of
            # "Installing X failed" for things nobody wanted is how a history
            # stops being read.
            _state.outcome = "cancelled"
            _state.step = "Stopped before it finished."
        if _state.outcome == "failed":
            _logger.error(
                "Removing %s failed: %s\n%s",
                extra.label,
                _state.step,
                "\n".join(_state.log[-40:]),
            )
        else:
            _logger.info("Removed %s.", extra.label)


#: Matches an extras marker in a requirement line, e.g. the `[standard]` in
#: `uvicorn[standard]>=0.52.1,<1.0`. pip's `-c` constraints flag rejects
#: extras outright, "ERROR: Constraints cannot have extras", and that
#: failure is for the *whole constraints file*, not just the offending line,
#: which is why every extras install failed the same way `requirements.txt`
#: itself has two: `uvicorn[standard]`, `fsspec[http]`.
_REQUIREMENT_EXTRAS_RE = re.compile(r"\[[^\]]*\]")


def _requirements_path() -> Path:
    """`requirements.txt`, from a checkout or from the packaged app's bundle.

    `parents[3]` of this file is the repo root from source; in a PyInstaller
    build it is the folder *above* the bundle, where there is no such file,
    so every extra a packaged app installed went in unconstrained, free to
    pull a numpy or a tokenizers the rest of the app was never built against.
    Both specs bundle the file at the root, beside alembic.ini.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "requirements.txt"
    return Path(__file__).resolve().parents[3] / "requirements.txt"


def _constraints_copy(req_path: Path) -> Path | None:
    """A version of `req_path` pip will actually accept as a `-c` file.

    A constraint only needs the version bound, not the extra, so this strips
    `[...]` rather than dropping the affected lines, `uvicorn` and `fsspec`
    still get pinned, just without the part `-c` can't parse. Written to a
    temp file; the caller deletes it once pip has run.
    """
    try:
        text = req_path.read_text(encoding="utf-8")
    except OSError:
        return None
    fd, tmp_path = tempfile.mkstemp(prefix="memorymap-pip-constraints-", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(_REQUIREMENT_EXTRAS_RE.sub("", text))
    return Path(tmp_path)


def _installed_snapshot() -> set[str]:
    """What is installed before pip starts: the packaged build's extras
    folder entries, or the running environment's distribution names."""
    target = frozen_extras_dir()
    if target is not None:
        return {child.name for child in target.iterdir()} if target.is_dir() else set()
    from importlib import metadata

    return {_canonical(str(d.metadata.get("Name") or "")) for d in metadata.distributions()}


def _roll_back(before: set[str]) -> None:
    """Take out what a stopped install put in (the owner: "make sure the
    cancelled install doesnt leave it half installed and taking up space").
    pip installs a requirement's dependencies one at a time, so a Stop after
    torch landed left torch. Only what was not there before goes; anything
    the person already had stays, even if a reinstall touched it."""
    target = frozen_extras_dir()
    if target is not None:
        root = target.resolve()
        for child in list(target.iterdir()) if target.is_dir() else []:
            if child.name in before or root not in child.resolve().parents:
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        _state.log.append("Removed what it had installed so far.")
        return
    new = sorted(_installed_snapshot() - before)
    pip_base = _pip_base_command()
    if not new or pip_base is None:
        return
    try:
        subprocess.run(  # noqa: S603  # names pip itself reported installed, no shell
            [*pip_base, "uninstall", "--yes", "--disable-pip-version-check", *new],
            capture_output=True, timeout=600, check=False, creationflags=NO_WINDOW,
        )
        _state.log.append(f"Removed what it had installed so far: {', '.join(new)}.")
    except (OSError, subprocess.SubprocessError):
        _logger.warning("Couldn't remove a stopped install's packages", exc_info=True)


def _run_install(extra: Extra, reinstall: bool = False) -> None:
    """pip, in a worker thread, with its output kept for the panel."""
    constraints_copy: Path | None = None
    #: pip's own temporary folder, removed whatever happens: a terminated pip
    #: leaves its unpacked wheels (gigabytes for torch) in the system temp.
    pip_tmp = Path(tempfile.mkdtemp(prefix="memorymap-pip-"))
    before = _installed_snapshot()
    try:
        # `sys.executable -m pip` and never a bare `pip`, see
        # `_pip_base_command`'s own docstring for why that's not quite right
        # either once the app is a frozen build, and what this does instead.
        pip_base = _pip_base_command()
        if pip_base is None:
            _state.outcome = "failed"
            _state.step = NO_PYTHON_FOUND_MESSAGE
            return
        # Constrain every extra install against requirements.txt so an optional
        # package's own dependency resolution can't drag a base package (e.g.
        # tokenizers, numpy) to a version the rest of the app doesn't expect.
        req_path = _requirements_path()
        constraints_copy = _constraints_copy(req_path) if req_path.is_file() else None
        constraint = ["-c", str(constraints_copy)] if constraints_copy else []

        command = [
            *pip_base,
            "install",
            "--disable-pip-version-check",
            # A reinstall is for the case the button exists to serve: it is
            # importable but broken: a half-finished download, a wheel built
            # for the wrong platform, the Windows torch DLL the README warns
            # about. `--upgrade` would look at the version, decide it already
            # has it and do nothing at all, which is the one outcome that
            # helps nobody. `--no-cache-dir` for the same reason: a corrupt
            # cached wheel would otherwise be reinstalled faithfully.
            *(["--force-reinstall"] if reinstall else []),
            # And always: a cache holds every wheel downloaded (torch is about
            # 2 GB), kept after a finished install and after a stopped one.
            "--no-cache-dir",
            *_frozen_target_args(),
            *extra.packages,
            *constraint,
        ]
        _state.step = f"pip install {' '.join(extra.packages)}"
        process = subprocess.Popen(  # noqa: S603  # fixed args from the allowlist, no shell
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=NO_WINDOW,
            env={**os.environ, "TMPDIR": str(pip_tmp), "TEMP": str(pip_tmp), "TMP": str(pip_tmp)},
        )
        _state.process = process
        for line in process.stdout or []:
            line = line.rstrip()
            if not line:
                continue
            _state.log.append(line)
            del _state.log[:-MAX_LOG_LINES]
            _state.step = line[:120]
        code = process.wait()
        _state.outcome = "completed" if code == 0 else "failed"
        if code != 0:
            _state.step = _pip_reason(_state.log, f"pip exited with code {code}")
        elif extra.id == "ocr":
            # The one extra with a system-binary half pip can't touch: 
            # asked for directly ("automate it if possible"). Best-effort:
            # a failed *binary* install never flips this extra's own
            # outcome to "failed", the pip packages are genuinely
            # installed and useful (ocr.py degrades cleanly without the
            # binary), so the honest outcome is still "completed", just
            # with the binary attempt's own result folded into the message.
            _state.step = "Installing the Tesseract program…"
            #: The wrapper was installed by a child process a moment ago; the
            #: import system caches directory listings, so without this the
            #: next `find_spec` can still say it is missing.
            importlib.invalidate_caches()
            installed, binary_message = ocr.attempt_binary_install()
            ocr.clear_language_cache()
            _state.log.append(binary_message)
            #: Said as it is (INBOX 443 (3)): this used to say "installed:
            #: restart Tessellate to use it" even when the program was missing
            #: and a restart would change nothing. The reader imports lazily,
            #: so a ready engine needs no restart.
            _state.step = (
                f"{extra.label} is ready. {binary_message}"
                if installed
                else f"The Python part is installed, but the Tesseract program is not. {binary_message}"
            )
        else:
            _state.step = f"{extra.label} installed: restart Tessellate to use it."
        if code == 0:
            activate_frozen_extras()
    except (OSError, subprocess.SubprocessError):
        # See `_run_uninstall`'s except block: same CodeQL
        # `py/stack-trace-exposure` shape, same fix: full detail to the log,
        # a generic fact to `_state.step`, which is what `/extras` returns.
        _logger.exception("Couldn't run pip to install %s", extra.label)
        _state.outcome = "failed"
        _state.step = "Couldn't run pip: see Settings → Logs for why."
    finally:
        _state.running = False
        _state.process = None
        if _state.cancelled:
            # Terminating pip mid-download makes it exit non-zero, which the
            # branches above have already written up as a failure. It wasn't
            # one, someone pressed Quit, and a task history full of
            # "Installing X failed" for things nobody wanted is how a history
            # stops being read.
            _state.outcome = "cancelled"
            _state.step = "Stopped before it finished."
            _roll_back(before)
        shutil.rmtree(pip_tmp, ignore_errors=True)
        # See the module docstring's numbered note above `_logger`: this call
        # was missing entirely until now, which is the actual reason a failed
        # *install* never reached Settings → Logs, `_run_uninstall` had it,
        # this function did not.
        if _state.outcome == "failed":
            _logger.error(
                "Installing %s failed: %s\n%s",
                extra.label,
                _state.step,
                "\n".join(_state.log[-40:]),
            )
        else:
            _logger.info("Installed %s.", extra.label)
        from tessellate.core import taskhistory
        taskhistory.record(
            "extra",
            f"Installing {extra.label}",
            _state.outcome,
            _state.step,
            duration_ms=(time.time() - _state.started) * 1000 if _state.started else None,
        )
        if constraints_copy is not None:
            constraints_copy.unlink(missing_ok=True)
        # Last, after the history row: a reader that waits for "not running"
        # (the Packages poll, a test) must find the row already written.
        _state.running = False


def _run_download_install(extra: Extra, reinstall: bool = False) -> None:
    """A download extra's install, in a worker thread, with the same
    bookkeeping as pip's: the step line, the log, the outcome, the task
    history. No restart: the files are read when the feature next runs.

    `reinstall` needs nothing extra here: `extra_downloads.install` always
    downloads afresh and replaces the folder whole."""
    try:
        extra_downloads.install(extra, _state)
        _state.outcome = "completed"
        _state.step = f"{extra.label} installed. It works now, offline."
    except extra_downloads.DownloadFailed as exc:
        _state.outcome = "failed"
        _state.step = extra_downloads.reason(exc.code, extra.label)
    except OSError:
        # A socket or disk error: the detail can carry a path, so it goes to
        # the log and the caller gets the fact (the CodeQL shape the pip
        # workers above already follow).
        _logger.exception("Couldn't download %s", extra.label)
        _state.outcome = "failed"
        _state.step = "Couldn't download it: check the connection, or see Settings → Logs for why."
    finally:
        if _state.cancelled:
            _state.outcome = "cancelled"
            _state.step = "Stopped before it finished."
        if _state.outcome == "failed":
            _logger.error("Installing %s failed: %s", extra.label, _state.step)
        else:
            _logger.info("Installed %s: %s", extra.label, _state.outcome)
        from tessellate.core import taskhistory

        taskhistory.record(
            "extra",
            f"Installing {extra.label}",
            _state.outcome,
            _state.step,
            duration_ms=(time.time() - _state.started) * 1000 if _state.started else None,
        )
        # Last, after the history row (see the pip worker above).
        _state.running = False


def _run_download_uninstall(extra: Extra) -> None:
    """Remove a download extra's folder."""
    try:
        extra_downloads.uninstall(extra)
        _state.outcome = "completed"
        _state.step = f"{extra.label} removed."
    except OSError:
        _logger.exception("Couldn't remove %s", extra.label)
        _state.outcome = "failed"
        _state.step = "Couldn't remove it: see Settings → Logs for why."
    finally:
        _state.running = False


def _claim(extra: Extra, step: str) -> None:
    """Mark `extra` as the one in hand. The caller holds `_lock`."""
    _state.running = True
    _state.extra_id = extra.id
    _state.outcome = ""
    _state.step = step
    _state.log = []
    _state.started = time.time()
    _state.cancelled = False
    _state.auto = False


def _busy() -> bool:
    """Something holds the installer: one package, or a bulk action between
    two of its packages (when `_state` is momentarily idle)."""
    return _state.running or _bulk.running


def _dispatch(func, *args: object, name: str = "") -> None:  # noqa: ANN001
    """Run an install, a removal or a bulk action on the job pool's one-wide
    `install` lane (`core/jobs.py`), never on a thread of its own: the pool
    is where background work is counted, and one wide is the one-pip-at-a-
    time rule made structural. Tests replace this to run the work inline.

    A pool that is shutting down drops the job (`enqueue` returns 0), and the
    claim taken for it would then hold the installer shut for the rest of the
    process; so it is let go here, with the reason where the screen reads it.
    """
    if jobs.enqueue("extras", func, *args, name=name):
        return
    _state.running = False
    _state.outcome = "failed"
    _state.step = "Tessellate is shutting down, so nothing was started."
    if _bulk.running:
        _bulk.running = False
        _bulk.outcome = "failed"
        _bulk.message = _state.step


def _run_single(worker, extra: Extra, *args: object) -> None:  # noqa: ANN001
    try:
        worker(extra, *args)
    finally:
        _forget_footprints()


def start(extra_id: str, reinstall: bool = False, auto: bool = False) -> tuple[bool, str]:
    """Begin an install. Returns (started, message).

    Never raises on a bad id, the id comes from a request, and an unknown one
    is a thing to report rather than a stack trace.

    `reinstall` is the escape hatch for the state this cannot detect: the module
    imports, so the app reports it installed, and it does not actually work.
    Detection is `find_spec`, which answers "is it there", not "is it sound".
    """
    extra = EXTRAS_BY_ID.get(extra_id)
    if extra is None:
        return False, "No such extra."
    refused = _install_refusal(extra, reinstall)
    if refused:
        return False, refused
    with _lock:
        if _busy():
            return False, "Another install is already running."
        if is_installed(extra) and not reinstall:
            return False, f"{extra.label} is already installed."
        _claim(extra, "starting pip…" if extra.kind == "pip" else "Starting the download…")
        _state.auto = auto
    worker = _run_download_install if extra.kind == "download" else _run_install
    _dispatch(_run_single, worker, extra, reinstall, name=extra.label)
    return True, f"{'Reinstalling' if reinstall else 'Installing'} {extra.label}."


def _install_refusal(extra: Extra, reinstall: bool) -> str:
    """Why `extra` may not be installed now, or "". Checked before the lock
    and before `reinstall` is considered: an extra nothing calls is not made
    installable by asking twice."""
    if extra.unavailable:
        return f"{extra.label} isn't ready to install yet. {extra.unavailable}"
    if unavailable_reason(extra):
        return f"{extra.label} can't be installed here. {unavailable_reason(extra)}"
    if reinstall:
        return _loaded_in_process_reason(extra)
    return ""


def remove(extra_id: str) -> tuple[bool, str]:
    """Uninstall one extra. Same allowlist, same one-at-a-time rule.

    Deliberately does *not* refuse when the module is missing: an extra can be
    half-installed, pip's metadata present and the module unimportable, and
    the button that would fix that is this one.
    """
    extra = EXTRAS_BY_ID.get(extra_id)
    if extra is None:
        return False, "No such extra."
    blocked = removal_locked(extra) or _loaded_in_process_reason(extra)
    if blocked:
        return False, blocked
    with _lock:
        if _busy():
            return False, "Another install is already running."
        _claim(extra, "starting pip…" if extra.kind == "pip" else "Removing…")
    worker = _run_download_uninstall if extra.kind == "download" else _run_uninstall
    _dispatch(_run_single, worker, extra, name=extra.label)
    return True, f"Removing {extra.label}."


def start_bulk(action: str, ids: list[str] | None = None, bundle: str = "") -> tuple[bool, str]:
    """Install, remove or reinstall several extras, one after another, as one
    job on the pool. Returns (started, message).

    INBOX 595. The ids come from a request, so each one must be an entry of
    the allowlist and the whole request is refused otherwise: a bulk body is
    no more a place for a package name than a single install's path is. A
    bundle is resolved here, from `BUNDLES`, never from the client's list.

    Each package keeps its own guards, checked when its turn comes rather
    than up front (the state can change while the ones before it run): one
    that is not ready, already there, or held open by this process is
    skipped or failed with its own sentence, and the rest go on. One failing
    never stops the others.
    """
    if action not in BULK_ACTIONS:
        return False, "Choose install, remove or reinstall."
    if bundle:
        chosen = BUNDLES_BY_ID.get(bundle)
        if chosen is None:
            return False, "No such bundle."
        wanted = list(chosen.extras)
    else:
        wanted = list(ids or [])
    if not wanted:
        return False, "Choose at least one package."
    if any(extra_id not in EXTRAS_BY_ID for extra_id in wanted):
        return False, "No such extra."
    ordered = list(dict.fromkeys(wanted))
    with _lock:
        if _busy():
            return False, "Another install is already running."
        _bulk.running = True
        _bulk.action = action
        _bulk.bundle = bundle
        _bulk.items = [
            {"id": extra_id, "label": EXTRAS_BY_ID[extra_id].label, "outcome": "queued", "message": ""}
            for extra_id in ordered
        ]
        _bulk.started = time.time()
        _bulk.cancelled = False
        _bulk.outcome = ""
        _bulk.message = ""
    label = bulk_label(action, len(ordered))
    _dispatch(_run_bulk, name=label)
    return True, f"{label}."


def bulk_label(action: str, count: int) -> str:
    """"Installing 3 packages", for `/tasks`, the toast and the history."""
    doing = _BULK_VERBS.get(action, _BULK_VERBS["install"])[0]
    return f"{doing} {count} package{'' if count == 1 else 's'}"


def _run_bulk() -> None:
    """The bulk job: each package in the order asked, each reporting its own
    outcome, until the list ends or someone presses Quit."""
    try:
        for item in _bulk.items:
            if _bulk.cancelled:
                item["outcome"] = "cancelled"
                item["message"] = "Stopped before it started."
                continue
            item["outcome"] = "running"
            try:
                _run_bulk_item(item)
            except Exception:  # noqa: BLE001  # one package's surprise is never the batch's
                # Nothing from the request in the line (CodeQL, log injection):
                # the verb is looked up in a table of fixed words, and the
                # item's own outcome below names the package to the person.
                verb = {"install": "install", "uninstall": "uninstall", "reinstall": "reinstall"}.get(
                    _bulk.action, "change"
                )
                _logger.exception("Couldn't %s one package in a bulk batch", verb)
                item["outcome"] = "failed"
                item["message"] = "Couldn't finish it: see Settings → Logs for why."
            finally:
                _state.running = False
                _state.process = None
                _forget_footprints()
    finally:
        _finish_bulk()


def _uninstall_skip(extra, installed: bool) -> str:  # noqa: ANN001
    """Why a bulk uninstall passes this package by, or "" when it goes ahead."""
    if not installed:
        return "Not installed, so there was nothing to remove."
    return removal_locked(extra) or ""


def _run_bulk_item(item: dict) -> None:
    """One package of a bulk action, with the guards its own button has."""
    extra = EXTRAS_BY_ID[item["id"]]
    action = _bulk.action
    installed = is_installed(extra)
    reinstall = action == "reinstall" and installed
    if action == "uninstall":
        skipped = _uninstall_skip(extra, installed)
        if skipped:
            item["outcome"], item["message"] = "skipped", skipped
            return
        refused = _loaded_in_process_reason(extra)
    else:
        if action == "install" and installed:
            item["outcome"] = "skipped"
            item["message"] = "Already installed."
            return
        refused = _install_refusal(extra, reinstall)
        if refused and (extra.unavailable or unavailable_reason(extra)):
            #: Not a failure: the row says this before anyone presses
            #: anything, and a bundle that names it is still worth the rest.
            item["outcome"] = "skipped"
            item["message"] = refused
            return
    if refused:
        item["outcome"] = "failed"
        item["message"] = refused
        return
    removing = action == "uninstall"
    with _lock:
        if extra.kind == "pip":
            _claim(extra, "starting pip…")
        else:
            _claim(extra, "Removing…" if removing else "Starting the download…")
    if removing:
        (_run_download_uninstall if extra.kind == "download" else _run_uninstall)(extra)
    elif extra.kind == "download":
        _run_download_install(extra, reinstall)
    else:
        _run_install(extra, reinstall)
    item["outcome"] = _state.outcome or "failed"
    item["message"] = _state.step
    if _state.outcome == "cancelled":
        _bulk.cancelled = True


def _finish_bulk() -> None:
    """The bulk's own ending: its outcome, one sentence for the history card
    naming what did not work, and the running flag down last."""
    items = _bulk.items
    total = len(items)
    done = [item for item in items if item["outcome"] == "completed"]
    failed = [item for item in items if item["outcome"] == "failed"]
    finished = _BULK_VERBS.get(_bulk.action, _BULK_VERBS["install"])[1]
    if _bulk.cancelled:
        _bulk.outcome = "cancelled"
    elif failed:
        _bulk.outcome = "failed"
    else:
        _bulk.outcome = "completed"
    parts = [f"{finished} {len(done)} of {total}."]
    if failed:
        parts.append("Not done: " + ", ".join(item["label"] for item in failed) + ".")
    if _bulk.cancelled:
        parts.append("Stopped before the rest.")
    if _bulk.action != "uninstall" and any(EXTRAS_BY_ID[item["id"]].kind == "pip" for item in done):
        parts.append("Restart Tessellate to use what was installed.")
    _bulk.message = " ".join(parts)
    from tessellate.core import taskhistory

    taskhistory.record(
        "extra",
        bulk_label(_bulk.action, total),
        _bulk.outcome,
        _bulk.message,
        duration_ms=(time.time() - _bulk.started) * 1000 if _bulk.started else None,
    )
    if failed:
        _logger.warning("%s: %s", bulk_label(_bulk.action, total), _bulk.message)
    _bulk.running = False


def _loaded_in_process_reason(extra: Extra) -> str:
    """Reported: faster-whisper install/reinstall/remove all silently failed
    on Windows after the dictation buttons had already been used once.

    A used model stays loaded in this process's memory for as long as it
    runs (`voice._loaded`), the whole point, since reloading one per request
    would be far too slow. Windows locks a native `.pyd`/DLL exclusively
    while any process has it mapped in, so pip can spawn, run, and still fail
    to actually replace those files; the failure then surfaces as a cryptic
    pip error in the install log rather than as this sentence. POSIX allows
    replacing a file that is still open elsewhere, which is why this was
    never seen from this sandbox.

    Only "voice" holds a native model like this today, the other extras
    either aren't native libraries or aren't cached across requests.
    """
    if extra.id == "needle":
        # The same Windows lock, on the needle engine: once a turn has used
        # it, `libneedle3.dll` is mapped for the life of the process. Asked
        # through `sys.modules` so a status question never imports it.
        module = sys.modules.get("tessellate.ai.needle_provider")
        if module is not None and module.loaded():
            return (
                "Restart Tessellate first. The needle engine is loaded from an "
                "earlier turn, and Windows can't replace or delete it while it "
                "is in use: a restart releases it."
            )
        return ""
    if extra.id != "voice":
        return ""
    from tessellate.ai import voice

    if voice._loaded is not None:  # noqa: SLF001  # this module's whole job is knowing this
        return (
            "Restart Tessellate first. The voice model is loaded in memory from "
            "an earlier recording, and Windows can't replace those files while "
            "they're in use: a restart releases them."
        )
    return ""


def reset_for_tests() -> None:
    """Process-global state, like the job registry, tests have to clear it or
    one test's install leaks into the next one's assertions."""
    global _state, _bulk
    _state = InstallState()
    _bulk = BulkState()
    _footprints.clear()


def install_blocking(extra_ids: list[str]) -> int:
    """Install each extra in turn and wait: the packaged installer's
    optional-packages page runs `Tessellate.exe --install-extras ...`
    (installer.iss), so the wizard and Settings -> Packages are one code
    path rather than a PowerShell copy that installed somewhere the app
    could not import from. Returns the number that failed."""
    failed = 0
    for extra_id in extra_ids:
        # Already there is done, not failed: an upgrade runs the wizard again
        # with the same boxes ticked, and `start` refuses an installed extra.
        extra = EXTRAS_BY_ID.get(extra_id)
        if extra is not None and not extra.unavailable and is_installed(extra):
            _logger.info("extra %s is already installed", extra_id)
            continue
        started, message = start(extra_id)
        if not started:
            _logger.warning("extra %s not installed: %s", extra_id, message)
            failed += 1
            continue
        while current().running:
            time.sleep(0.5)
        if current().outcome != "completed":
            _logger.warning("extra %s failed: %s", extra_id, current().step)
            failed += 1
    return failed


def download_ready(extra_id: str) -> Path | None:
    """The installed folder of a download extra, or None. What the features
    that use one ask (the run sandbox, the needle provider), so none of them
    imports anything to find out. Here rather than in `extra_downloads` so
    that module never imports this one (CodeQL 429 to 431: an import cycle)."""
    extra = EXTRAS_BY_ID.get(extra_id)
    if extra is None or extra.kind != "download" or not extra_downloads.is_installed(extra):
        return None
    return extra_downloads.folder(extra)
