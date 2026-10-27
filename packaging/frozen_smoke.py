"""Smoke-test a running packaged Tessellate: every asset and the API paths
that only a frozen build can get wrong.

    python packaging/frozen_smoke.py --base http://127.0.0.1:8765 --data-dir DIR
    python packaging/frozen_smoke.py --list          # the derived asset URLs

Run by `.github/workflows/package-check.yml` against the PyInstaller build on
windows-latest, and usable against any server (a source checkout serves the
same answers). Standard library only, so it runs on the runner's Python with
nothing installed.

**The asset list is read from the code, not written here.** The page fetches
most of its scripts and stylesheets after boot (`LAZY_MODULES` in
`frontend/js/app.js`, a worker's URL in another file), and none of those are
in `index.html`, so a smoke that checked the page's own references proved
nothing about them. `asset_urls()` parses `LAZY_MODULES` and every quoted
local asset path in the frontend's scripts, so a file that moves into or out
of a bundle is checked the next run without anyone editing this file.
`tests/test_frozen_packaging.py` checks the same list against the files on
disk.

Every failure is one line naming the URL or endpoint, and the exit code is
the number of failures (capped at 100), so the CI log says what broke.
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

#: A local asset path as a string literal in the frontend's code: a quote, a
#: root-relative path under one of the served folders, a file extension, and
#: the closing quote straight after (so a selector such as
#: `script[src*="/js/app.js?"]` is not read as a URL).
_LITERAL = re.compile(
    r"""["'`](/(?:js|css|vendor|board-library)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)["'`]"""
)
#: `src="/..."` and `href="/..."` in index.html, query string dropped.
_PAGE_REF = re.compile(r"""(?:src|href)="(/[^"?#]+\.(?:js|css|mjs))(?:\?[^"]*)?\"""")

#: Fetched by URL from inside other files (a worker, a font face, the
#: grammar checker's binary), each named here because what names them is
#: not a string this parser reads.
EXTRA_ASSETS = (
    "/vendor/harper/harper_wasm_slim_bg.wasm",
    "/vendor/phosphor/Phosphor.woff2",
    "/manifest.webmanifest",
    "/sw.js",
    "/favicon.svg",
    # The diagram frame's page is a route (security.MERMAID_FRAME_HTML), so its two
    # scripts are named here.
    "/js/mermaid-frame.js",
    "/vendor/mermaid/mermaid.min.js",
)


def lazy_module_urls(app_js: str) -> list[str]:
    """Every file named in `const LAZY_MODULES = { ... };`, in order.

    Raises when the table is missing or empty, so renaming it fails the smoke
    and the test loudly rather than checking nothing."""
    start = app_js.find("const LAZY_MODULES = {")
    if start == -1:
        raise ValueError("frontend/js/app.js has no `const LAZY_MODULES = {` table")
    end = app_js.find("\n};", start)
    if end == -1:
        raise ValueError("LAZY_MODULES in frontend/js/app.js has no closing `};` at column 0")
    block = app_js[start:end]
    urls = [m.group(1) for m in _LITERAL.finditer(block)]
    if not urls:
        raise ValueError("LAZY_MODULES in frontend/js/app.js names no files")
    return list(dict.fromkeys(urls))


def code_literal_urls() -> list[str]:
    """Every quoted local asset path in the frontend's own scripts."""
    found: dict[str, None] = {}
    for path in sorted((FRONTEND / "js").glob("*.js")) + [FRONTEND / "sw.js"]:
        for match in _LITERAL.finditer(path.read_text(encoding="utf-8")):
            found[match.group(1)] = None
    return list(found)


def page_urls(html: str) -> list[str]:
    return list(dict.fromkeys(_PAGE_REF.findall(html)))


def asset_urls() -> list[str]:
    """What the smoke fetches besides the page's own references."""
    app_js = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    urls = lazy_module_urls(app_js) + code_literal_urls() + list(EXTRA_ASSETS)
    # The other pages (the capture window, the web clipper) and theirs.
    for page in sorted(FRONTEND.glob("*.html")):
        if page.name == "index.html":
            continue
        urls.append(f"/{page.name}")
        urls += page_urls(page.read_text(encoding="utf-8"))
    return list(dict.fromkeys(urls))


def static_mime_types() -> dict[str, str]:
    """`STATIC_MIME_TYPES` from `api/app.py`, read without importing it."""
    tree = ast.parse((ROOT / "src" / "tessellate" / "api" / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        target = getattr(node, "target", None) or (getattr(node, "targets", None) or [None])[0]
        if isinstance(target, ast.Name) and target.id == "STATIC_MIME_TYPES":
            return ast.literal_eval(node.value)
    raise ValueError("api/app.py has no STATIC_MIME_TYPES")


def expected_type(url: str, types: dict[str, str]) -> str | None:
    return types.get(Path(urllib.parse.urlparse(url).path).suffix.lower())


def source_version() -> str:
    text = (ROOT / "src" / "tessellate" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"', text, re.MULTILINE)
    if not match:
        raise ValueError("src/tessellate/__init__.py has no __version__")
    return match.group(1)


def alembic_head() -> str:
    """The one revision no other revision names as its parent."""
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in (ROOT / "migrations" / "versions").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision[^=]*=\s*["\']([0-9a-f]+)["\']', text, re.MULTILINE)
        down = re.search(r"^down_revision[^=]*=\s*(.+)$", text, re.MULTILINE)
        if rev:
            revisions.add(rev.group(1))
        if down:
            parents.update(re.findall(r"[0-9a-f]{8,}", down.group(1)))
    heads = sorted(revisions - parents)
    if len(heads) != 1:
        raise ValueError(f"expected one Alembic head, found {heads}")
    return heads[0]


# --- HTTP ---------------------------------------------------------------------

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Reply:
    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body

    @property
    def type(self) -> str:
        return self.headers.get("content-type", "")

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def request(base: str, path: str, *, method: str = "GET", body=None, token: str = "", timeout: float = 60) -> Reply:
    data = None
    headers = {"Accept-Encoding": "identity"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Auth-Token"] = token
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            reply = Reply(response.status, {k.lower(): v for k, v in response.headers.items()}, response.read())
    except urllib.error.HTTPError as exc:
        reply = Reply(exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read())
    except OSError as exc:
        reply = Reply(0, {}, str(exc).encode("utf-8", "replace"))
    return reply


def wait_until_up(base: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        reply = request(base, "/health", timeout=3)
        if reply.status == 200:
            return True
        time.sleep(1)
    return False


# --- checks -------------------------------------------------------------------


def check_assets(base: str, fail) -> int:
    """The page, everything it references, and every lazily loaded file, each
    answered 200 with the type the window insists on (a script served as
    text/plain is refused under nosniff)."""
    types = static_mime_types()
    page = request(base, "/")
    if page.status != 200:
        fail(f"GET / answered HTTP {page.status}")
        return 0
    html = page.body.decode("utf-8", "replace")
    urls = page_urls(html)
    if len(urls) < 10:
        fail(f"GET / references only {len(urls)} scripts and stylesheets")
    urls += [url for url in asset_urls() if url not in urls]
    for url in urls:
        reply = request(base, url)
        want = expected_type(url, types)
        if reply.status != 200:
            fail(f"asset {url}: HTTP {reply.status} (missing from the bundle?)")
        elif want and not reply.type.lower().startswith(want):
            fail(f"asset {url}: served as {reply.type or 'no type'}, expected {want}")
        elif not reply.body:
            fail(f"asset {url}: empty body")
    sandbox = request(base, "/documents/run-sandbox")
    if sandbox.status != 200:
        fail(f"GET /documents/run-sandbox answered HTTP {sandbox.status}")
    return len(urls)


def sign_in(base: str, password: str, fail) -> str:
    status = request(base, "/auth/status")
    setup = status.status == 200 and bool(status.json().get("setup_required"))
    reply = request(base, "/auth/setup" if setup else "/auth/unlock", method="POST", body={"password": password})
    if reply.status != 200:
        # One of the two always applies; try the other before failing.
        reply = request(base, "/auth/unlock" if setup else "/auth/setup", method="POST", body={"password": password})
    if reply.status != 200:
        fail(f"POST /auth/setup and /auth/unlock: HTTP {reply.status} {reply.body[:200]!r}")
        return ""
    return reply.json().get("token", "")


NOTE = "Packaging smoke note about zebras"


def seed(base: str, password: str, fail) -> None:
    """Sign in and write one note: what the upgrade check later expects to
    find, written by the older build."""
    token = sign_in(base, password, fail)
    if not token:
        return
    created = request(base, "/entries", method="POST", token=token, body={"content": NOTE, "tags": ["smoke"]})
    if created.status not in (200, 201):
        fail(f"POST /entries: HTTP {created.status} {created.body[:200]!r}")


def check_api(base: str, data_dir: Path | None, password: str, expect_note: bool, fail) -> None:
    health = request(base, "/health")
    if health.status != 200:
        fail(f"GET /health: HTTP {health.status}")
        return
    served = health.json().get("version")
    want = source_version()
    if served != want:
        fail(f"GET /health: version {served!r}, but src/tessellate/__init__.py says {want!r}")

    token = sign_in(base, password, fail)
    if not token:
        return

    if not expect_note:
        created = request(base, "/entries", method="POST", token=token, body={"content": NOTE, "tags": ["smoke"]})
        if created.status not in (200, 201):
            fail(f"POST /entries: HTTP {created.status} {created.body[:200]!r}")

    found = request(base, "/search?q=zebras", token=token)
    hits = found.json().get("hits", []) if found.status == 200 else []
    if found.status != 200:
        fail(f"GET /search?q=zebras: HTTP {found.status} {found.body[:200]!r}")
    elif not any("zebras" in (hit.get("snippet", "") + hit.get("title", "")) for hit in hits):
        fail(f"GET /search?q=zebras: the smoke note is not among {len(hits)} hits")

    # A question about the notebook's shape is counted from rows, no model.
    stats = request(base, "/chat", method="POST", token=token, body={"question": "what are my most common tags"})
    if stats.status != 200:
        fail(f"POST /chat (a stats question): HTTP {stats.status} {stats.body[:200]!r}")
    else:
        answer = stats.json()
        # The tag is checked only where this run wrote the note: an older
        # build that seeded it may have filed its tags differently.
        counted = answer.get("search_mode") == "stats"
        if not counted or (not expect_note and "smoke" not in (answer.get("ai_response") or "")):
            fail(f"POST /chat (a stats question): not answered by counting: {str(answer)[:300]}")

    export = request(base, "/export/backup", token=token)
    if export.status != 200:
        fail(f"GET /export/backup: HTTP {export.status}")
    else:
        try:
            names = zipfile.ZipFile(io.BytesIO(export.body)).namelist()
        except zipfile.BadZipFile:
            names = []
        if not any(name.endswith(("tessellate.db", "memorymap.db")) for name in names):  # brand: keep
            fail(f"GET /export/backup: not a zip with the database in it ({names[:5]})")

    for body, label in (({}, "plain"), ({"password": "smoke-password-123"}, "sealed")):
        bundle = request(base, "/backups/bundle", method="POST", token=token, body=body)
        if bundle.status != 200 or len(bundle.body) < 200:
            fail(f"POST /backups/bundle ({label}): HTTP {bundle.status}, {len(bundle.body)} bytes")

    snapshot = request(base, "/backups", method="POST", token=token)
    if snapshot.status not in (200, 201):
        fail(f"POST /backups: HTTP {snapshot.status} {snapshot.body[:200]!r}")
    elif data_dir is not None:
        name = snapshot.json().get("name", "")
        if not (data_dir / "backups" / name).is_file():
            fail(f"POST /backups: {name!r} is not in {data_dir / 'backups'}")

    changelog = request(base, "/changelog", token=token)
    if changelog.status != 200 or len(changelog.json().get("markdown", "")) < 1000:
        fail(f"GET /changelog: HTTP {changelog.status}, the release notes are missing")

    extras = request(base, "/extras", token=token)
    if extras.status != 200:
        fail(f"GET /extras: HTTP {extras.status}")

    if data_dir is not None:
        check_alembic(data_dir, fail)


def check_alembic(data_dir: Path, fail) -> None:
    """The start-up stamp (or upgrade) reached the newest revision: what
    `core/database._ensure_alembic_baseline` logs and swallows when the
    bundle's `alembic.ini` or `migrations/` cannot be read."""
    db = data_dir / "tessellate.db"
    if not db.is_file():
        db = data_dir / "memorymap.db"  # brand: keep, a notebook not yet renamed
    if not db.is_file():
        fail(f"alembic: no database at {db}")
        return
    head = alembic_head()
    # A file URI, so a Windows path (a drive letter, backslashes, a space or
    # a non-ASCII letter) is spelled the way SQLite reads it.
    connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    except sqlite3.Error as exc:
        rows = []
        fail(f"alembic: {db} has no alembic_version table ({exc}); the start-up stamp failed")
    finally:
        connection.close()
    if rows and rows[0][0] != head:
        fail(f"alembic: {db} is at {rows[0][0]}, the newest revision is {head}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--password", default="testpassword123")
    parser.add_argument("--wait", type=float, default=60, help="seconds to wait for /health")
    parser.add_argument("--log", type=Path, help="printed when something fails")
    parser.add_argument("--only", choices=("assets", "api"), help="run one half")
    parser.add_argument("--seed", action="store_true", help="sign in and write one note, nothing else")
    parser.add_argument("--expect-note", action="store_true", help="the note is already there (an upgrade)")
    parser.add_argument("--list", action="store_true", help="print the derived asset URLs and exit")
    args = parser.parse_args(argv)

    if args.list:
        types = static_mime_types()
        for url in asset_urls():
            print(f"{url}\t{expected_type(url, types) or '-'}")
        return 0

    base = args.base.rstrip("/")
    failures: list[str] = []

    def fail(message: str) -> None:
        failures.append(message)
        print(f"FAIL {message}", flush=True)

    if not wait_until_up(base, args.wait):
        fail(f"GET {base}/health did not answer within {args.wait:.0f} s")
    else:
        if args.seed:
            seed(base, args.password, fail)
        else:
            if args.only in (None, "assets"):
                count = check_assets(base, fail)
                print(f"checked {count} assets")
            if args.only in (None, "api"):
                check_api(base, args.data_dir, args.password, args.expect_note, fail)
    if failures and args.log and args.log.is_file():
        print(f"--- last lines of {args.log} ---")
        print("\n".join(args.log.read_text(encoding="utf-8", errors="replace").splitlines()[-60:]))
    print(f"{len(failures)} failure(s)")
    return min(len(failures), 100)


if __name__ == "__main__":
    sys.exit(main())
