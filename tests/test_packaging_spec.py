"""The Windows PyInstaller spec's `hiddenimports` list, kept honest against
the source it's meant to cover.

Nothing here can run PyInstaller itself, that only happens in CI, on
windows-latest (packaging/windows/tessellate.spec's own header comment says
so). What this guards against is cheaper and just as real: a module reached
only through `importlib.import_module` (searxng_manager.py's `__getattr__`
facade, the same "picked by name at runtime" shape as the uvicorn/sqlalchemy/
pywebview/pystray entries already in the spec) going missing from a frozen
build because nobody remembered to list it. That exact bug shipped once,
confirmed by a real user's support bundle: "ModuleNotFoundError: No module
named 'tessellate.search.searxng_docker'" on a packaged Windows install.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tessellate.search import searxng_manager

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "packaging" / "windows" / "tessellate.spec"
LINUX_SPEC_PATH = ROOT / "packaging" / "linux" / "tessellate.spec"
ISS_PATH = ROOT / "packaging" / "windows" / "installer.iss"
FRONTEND = ROOT / "frontend"


@pytest.mark.parametrize("spec", [SPEC_PATH, LINUX_SPEC_PATH], ids=["windows", "linux"])
def test_every_searxng_facade_module_is_a_hidden_import(spec):
    spec_text = spec.read_text(encoding="utf-8")
    for module_name in searxng_manager._FACADE_NAMES:
        needle = f"tessellate.search.{module_name}"
        assert needle in spec_text, (
            f"{needle} is reached only via searxng_manager's dynamic "
            "__getattr__ and must be listed in the spec's hiddenimports, "
            "or a frozen build can't import it"
        )


# --- every file the page asks for is in the bundle ---------------------------


def _page_references() -> set[str]:
    """Every local file the running page fetches, as a path under frontend/:
    the tags in index.html, the lazy bundles in app.js's LAZY_MODULES, the
    URLs written as strings in any frontend script (workers, the service
    worker, vendored libraries), the manifest's icons, the module imports
    the grammar worker makes, and the fonts the icon stylesheet names."""
    found: set[str] = set()
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for url in re.findall(r'(?:src|href)="(/[^"#?]+)', html):
        #: `/auth/...` is the server's own route (the lock screen's "Install the
        #: certificate" link answers from `routes_auth.py`), not a file under
        #: frontend/ to bundle.
        if url.startswith("/auth/"):
            continue
        found.add(url.lstrip("/"))
    app = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    lazy = re.search(r"const LAZY_MODULES = \{(.*?)\n\};", app, re.S)
    assert lazy, "LAZY_MODULES moved; this test reads it by name"
    for url in re.findall(r'"(/js/[a-z0-9-]+\.js)"', lazy.group(1)):
        found.add(url.lstrip("/"))
    for script in (FRONTEND / "js").glob("*.js"):
        text = script.read_text(encoding="utf-8")
        for url in re.findall(
            r"[\"'`](/(?:vendor/[^\"'`?$]+|(?:js/)?[a-z0-9-]+\.(?:js|wasm|css|json|webmanifest|png|svg|ico)))[\"'`?]",
            text,
        ):
            found.add(url.lstrip("/"))
        for rel in re.findall(r'^import .* from "\.\./([^"]+)";', text, re.M):
            found.add(rel)
    manifest = (FRONTEND / "manifest.webmanifest").read_text(encoding="utf-8")
    for url in re.findall(r'"src":\s*"(/[^"]+)"', manifest):
        found.add(url.lstrip("/"))
    for css in [*FRONTEND.glob("css/*.css"), *FRONTEND.glob("vendor/*/style.css")]:
        for rel in re.findall(r'url\("?\./([^")]+)"?\)', css.read_text(encoding="utf-8")):
            found.add(str(css.parent.relative_to(FRONTEND) / rel))
    harper = FRONTEND / "vendor" / "harper" / "slimBinary.js"
    for rel in re.findall(r'new URL\("([^"]+)", import\.meta\.url\)', harper.read_text(encoding="utf-8")):
        found.add(f"vendor/harper/{rel}")
    return found


def _tracked_frontend_files() -> set[str]:
    """What CI's checkout has, which is what the bundle is built from: a
    file present here only because it is ignored would pass an existence
    check and still be missing from every release."""
    out = subprocess.run(
        ["git", "ls-files", "frontend"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return {line.removeprefix("frontend/") for line in out.splitlines() if line}


def test_the_reference_walk_finds_the_files_it_exists_for():
    """A walk that silently matched nothing would pass everything below."""
    refs = _page_references()
    for expected in (
        "js/app.js",
        "js/documents-code.js",
        "js/documents-prose.js",
        "js/whiteboard-map.js",
        "js/harper-worker.js",
        "js/graph-worker.js",
        "sw.js",
        "vendor/harper/harper_wasm_slim_bg.wasm",
        "vendor/harper/BinaryModule-BmeyZWwZ.js",
        "vendor/emmet/emmet.min.js",
        "vendor/phosphor/Phosphor.woff2",
        "css/00-tokens-shell.css",
        "icon-512.png",
    ):
        assert expected in refs, expected


def test_every_file_the_page_loads_is_committed_and_bundled():
    """The spec bundles frontend/ whole, so a file is in the build exactly
    when it is in CI's checkout. Checked from both ends: the spec still
    takes the whole folder (a narrowed datas list is how a split file like
    documents-prose.js would go missing), and every file the page asks for
    is committed."""
    for spec in (SPEC_PATH, LINUX_SPEC_PATH):
        assert '(str(FRONTEND_DIR), "frontend")' in spec.read_text(encoding="utf-8"), spec
    tracked = _tracked_frontend_files()
    missing = sorted(ref for ref in _page_references() if ref not in tracked)
    assert not missing, f"referenced by the page but not committed under frontend/: {missing}"


@pytest.mark.parametrize("spec", [SPEC_PATH, LINUX_SPEC_PATH], ids=["windows", "linux"])
def test_the_bundle_carries_its_data_files(spec):
    """Alembic's migrations, and the About panel's release notes, which
    api/app.py reads from the bundle root once frozen."""
    text = spec.read_text(encoding="utf-8")
    assert '(str(MIGRATIONS_DIR), "migrations")' in text
    assert '(str(ALEMBIC_INI), ".")' in text
    assert "CHANGELOG" in text and 'CHANGELOG.md' in text


def test_the_windows_build_carries_the_time_zone_database():
    """Windows has no IANA zone files; zoneinfo reads the `tzdata` package
    there. Imported by the spec so a build without it fails, not ships."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    assert "import tzdata" in text
    assert 'collect_data_files("tzdata")' in text and "*TZDATA_FILES" in text


# --- the build installs what the app imports ---------------------------------

#: In requirements.txt and deliberately not in a packaged build: search by
#: meaning's engine (an optional install Settings, Packages fetches; it was
#: sentence-transformers and torch until 2026-10-27) and the test tools.
NOT_BUNDLED = {"fastembed", "pytest", "httpx", "pytest-xdist"}


def _runtime_requirements() -> set[str]:
    names = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        names.add(re.split(r"[\[<>=!~;\s]", line, maxsplit=1)[0].lower())
    return names - NOT_BUNDLED


def _build_installs(workflow: str) -> list[set[str]]:
    """Each `pip install ...` line block in a workflow, as package names."""
    text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    blocks = []
    for match in re.finditer(r"pip install ((?:[^\n]*\\\n)*[^\n]*)", text):
        words = match.group(1).replace("\\\n", " ").split()
        names = {
            re.split(r"[\[<>=!~;]", w.strip('"'), maxsplit=1)[0].lower()
            for w in words
            if not w.startswith("-")
        }
        if "pyinstaller" in names:
            blocks.append(names)
    return blocks


@pytest.mark.parametrize("workflow, jobs", [("release.yml", 2), ("package-check.yml", 1)])
def test_every_runtime_requirement_is_in_the_build(workflow, jobs):
    """A requirement the build does not install is a module the frozen app
    does not have. `tzdata` was missing from every packaged build (the
    Windows app could not name a single time zone), and `defusedxml` from
    the Linux one."""
    blocks = _build_installs(workflow)
    assert len(blocks) == jobs, blocks
    wanted = _runtime_requirements()
    assert {"tzdata", "defusedxml", "fastapi"} <= wanted
    for names in blocks:
        assert not wanted - names, f"{workflow} does not install {sorted(wanted - names)}"


# --- installer.iss ------------------------------------------------------------


def _code_section() -> str:
    text = ISS_PATH.read_text(encoding="utf-8")
    return text[text.index("[Code]") :]


def test_no_comment_in_the_wizard_code_nests_a_brace():
    """Pascal's `{ }` comments do not nest: the first `}` ends the comment
    and the rest is read as code. A comment naming `{code:GetSelectedExtras}`
    did exactly that, in a section nothing but a release ever compiled."""
    code = re.sub(r"'[^'\n]*'", "''", _code_section())  # string literals hold constants
    depth_one = False
    for index, char in enumerate(code):
        if char == "{":
            assert not depth_one, f"a brace inside a comment at: {code[index - 60 : index + 20]!r}"
            depth_one = True
        elif char == "}":
            depth_one = False


def test_a_silent_install_downloads_nothing_it_was_not_asked_for():
    """The in-app updater runs the installer with /VERYSILENT; the page's
    defaults must not start a 2 GB download inside every update."""
    code = _code_section()
    body = code[code.index("function GetSelectedExtras") :]
    body = body[: body.index("\nend;")]
    assert "if WizardSilent then" in body
    assert "{param:EXTRAS|}" in body


def test_a_silent_update_reopens_the_app_it_closed():
    """The updater's /VERYSILENT install skipped the "Launch now" entry
    (skipifsilent), so the app closed for an update and stayed closed. The
    updater now passes /RELAUNCH=1 and a [Run] entry honours it, silent
    installs only: a scripted /VERYSILENT alone must not open a window."""
    text = ISS_PATH.read_text(encoding="utf-8")
    run = text[text.index("[Run]") : text.index("[UninstallDelete]")]
    entries = [line for line in run.splitlines() if "Check: ShouldRelaunch" in line]
    assert len(entries) == 1, "exactly one relaunch entry"
    assert "skipifsilent" not in entries[0] and "nowait" in entries[0]
    assert "runasoriginaluser" in entries[0]
    body = _code_section()
    body = body[body.index("function ShouldRelaunch") :]
    body = body[: body.index("\nend;")]
    assert "WizardSilent" in body and "{param:RELAUNCH|0}" in body
    updater = (ROOT / "src" / "tessellate" / "api" / "routes_update.py").read_text(encoding="utf-8")
    assert '"/RELAUNCH=1"' in updater


def test_the_installer_only_runs_where_the_exe_can():
    text = ISS_PATH.read_text(encoding="utf-8")
    assert "ArchitecturesAllowed=x64compatible" in text
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in text


def test_the_app_id_never_changes():
    """Inno finds the install to upgrade by AppId. A new one would install a
    second copy beside the first, with two uninstall entries."""
    assert "AppId={{B4C6E3F1-6E6A-4B7E-9C1D-3F6A2E8D9C40}" in ISS_PATH.read_text(encoding="utf-8")


def test_uninstall_never_names_the_notes_folder():
    """Notes live in %APPDATA%\\MemoryMap AI; INSTALL.md promises the
    uninstaller leaves them. Only {app} paths may be deleted."""
    text = ISS_PATH.read_text(encoding="utf-8")
    section = text[text.index("[UninstallDelete]") : text.index("[Code]")]
    for line in section.splitlines():
        if line.startswith("Type:"):
            assert 'Name: "{app}\\' in line, line
    assert "{userappdata}" not in section
    # The old in-folder `data` is emptied by name, never swept whole.
    assert 'filesandordirs; Name: "{app}\\data"' not in section


def test_the_packaged_exe_has_no_tk_splash():
    """The bootloader Splash is a Tcl/Tk window, and on the owner's first
    packaged run it failed and left Tk's empty "tk" root window on screen
    (0.3.3). It is off; the app's own loading window says what the launch is
    doing, and the hooks that drove the old card stay as harmless no-ops."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "Splash(" not in code
    assert "splash.binaries" not in code
    main = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")
    assert "html=_loading_html()" in main
