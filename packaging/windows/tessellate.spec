# PyInstaller spec for the Windows desktop build.
#
# Built on windows-latest in CI (.github/workflows/release.yml), never on
# this developer's own machine — PyInstaller bundles for the OS it runs on,
# it does not cross-compile, so a spec written and reasoned about here is
# unverified until that workflow actually runs it. Read this file's own
# comments as "why", not "confirmed working."
#
# Usage (from the repo root, on Windows):
#   pip install -e ".[desktop]" pyinstaller
#   pyinstaller packaging/windows/tessellate.spec --distpath dist --workpath build
#
# Produces dist/Tessellate/Tessellate.exe (onedir, not onefile — see
# below for why) plus everything it needs beside it. installer.iss in this
# same folder packages that whole folder into the actual installer.

import sys
from pathlib import Path

block_cipher = None

# packaging/windows/tessellate.spec -> repo root is two levels up.
REPO_ROOT = Path(SPECPATH).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
MIGRATIONS_DIR = REPO_ROOT / "migrations"
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
ENTRY_SCRIPT = REPO_ROOT / "src" / "tessellate" / "__main__.py"
ICON = str(FRONTEND_DIR / "icon.ico")
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# **The IANA time zone database, which Windows does not have.** zoneinfo
# reads the system's zone files on Linux and macOS and the `tzdata` package
# on Windows, and nothing in the build installed that package: the packaged
# app refused the timezone the window reports on every start (the
# `/preferences` validator raised ZoneInfoNotFoundError for every zone name,
# "Europe/London" included) and read "today" and "in ten minutes" on the
# machine's zone instead of the person's. Imported here, not just listed,
# so a build environment without it fails at this line rather than shipping
# a build that quietly lacks it; PyInstaller's own zoneinfo hook then bundles
# the data on Windows.
import tzdata  # noqa: E402,F401
from PyInstaller.utils.hooks import collect_data_files  # noqa: E402

TZDATA_FILES = collect_data_files("tzdata")

# **Every module of the app, by file, not by whatever the analysis can see.**
# PyInstaller follows `import x` statements; it does not follow
# `importlib.import_module("x")`, and this app reaches several of its own
# modules only that way (to keep `core/` free of import cycles, ARCH-10).
# Measured on a build of this spec: 198 of 200 modules bundled, and one of the
# two missing was `tessellate.ai.needle_provider`, which `ai/tool_fallback.py`
# imports by name, so the needle extra (tool calling without Ollama) raised
# ModuleNotFoundError on every packaged install. The searxng facades below
# were the same bug found earlier by a support bundle. Listing the package's
# files makes the next such module impossible to miss;
# tests/test_frozen_packaging.py checks the list against what is imported by
# name. `tessellate.__main__` is left out on purpose: it is the entry script,
# and a second copy under its package name is what `routes_settings.
# _desktop_entry` takes care never to import.
SRC_DIR = REPO_ROOT / "src"


def _app_modules():
    found = []
    for path in sorted((SRC_DIR / "tessellate").rglob("*.py")):
        parts = list(path.relative_to(SRC_DIR).with_suffix("").parts)
        if parts[-1] == "__main__":
            continue
        if parts[-1] == "__init__":
            parts.pop()
        found.append(".".join(parts))
    return found


APP_MODULES = _app_modules()

# **The whole standard library, for the optional packages.** A packaged build
# carries only the standard-library modules the app itself imports, and the
# extras (Settings > Packages, the installer's optional page) are installed
# later, into the data folder, and run on the bundle's own interpreter. Any
# standard module they import that the app never did is simply not there.
# Measured on a build of this spec against what the extras import:
# `transformers` imports `filecmp` at the top of a module its auto classes
# load, so search by meaning (the recommended, ticked-by-default extra) could
# not import; `pypdfium2` and `scipy` need `ctypes.util`, `lxml` and `numpy`
# `optparse`, `huggingface_hub` `venv`. A list of those five would be the next
# missing one waiting to happen, so every module of the standard library is
# named, apart from the GUI toolkit, the test suite, the bundled pip wheels
# and the IDE, which no extra uses and which would add megabytes (Tk alone
# brings its own DLLs). Measured cost: 3 MB (183.3 to 186.2 MB, Linux build).
_STDLIB_SKIP = {
    "tkinter", "turtle", "turtledemo", "idlelib", "test", "ensurepip",
    "lib2to3", "pydoc_data", "this", "antigravity", "__phello__", "_pyrepl",
}


def _stdlib_modules():
    import importlib.util

    found = []
    for top in sorted(sys.stdlib_module_names):
        if top in _STDLIB_SKIP or top.startswith("_"):
            continue
        try:
            spec = importlib.util.find_spec(top)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            continue
        found.append(top)
        for location in spec.submodule_search_locations or []:
            base = Path(location)
            for path in sorted(base.rglob("*.py")):
                parts = list(path.relative_to(base).with_suffix("").parts)
                if any(p in ("test", "tests", "idle_test") or p.startswith("test_") for p in parts):
                    continue
                if parts[-1] == "__init__":
                    parts.pop()
                if not parts or any("-" in p for p in parts):
                    continue
                found.append(".".join([top, *parts]))
    return found


STDLIB_MODULES = _stdlib_modules()

def _without_bytecode(datas):
    """The data files minus any `__pycache__` folder (only folders: a package's
    own data files are never touched). `(MIGRATIONS_DIR, "migrations")` copies the folder whole, so a
    build machine that had ever imported a migration (a local run, a test)
    shipped `migrations/__pycache__` too: stale bytecode for the build
    machine's Python, in a bundle that must write none (`sys.dont_write_
    bytecode` is set when frozen). CI's clean checkout has none, which is why
    this only showed on a developer's own build. Entries are `(dest, src,
    typecode)`; the destination is what carries the folder name."""
    kept = []
    for entry in datas:
        parts = str(entry[0]).replace("\\", "/").split("/")
        if "__pycache__" in parts:
            continue
        kept.append(entry)
    return kept


a = Analysis(
    [str(ENTRY_SCRIPT)],
    pathex=[str(REPO_ROOT / "src")],
    binaries=[],
    datas=[
        # Bundled at the extraction root as "frontend" — api/app.py's
        # FRONTEND_DIR and __main__.py's icon lookup both expect exactly
        # that path once sys.frozen is true (see their own comments).
        (str(FRONTEND_DIR), "frontend"),
        # The pre-window splash the exe starts itself (__main__._start_frozen_splash).
        (str(REPO_ROOT / "scripts" / "splash.ps1"), "scripts"),
        # Same reason, same extraction-root convention: core/database.py's
        # _migrations_root() looks for these two right beside "frontend"
        # once sys.frozen is true. Without them, a frozen build silently
        # falls back to "Alembic config not found" (logged, never fatal —
        # see _ensure_alembic_baseline's own docstring) and every install
        # stays on the pre-Alembic additive-only path.
        (str(MIGRATIONS_DIR), "migrations"),
        (str(ALEMBIC_INI), "."),
        # The constraints an optional package is installed against
        # (core/extras._requirements_path), so an extra cannot drag a shared
        # library to a version the bundle was not built with.
        (str(REPO_ROOT / "requirements.txt"), "."),
        # The About panel's release notes (api/app.py `/changelog`, which
        # reads it from the bundle root when frozen). Without it the panel
        # was empty on every packaged build.
        (str(CHANGELOG), "."),
        # The taxonomy pack filing reads (ai/taxonomy.py `DATA_DIR`): JSON
        # beside the module, so it goes where the module's package is.
        (str(REPO_ROOT / "src" / "tessellate" / "ai" / "data" / "taxonomy"), "tessellate/ai/data/taxonomy"),
        *TZDATA_FILES,
    ],
    hiddenimports=[
        # uvicorn picks its event loop / protocol implementations at
        # runtime via importlib rather than a top-level import, which is
        # exactly the shape PyInstaller's static analysis cannot see.
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan.on",
        # SQLAlchemy's sqlite dialect, same "picked by name at runtime"
        # shape as the uvicorn entries above.
        "sqlalchemy.dialects.sqlite",
        # zoneinfo finds this package by name at run time (see TZDATA_FILES).
        "tzdata",
        # pywebview's Windows backends. edgechromium is the modern
        # (WebView2) one and what a current Windows ships; mshtml is the
        # legacy IE-engine fallback pywebview itself falls back to. Neither
        # is imported by name anywhere in this app's own code, so without
        # this pywebview finds nothing to render into on a frozen build.
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        # multipart form parsing (note/document file uploads) and password
        # hashing both resolve their real backend at import time in a way
        # PyInstaller's analysis has been seen to miss.
        "multipart",
        "bcrypt",
        # pystray's own backend selection (__main__._start_tray) is the same
        # "picked by name at runtime" shape as pywebview's platforms above —
        # win32 is the only one this build ever runs, but PyInstaller's
        # static analysis has no way to know that from `import pystray` alone.
        "pystray._win32",
        "PIL.Image",
        # search/searxng_manager.py's own module __getattr__ reaches these
        # four facade files exclusively through importlib.import_module —
        # the same "picked by name at runtime" shape as every entry above,
        # and confirmed missing from a real packaged build by a support
        # bundle: "ModuleNotFoundError: No module named
        # 'tessellate.search.searxng_docker'". None of the four is ever
        # imported by its own name anywhere else in this app, so PyInstaller's
        # static analysis has no path to any of them without this.
        "tessellate.search.searxng_settings",
        "tessellate.search.searxng_docker",
        "tessellate.search.searxng_install",
        "tessellate.search.searxng_process",
        *APP_MODULES,
        *STDLIB_MODULES,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Never bundled: search by meaning is an optional install from
        # Settings > Packages (core/extras.py id="semantic"), and the app
        # falls back to keywords without it. fastembed and ONNX Runtime are
        # about 60 MB; torch and sentence-transformers, the engine before
        # it, stay listed so a stray install on the build machine is never
        # picked up. (Nothing imports them at module level; this makes the
        # intent explicit.)
        "fastembed",
        "onnxruntime",
        "torch",
        "sentence_transformers",
    ],
    cipher=block_cipher,
    noarchive=False,
)

a.datas = _without_bytecode(a.datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# **Off, after the first packaged run** (the owner, 0.3.3 on Windows: "the
# windows splash doesn't work" and a blank window titled "tk" with Tk's
# feather icon for a couple of seconds). PyInstaller's Splash is a Tcl/Tk
# window: when its script fails on the user's machine, Tk's empty root is
# what is left on screen. The app's own loading window (`_loading_html`,
# opened as soon as Python runs) already says what the launch is doing,
# so the bootloader card is dropped rather than patched blind. A
# pre-Python card: the exe now starts scripts/splash.ps1 itself, the card
# start.bat shows (`_start_frozen_splash`). `_splash_status` and `_close_bootloader_splash` stay: both are no-ops
# when `pyi_splash` does not exist.

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Tessellate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    # No code signing yet (deliberate, for now — see README's Windows
    # install note): an unsigned exe still needs an icon so Explorer, the
    # taskbar and the installer shortcut all show the real one rather than
    # a generic default, which is a separate thing from the signature.
    icon=ICON,
)

# onedir, not onefile: a onefile build re-extracts itself to a temp folder
# on every single launch, which is a slow, avoidable cold start for an app
# meant to be opened like any other desktop program. installer.iss installs
# this whole folder, which is also the more normal shape for an "installed"
# app (matches the earlier portable-vs-installed decision) — a onefile
# build is the better fit for the portable case this project chose not to
# ship for v1.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Tessellate",
)
