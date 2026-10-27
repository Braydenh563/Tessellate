# PyInstaller spec for the Linux desktop build.
#
# Built on ubuntu-latest in CI (.github/workflows/release.yml), never on this
# developer's own machine — PyInstaller bundles for the OS it runs on, it does
# not cross-compile, so a spec written and reasoned about here is unverified
# until that workflow actually runs it. Read this file's own comments as
# "why", not "confirmed working" — same standing caveat as the Windows spec
# beside it.
#
# No system tray on this build (see __main__.py's own comment on the
# win32-only gate): pystray's Linux backend needs GTK, which — like macOS's
# AppKit — only tolerates UI calls from the main thread, and this app's tray
# runs its event loop on a background thread while webview.start() blocks
# the main one. That is fine on Windows (the only platform it was built and
# tested against) and is exactly the reason macOS was never targeted either.
# Shipping the same architecture here would be a guess, not a port. The
# window still opens and closes normally — just no tray icon or minimize-to-
# tray, the same fallback already in place when pystray isn't installed.
#
# Usage (from the repo root, on Linux):
#   pip install -e ".[desktop]" pyinstaller
#   pyinstaller packaging/linux/tessellate.spec --distpath dist --workpath build
#
# Produces dist/Tessellate/Tessellate (onedir, not onefile — see the
# Windows spec's own comment for why) plus everything it needs beside it.
# The release workflow zips that whole folder rather than building a
# system-specific installer/package (.deb/.rpm/AppImage) — a plain zip has
# no packaging-format decision to get wrong for a first release, at the
# cost of no desktop-menu integration or auto-update path either.

import sys
from pathlib import Path

block_cipher = None

# packaging/linux/tessellate.spec -> repo root is two levels up.
REPO_ROOT = Path(SPECPATH).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
MIGRATIONS_DIR = REPO_ROOT / "migrations"
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
ENTRY_SCRIPT = REPO_ROOT / "src" / "tessellate" / "__main__.py"
ICON = str(FRONTEND_DIR / "icon-512.png")

# Every module of the app, by file: the same list, for the same reason, as
# packaging/windows/tessellate.spec's APP_MODULES (an `importlib.import_module`
# by name is invisible to the analysis; `ai/needle_provider.py` was missing).
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
        # Same reason, same extraction-root convention:
        # core/database.py's _migrations_root() looks for these two right
        # beside "frontend" once sys.frozen is true. Without them, a frozen
        # build silently falls back to "Alembic config not found" (logged,
        # never fatal — see _ensure_alembic_baseline's own docstring) and
        # every install stays on the pre-Alembic additive-only path.
        (str(MIGRATIONS_DIR), "migrations"),
        (str(ALEMBIC_INI), "."),
        # The constraints an optional package is installed against
        # (core/extras._requirements_path), so an extra cannot drag a shared
        # library to a version the bundle was not built with.
        (str(REPO_ROOT / "requirements.txt"), "."),
        # The About panel's release notes, read from the bundle root when
        # frozen (api/app.py `/changelog`); the Windows spec says more.
        (str(REPO_ROOT / "CHANGELOG.md"), "."),
        # The taxonomy pack filing reads (ai/taxonomy.py `DATA_DIR`): JSON
        # beside the module, so it goes where the module's package is.
        (str(REPO_ROOT / "src" / "tessellate" / "ai" / "data" / "taxonomy"), "tessellate/ai/data/taxonomy"),
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
        # pywebview's Linux backend: GTK (via PyGObject) is the one every
        # mainstream distro's default desktop can satisfy without asking
        # for a second toolkit; pywebview falls back to Qt only if GTK
        # isn't importable, which the CI runner may not have either — a
        # missing hidden import here means "no window opens" rather than a
        # partial failure, so this is the one entry in this file most
        # worth checking first if the Linux job's smoke step fails.
        "webview.platforms.gtk",
        # multipart form parsing (note/document file uploads) and password
        # hashing both resolve their real backend at import time in a way
        # PyInstaller's analysis has been seen to miss.
        "multipart",
        "bcrypt",
        # Reached only through searxng_manager's importlib facade, so the
        # analysis cannot see them; the Windows spec had them after a real
        # support bundle showed the ModuleNotFoundError, this one never did.
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
        # Settings > Packages, as in the Windows spec (see its comment).
        "fastembed",
        "onnxruntime",
        "torch",
        "sentence_transformers",
        # No tray on this build (see the module docstring above) — pystray
        # is not installed for this job at all, so there is nothing to
        # exclude by name here; this entry exists so a future session
        # doesn't add pystray to the Linux install step without reading
        # why it was left out.
    ],
    cipher=block_cipher,
    noarchive=False,
)

a.datas = _without_bytecode(a.datas)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    icon=ICON,
)

# onedir, not onefile — see the Windows spec's own comment: a onefile build
# re-extracts itself to a temp folder on every launch, a slow, avoidable cold
# start for something meant to be opened like a normal desktop program.
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Tessellate",
)
