"""Build the FastAPI app: API routers + the static frontend.

No CORS middleware: the frontend is served from the same origin as the
API, so none is needed (plan §4). Note that an absent CORS policy is not
the same as a closed door, CORS governs whether a script may *read* a
reply, not whether the request is sent or acted on. What actually refuses
a request made by another site's page is the Origin check in
core/security.py, which runs alongside the CSP from the same module.
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import logging
import os
import re
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware

from tessellate import __version__
from tessellate.ai import autonomous, embeddings
from tessellate.search import searxng_manager
from tessellate.api import versioning
from tessellate.api import (
    asset_strip,
    routes_ask_history,
    routes_capabilities,
    routes_auth,
    routes_bookmarks,
    routes_categories,
    routes_chat,
    routes_conversations,
    routes_debug,
    routes_documents,
    run_sandbox,
    routes_backups,
    routes_duplicates,
    routes_tidy,
    routes_drafts,
    routes_learned,
    routes_meetings,
    routes_mentions,
    routes_inbox,
    routes_entities,
    routes_relations,
    routes_properties,
    routes_bench,
    routes_editor,
    routes_import,
    routes_usage,
    routes_night,
    routes_questions,
    routes_read,
    routes_statistics,
    routes_utilities,
    routes_privacy,
    routes_vision,
    routes_resurface,
    routes_entries,
    routes_files,
    routes_graph,
    routes_help,
    routes_insights,
    routes_library,
    routes_maintenance,
    routes_models,
    routes_recordings,
    routes_reminders,
    routes_settings,
    routes_spaces,
    routes_tasks,
    routes_timeline,
    routes_search,
    routes_tags,
    routes_translate,
    routes_update,
    routes_captions,
    routes_voice,
    routes_webclip,
    routes_websearch,
    routes_whiteboard,
    routes_board_library,
    routes_code_snippets,
    routes_code_assist,
    routes_board_history,
    routes_map_suggest,
    routes_map_from_notes,
)
from tessellate.api.routes_auth import require_unlock
from tessellate.api.this_computer import is_another_device
from tessellate.core import (
    backup,
    bgtasks,
    deps,
    diskspace,
    egress,
    events,
    jobruns,
    jobs,
    logbuffer,
    netbind,
    origin,
    passes,
    security,
    startup_status,
)
from tessellate.core.deps import init_app_state
from tessellate.entry import manager

# repo-root/frontend: three levels up from src/tessellate/api/app.py in a
# source checkout. A PyInstaller build has no "three levels up": everything
# bundled lands directly under the extraction root (sys._MEIPASS in onefile
# mode, or the executable's own directory in onedir mode) with the `src/`
# layer gone, so the same parents[3] math would resolve to the extraction
# root's own *parent*: a directory this app has no business reading, let
# alone one that happens to contain a "frontend" folder. Checked first and
# explicitly, not inferred from a path that only looks the same in both
# cases by coincidence.
if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    BUNDLE_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = BUNDLE_ROOT / "frontend"


#: **Every type the page is served with, named here rather than read from the
#: machine.** Starlette asks `mimetypes`, and on Windows `mimetypes` loads the
#: registry *over* Python's own table, so a machine where an editor or an old
#: installer once set `.js` to `text/plain` (a known Windows state, and the
#: reason Django and Flask users meet a blank page there) serves `app.js` as
#: text. With `X-Content-Type-Options: nosniff` on every response
#: (`core/security.py`) the window then refuses every script, and the grammar
#: worker, a module worker, refuses a non-JavaScript type even without it.
#: The packaged Windows app is the build that meets this; the pins cost
#: nothing anywhere else.
STATIC_MIME_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".wasm": "application/wasm",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/vnd.microsoft.icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".txt": "text/plain",
}


def pin_static_mime_types() -> None:
    """Put `STATIC_MIME_TYPES` over whatever the registry said. `add_type`
    initialises the table first when nothing has yet, so the registry read
    happens before these, never after them."""
    import mimetypes

    for suffix, media_type in STATIC_MIME_TYPES.items():
        mimetypes.add_type(media_type, suffix)


# (Embedding warm-up now lives in ai/embeddings.start_warmup, which also
# tracks running/failed state for the status pill.)


#: **Each asset URL is stamped with a hash of that file** (audit 2026-10-05,
#: FE-02). This replaced `_BOOT_TOKEN`, one value per server process spliced
#: onto every stamp: it fixed a real report (the desktop window's own cache
#: running yesterday's scripts for days, "basically all my bugs are still
#: there", CLAUDE.md section 5) by making every launch a *different* URL for
#: every file, which also made every launch a cold load: 0 of 49 assets
#: from cache, 2.1 MB fetched and every script parsed cold, measured after a
#: restart. A hash of the file's bytes answers the same question exactly
#: ("is this the file the browser last cached?"): an edited file gets a new
#: URL on the very next page load, with or without a restart, and an
#: unchanged one keeps its URL, so its HTTP cache and V8's code cache, across
#: launches. `STRIP_VERSION` goes into the hash too, because what is served
#: is the stripped file (`asset_strip.py`), and a changed stripper changes it.
#:
#: Keyed on (mtime, size) so a page load stats each file rather than reading
#: it; the read and hash happen once per file version.
_asset_hashes: dict[str, tuple[int, int, str]] = {}


def asset_hash(path: Path) -> str | None:
    """Ten hex characters of sha256 over a frontend file and the stripper's
    version, or None when there is no such file."""
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    key = str(path)
    cached = _asset_hashes.get(key)
    if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
        return cached[2]
    digest = hashlib.sha256(path.read_bytes())
    digest.update(asset_strip.STRIP_VERSION.encode())
    value = digest.hexdigest()[:10]
    _asset_hashes[key] = (stat.st_mtime_ns, stat.st_size, value)
    return value


#: A local URL carrying the version stamp, in the page's markup.
_STAMPED_URL = re.compile(rb"(/[A-Za-z0-9_./-]+)\?v=" + re.escape(__version__.encode()) + rb"(?![\w.-])")


def _stamp_for(rel: str) -> str:
    digest = asset_hash(FRONTEND_DIR / rel.lstrip("/"))
    return f"{__version__}-{digest}" if digest else __version__


def asset_stamps() -> dict[str, str]:
    """Every script and stylesheet a page can load after boot, mapped to its
    stamp: what `lazyAssetStamp` (frontend/js/app.js) reads for a lazy bundle
    or a worker, so a file loaded on demand is stamped by its own bytes too.

    **Stylesheets as well as scripts.** A lazy bundle's own stylesheet
    (`/css/library-lazy.css` in `LAZY_MODULES`) was not in the map, so it
    took app.js's stamp, and a stamped URL is cached `immutable` for a year:
    an edited library-lazy.css with app.js unchanged was the same URL, and
    the desktop window, whose cache outlives every launch, kept the old
    rules (the trap in CLAUDE.md section 5)."""
    stamps = {
        f"/js/{p.name}": _stamp_for(f"/js/{p.name}")
        for p in sorted((FRONTEND_DIR / "js").glob("*.js"))
    }
    stamps.update(
        (f"/css/{p.name}", _stamp_for(f"/css/{p.name}"))
        for p in sorted((FRONTEND_DIR / "css").glob("*.css"))
    )
    return stamps


#: The pages of their own whose local stamps are rewritten as they are
#: served. `clip.html` and `capture.html` joined (OPEN 1101): a plain
#: `?v=<version>` let an edit inside one version be served stale from the
#: immutable HTTP cache.
STAMPED_PAGES = ("offline.html", "clip.html", "capture.html")


def served_offline_html(name: str = "offline.html") -> bytes:
    """`offline.html` as served: the page the service worker shows when the
    server cannot be reached (frontend/sw.js), with its local stamps given
    each file's hash exactly as `index.html`'s are, so the stylesheets it
    links are the same URLs (and the same cache entries) the app loaded.
    The same for the other `STAMPED_PAGES`."""
    page = FRONTEND_DIR / name
    stripped = asset_strip.strip_for_path(name, page.read_bytes())
    return _STAMPED_URL.sub(
        lambda m: m.group(1) + b"?v=" + _stamp_for(m.group(1).decode()).encode(), stripped
    )


_index_cache: dict[str, object] = {}


def served_index_html() -> bytes:
    """`index.html` as served: comments stripped, every local `?v=<version>`
    given its file's own hash, and the lazy scripts' stamps carried in a
    `<meta name="asset-stamps" content="/js/a.js=<stamp>,...">` (a meta, not
    a JSON `<script>`: the page holds no inline script at all,
    `test_static_freshness.py`). Rebuilt only when the page or a stamp
    moves."""
    page = FRONTEND_DIR / "index.html"
    stat = page.stat()
    stamps = asset_stamps()
    source = (stat.st_mtime_ns, stat.st_size)
    if _index_cache.get("source") != source:
        stripped = asset_strip.strip_for_path("index.html", page.read_bytes())
        _index_cache["source"] = source
        _index_cache["stripped"] = stripped
        _index_cache["urls"] = sorted({m.group(1) for m in _STAMPED_URL.finditer(stripped)})
    # Every stamped URL's stamp is part of the key: an edited stylesheet
    # changes the page as surely as an edited page does.
    referenced = tuple(_stamp_for(url.decode()) for url in _index_cache["urls"])  # type: ignore[union-attr]
    signature = (source, referenced, tuple(stamps.values()))
    if _index_cache.get("signature") == signature:
        return _index_cache["body"]  # type: ignore[return-value]
    body = _index_cache["stripped"]
    body = _STAMPED_URL.sub(
        lambda m: m.group(1) + b"?v=" + _stamp_for(m.group(1).decode()).encode(), body
    )
    data = ",".join(f"{path}={stamp}" for path, stamp in stamps.items()).encode()
    block = b'<meta name="asset-stamps" content="' + data + b'">'
    head_end = body.lower().find(b"</head>")
    body = body[:head_end] + block + body[head_end:] if head_end != -1 else body + block
    _index_cache["signature"] = signature
    _index_cache["body"] = body
    return body


class _UnversionedStatic(StaticFiles):
    """A static folder that is not part of the API, so not under `/api/v1`."""

    async def get_response(self, path: str, scope):
        if versioning.is_versioned(scope):
            raise StarletteHTTPException(status_code=404)
        return await super().get_response(path, scope)


class RevalidatedStatic(StaticFiles):
    """The frontend, served so a cache can never hand back yesterday's build.

    **This is a desktop-app bug hiding in a header.** `StaticFiles` sends
    `last-modified` and an `etag` but no `Cache-Control` at all, and a response
    with neither `Cache-Control` nor `Expires` is one an HTTP cache may reuse
    *without asking*: for a heuristic fraction of its age (RFC 9111 §4.2.2).
    In a browser you press reload and never notice. The desktop shell has no
    reload, is a WebView2/WebKit instance with its own on-disk cache, and
    restarts the *process* without invalidating anything, so after an update
    the app can go on running the previous `app.js` indefinitely.

    That is precisely the shape of "the recycle bin's Empty now button is still
    broken": the fix for it (§35F's in-app confirm dialog) is in the file, and
    the flow was driven end to end in Chromium against this server, the dialog
    opens, the notes go, the server reports an empty bin. A user still seeing
    the old behaviour is running the old script.

    `no-cache` is not `no-store`: the file is still cached, and the conditional
    request still answers 304 from the etag above. All it removes is the
    guessing. Everything here is served from localhost, so the cost of a
    revalidation round-trip is not a real cost.

    **The `?v=<version>` stamp changes this calculus for exactly the URLs
    that carry it** (INBOX 47). `test_asset_cache_busting.py` already
    guarantees every local css/js reference in `index.html` is stamped with
    the current `__version__`, and a stamped URL is a *different* URL on
    every release: nothing is ever served stale from it, unlike the
    unstamped path above where staleness is only *revalidated* away. So a
    stamped request gets `public, max-age=31536000, immutable` (the
    one-year-plus-immutable idiom browsers treat as "never revalidate")
    instead of `no-cache`, saving the round trip `no-cache` still pays.
    Unstamped requests (`/vendor/*`, deliberately unstamped per that same
    test, and any bare path) keep the `no-cache` behaviour above unchanged.

    **`index.html` itself is rewritten as it is served** (`served_index_html`):
    every `?v={__version__}` becomes `?v={__version__}-<hash of that file>`,
    so a file edited between two launches is a new URL the moment the page
    is next loaded (the desktop window's own cache, which the old per-launch
    `_BOOT_TOKEN` was there for, can never run yesterday's file), while an
    unchanged file keeps its URL and its cache across launches (audit
    2026-10-05, FE-02: the token had made every launch a cold load).
    """

    #: `index.html`'s body needs to change whenever any asset does (it is the
    #: source of every other URL's `?v=` stamp), *even when the file on disk
    #: has not*: an edited `app.js` changes the page's stamp for it. Handled
    #: before `super()` is ever called, not after: `StaticFiles.get_response` answers a conditional
    #: `If-None-Match`/`If-Modified-Since` against the file's own constant
    #: etag/mtime with a 304 before this class sees a status code to check,
    #: and a 304 tells the browser to keep exactly the stale cached body
    #: this fix exists to stop it keeping. Skipping `super()` for this one
    #: path means no validator is ever computed or sent, no conditional
    #: request has grounds to fire, and every request gets this boot's real
    #: body. Three spellings of the same request reach here: Starlette's own
    #: `get_path` runs `os.path.normpath` on the route, which turns `/`'s
    #: empty split into `"."` rather than `""` (confirmed live: the first
    #: version of this checked `""` and never fired), and a request for the
    #: file by its literal name arrives as `"index.html"` unchanged.
    _INDEX_PATHS = ("", ".", "index.html")

    async def get_response(self, path: str, scope):
        #: `/api/v1` is the API and nothing else (H4, `api/versioning.py`).
        if versioning.is_versioned(scope):
            raise StarletteHTTPException(status_code=404)
        #: `super().get_response` raises this same 405 for anything but
        #: GET/HEAD; the bypass above skips straight past that check along
        #: with the conditional-request one, so it has to raise it itself.
        if path in self._INDEX_PATHS and scope["method"] not in ("GET", "HEAD"):
            raise StarletteHTTPException(status_code=405)
        if path in self._INDEX_PATHS:
            body = await run_in_threadpool(served_index_html)
            #: INBOX 867: a page reached over the network says so, and the
            #: lock card shows "Install the certificate" by CSS alone.
            if not netbind.arrived_on_loopback(scope.get("server")):
                body = body.replace(b"<html ", b'<html data-lan="1" ', 1)
            response = HTMLResponse(content=body)
            response.headers["Cache-Control"] = "no-cache"
            return response
        if path in STAMPED_PAGES and scope["method"] in ("GET", "HEAD"):
            response = HTMLResponse(content=await run_in_threadpool(served_offline_html, path))
            response.headers["Cache-Control"] = "no-cache"
            return response
        strip = self._strippable(path)
        if strip and "range" in Headers(scope=scope):
            # A stripped file is one representation, served whole: a byte
            # range of it would be a range of something no validator names.
            scope = {
                **scope,
                "headers": [(k, v) for k, v in scope.get("headers", []) if k.lower() != b"range"],
            }
        response = await super().get_response(path, scope)
        response = await self._precompressed(response, scope, strip)
        query = scope.get("query_string", b"")
        if isinstance(query, bytes):
            query = query.decode("latin-1")
        stamped = "v" in parse_qs(query)
        if stamped:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    #: **Each file is compressed once, not on every fetch** (INBOX 472).
    #: `GZipMiddleware` compressed a static file afresh on every request:
    #: measured on loopback, `08-consistency.css` (448 KB) took 22 to 46 ms
    #: gzipped against 5 ms sent as it is, `app.js` 10 ms against 4, and a
    #: launch used to fetch every stylesheet and script again (a per-process
    #: stamp gave each one a new URL). So every start paid the whole frontend's
    #: compression on the server's one event loop while the boot's own API
    #: calls queued behind it. The bytes are kept per file, keyed on its
    #: mtime and size, so an edited file is compressed again on its next
    #: fetch and an unchanged one never is. The response carries
    #: `Content-Encoding`, which `GZipMiddleware` reads as "already done" and
    #: passes through. Level 9 rather than the middleware's 6: paid once per
    #: file version instead of per request, it is worth the 0.2 to 0.6% it
    #: takes off the wire (`app.js` 42,997 to 42,922 bytes).
    #:
    #: Kept on disk as well (`<data dir>/cache/static-gz`), because a launch
    #: is a new process: an in-memory copy alone is cold on exactly the start
    #: it was meant for. The whole frontend is 448 ms of compression on the
    #: sandbox, about 150 of it on the boot path, paid once per file version
    #: rather than once per launch. Backups copy the database only, so the
    #: folder is never in one, and anything going wrong with it (a read-only
    #: data dir, a full disk) falls back to compressing in memory.
    #: `application/wasm` (audit 2026-10-05, FE-03): the grammar checker's
    #: 15.9 MB binary is 8 MB gzipped. It was left out because the middleware
    #: compressed it on every fetch (755 ms); here that is paid once per
    #: version and read from `<data dir>/cache/static-gz` after.
    _GZIP_TYPES = (
        "text/",
        "application/javascript",
        "application/json",
        "image/svg+xml",
        "application/wasm",
    )
    _gzip_cache: dict[str, tuple[int, int, bytes]] = {}

    #: **Comments are stripped from what is served** (audit 2026-10-05, FE-01):
    #: the app's own `js/*.js` and `css/*.css` (and `index.html`, above), never
    #: `vendor/`, never the files on disk. See `asset_strip.py` for why and how.
    @staticmethod
    def _strippable(path: str) -> bool:
        path = path.replace("\\", "/")
        return (path.startswith("js/") and path.endswith(".js")) or (
            path.startswith("css/") and path.endswith(".css")
        )

    async def _precompressed(self, response, scope, strip: bool = False):
        if not isinstance(response, FileResponse) or response.status_code != 200:
            return response
        if scope["method"] not in ("GET", "HEAD"):
            return response
        request_headers = Headers(scope=scope)
        wants_gzip = "gzip" in request_headers.get("accept-encoding", "")
        if not strip and (scope["method"] != "GET" or not wants_gzip or "range" in request_headers):
            return response
        media_type = (response.media_type or "").lower()
        if not strip and not media_type.startswith(self._GZIP_TYPES):
            return response
        stat = response.stat_result
        if stat is None or (not strip and stat.st_size < 500):
            return response
        key = str(response.path)
        cached = self._gzip_cache.get(key)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            body = cached[2]
        else:
            body = await run_in_threadpool(_static_gzip, key, stat.st_mtime_ns, stat.st_size, strip)
            self._gzip_cache[key] = (stat.st_mtime_ns, stat.st_size, body)
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "content-encoding")
        }
        headers["Vary"] = "Accept-Encoding"
        if wants_gzip:
            headers["Content-Encoding"] = "gzip"
        else:
            body = gzip.decompress(body)
        if scope["method"] == "HEAD":
            headers["Content-Length"] = str(len(body))
            return Response(content=b"", headers=headers, media_type=response.media_type)
        return Response(content=body, headers=headers, media_type=response.media_type)


def _static_gzip(path: str, mtime_ns: int, size: int, strip: bool = False) -> bytes:
    """A static file's gzip bytes, from the disk cache or compressed now.

    One file per path, named for its version, so an edited file's old copy is
    replaced rather than accumulated (RevalidatedStatic._precompressed). A
    stripped file's name carries the stripper's version as well, so a new
    stripper never reads an old one's output."""
    stem = hashlib.sha1(path.encode(), usedforsecurity=False).hexdigest()[:16]
    if strip:
        size = f"{size}-s{asset_strip.STRIP_VERSION}"  # type: ignore[assignment]
    try:
        folder = deps.get_config().data_dir / "cache" / "static-gz"
    except Exception:  # noqa: BLE001  # no data dir yet is no reason to fail a page
        folder = None
    if folder is not None:
        try:
            return (folder / f"{stem}-{mtime_ns}-{size}.gz").read_bytes()
        except OSError:
            # Not cached yet (or unreadable): it is compressed below instead.
            pass
    raw = Path(path).read_bytes()
    if strip:
        raw = asset_strip.strip_for_path(path, raw)
    # Level 9 for the app's own text (paid once per version); 6 for a large
    # binary such as the grammar checker's 15.9 MB WASM, where 9 takes
    # seconds longer for well under a percent.
    body = gzip.compress(raw, 9 if len(raw) < 4_000_000 else 6, mtime=0)
    if folder is not None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for stale in folder.glob(f"{stem}-*.gz"):
                stale.unlink(missing_ok=True)
            partial = folder / f"{stem}.{os.getpid()}.part"
            partial.write_bytes(body)
            os.replace(partial, folder / f"{stem}-{mtime_ns}-{size}.gz")
        except OSError:
            # A read-only or full data dir only costs the next launch a compression.
            pass
    return body


def clear_static_cache() -> int:
    """Drop the compressed static files, in memory and on disk (INBOX 487).

    Only `<data dir>/cache/static-gz`'s own `.gz` and `.part` files: the
    notebook is not in there, and the next fetch compresses again. Returns how
    many files went."""
    RevalidatedStatic._gzip_cache.clear()
    removed = 0
    try:
        folder = deps.get_config().data_dir / "cache" / "static-gz"
        for path in [*folder.glob("*.gz"), *folder.glob("*.part")]:
            path.unlink(missing_ok=True)
            removed += 1
    except OSError:
        # A folder that cannot be listed or a file in use is a cache that
        # stays; the memory copy is already gone.
        pass
    return removed


def _purge_expired_bin_entries() -> None:
    """Recycle-bin auto-clear: permanently drop entries
    binned longer than the user's configured number of days."""
    try:
        session = deps.get_db().session()
        try:
            config = deps.get_config()
            days = int(config.get_preference("recycle_bin_days", 30))
            with events.acting_as("system:recycle-bin"):
                manager.purge_expired_deleted(session, days, uploads_dir=config.uploads_dir)
                # The bin's documents and reminders, on the same rule.
                from tessellate.entry import bin as other_bin

                other_bin.purge_expired(session, days)
        finally:
            session.close()
    except Exception:  # noqa: BLE001  # a failed purge must never block startup
        # Swallowing the failure is right; swallowing the reason is not. A bin
        # that has quietly stopped clearing is invisible until the disk fills.
        logging.getLogger("tessellate.startup").warning(
            "the recycle-bin auto-clear didn't run this start", exc_info=True
        )


def _compact_event_log() -> None:
    """Keep `audit_log` from growing by a copy of every note on every edit.

    Beside the recycle-bin clear above and for the same reason: it is work
    that has to happen on a schedule in an app with no scheduler, so it
    happens once per launch, cheaply, and never stops the app from starting.

    Compaction, not deletion: `events.compact`'s own docstring says why
    (an entity's events have to keep replaying to its current state), and
    what it gives up (a version older than the window is no longer readable).
    The window is a preference so a notebook that wants a longer memory can
    have one without a code change.
    """
    try:
        session = deps.get_db().session()
        try:
            config = deps.get_config()
            days = int(
                config.get_preference("event_log_days", events.COMPACT_AFTER_DAYS)
            )
            summary = events.compact(session, older_than_days=days)
            if summary["events"]:
                # Worth a line: this is the one background job that makes a
                # note's older history stop being readable, so a person
                # looking for why should find it said plainly.
                logging.getLogger("tessellate.startup").info(
                    "event log compacted: %s events across %s items now keep "
                    "their record but not their text",
                    summary["events"],
                    summary["entities"],
                )
        finally:
            session.close()
    except Exception:  # noqa: BLE001  # a failed compaction must never block startup
        logging.getLogger("tessellate.startup").warning(
            "the event log compaction didn't run this start", exc_info=True
        )


#: Housekeeping's two steps, by name, for `core/passes.py` (Run now in
#: Background tasks). Looked up on this module at call time, so a test that
#: stands in for one is honoured here as in `_startup_maintenance`.
def _purge_step() -> None:
    _purge_expired_bin_entries()


def _compact_step() -> None:
    _compact_event_log()


passes.register_housekeeping("purge-bin", _purge_step)
passes.register_housekeeping("compact-history", _compact_step)


def _install_pending_extras() -> None:
    """The optional packages ticked in Setup (installer.iss writes their ids
    to pending-extras.txt), installed now as one background job with its
    progress and Stop, instead of freezing Setup's window for minutes."""
    from pathlib import Path

    from tessellate.core import extras

    pending = Path(deps.get_config().data_dir) / "pending-extras.txt"
    if not pending.is_file():
        return
    ids = [part.strip() for part in pending.read_text(encoding="utf-8").split(",") if part.strip()]
    #: A retired id (python-docx, `docx`, went in Brief 42) from a Setup older
    #: than this app would otherwise fail the whole list with "No such extra".
    ids = [extra_id for extra_id in ids if extra_id in extras.EXTRAS_BY_ID]
    if not ids:
        pending.unlink(missing_ok=True)
        return
    started, message = extras.start_bulk("install", ids)
    logging.getLogger("tessellate.startup").info("packages picked in Setup %s: %s", ids, message)
    #: Only once the job is running: another install in hand at launch refuses
    #: the list, and a list deleted before it was accepted was a pick lost
    #: (Brief 101c). The next launch asks again; a package already there is
    #: skipped, and a Stop on the job is the person's answer for this run.
    if started:
        pending.unlink(missing_ok=True)


def _choose_chat_model_if_missing() -> None:
    """The stored chat model is not installed (a fresh install's llama3.2):
    use the best one that is, and log it. Ollama not running: nothing to do."""
    from tessellate.ai import model_manager as mm

    config, ollama = deps.get_config(), deps.get_ollama()
    if ollama is None or not ollama.is_running():
        return
    mm.choose_chat_model_if_missing(config, ollama.list_models())


def _startup_maintenance() -> None:
    """The once-per-launch housekeeping, off the path to the first byte
    (ARCH-19). Looked up on the module at call time, so a test can stand in
    for each. Each step already logs and swallows its own failure."""
    module = sys.modules[__name__]
    #: Recorded as "Housekeeping" (INBOX 713), so Background jobs can say
    #: when it last ran beside its Run now (`core/passes.py`).
    with jobruns.started_by("start-up"), jobruns.job_run("maintenance") as run:
        steps = (
            ("_check_notebook_file", "Check the notebook file"),
            ("_purge_expired_bin_entries", "Clear expired notes from the bin"),
            ("_compact_event_log", "Tidy the edit history"),
            ("_backup_if_due", "Back up if today's is due"),
            ("_choose_chat_model_if_missing", "Choose a chat model you have"),
            ("_install_pending_extras", "Install the packages picked in Setup"),
            ("_read_note_dates", "Queue reading the dates written in your notes"),
        )
        run.plan([words for _, words in steps])
        for index, (step, words) in enumerate(steps):
            run.say(f"{words}.")
            try:
                getattr(module, step)()
            except Exception:  # noqa: BLE001  # one step must not stop the next
                logging.getLogger("tessellate.startup").warning("startup maintenance step %s failed", step, exc_info=True)
                run.say(f"That step did not finish: {words.lower()}. The server log has the detail.")
            run.step(index + 1)
        run.result = "at start"


def _read_note_dates() -> None:
    """Notes saved before written-out dates were read get them read once, as
    a background job that resumes where it stopped (`entry/redate.py`)."""
    from tessellate.entry import redate

    redate.enqueue_if_pending()


def _check_notebook_file() -> None:
    """SQLite's quick check on the notebook, first, before anything writes
    (WORLD_CLASS 25e). The page shows the notice from `/backups/integrity`;
    a damaged file is never copied over a good backup, because the daily
    backup checks its own copy (`backup.verify_copy`) and refuses it."""
    backup.check_at_boot(deps.get_config().db_path)


def _backup_if_due() -> None:
    """Scheduled local backups: one consistent snapshot per day,
    taken at startup. Failure must never stop the app."""
    try:
        config = deps.get_config()
        keep = int(config.get_preference("backup_retention_count", backup.KEEP_BACKUPS))
        if backup.backup_is_due(config.db_path, config.data_dir):
            with jobruns.job_run("backup") as run:
                path = backup.backup_now(config.db_path, config.data_dir, keep, run, origin="daily")
                run.result = f"saved {path.name} (the daily backup at start)"
        #: Every start holds the folder to the retention number, not only a
        #: day with a backup due: the safety copy before a migration
        #: (`database.py`) is taken with no notebook preference to read, and
        #: it left four backups under a limit of three (the owner, 2026-10-11).
        backup.prune(config.data_dir, keep)
    except Exception:  # noqa: BLE001  # a failed backup must never block startup
        # This one matters more than it looks: the user believes they have
        # daily local backups, and without this line a backup that has been
        # failing for months looks exactly like one that has been working.
        logging.getLogger("tessellate.startup").warning(
            "today's local backup didn't run: check Settings → Logs",
            exc_info=True,
        )


def _start_searxng_if_asked() -> None:
    """Bring the user's own search engine up with the app, when they asked.

    Reported: *"maybe a setting for allowing the searxng or web search to be on
    or automatically started which is togglable? it keeps disabling itself."*
    Web search was not disabling itself, the *engine* was gone. SearXNG runs
    as a container this app starts on demand, and nothing restarted it after a
    reboot or a `docker` restart, so every search after that fell back to
    DuckDuckGo, which rate-limits and answers with an error. From the outside
    those are indistinguishable from the setting having switched itself off.

    Off by default, because starting a container is not something a local-first
    app should do to a machine without being asked. In a thread, because the
    start can take tens of seconds pulling an image and a slow engine must not
    be a slow app, and inside a try, for the reason the two functions above
    give: a failure here must never stop Tessellate from opening.
    """
    try:
        config = deps.get_config()
        if not config.get_preference("searxng_autostart", False):
            return
        threading.Thread(
            target=lambda: searxng_manager.start(config.data_dir),
            name="searxng-autostart",
            daemon=True,
        ).start()
    except Exception:  # noqa: BLE001  # a failed autostart must never block startup
        logging.getLogger("tessellate.startup").warning(
            "SearXNG autostart didn't run this start", exc_info=True
        )


def _start_autonomous_loop() -> None:
    """Start the background librarian's scheduler (§39).

    This call is the whole feature. Without it `autonomous.py` is imported and
    never run, which is exactly how it shipped: Settings offered an interval,
    an on/off switch and three task toggles, all of them wired to preferences
    that nothing ever read. The switch inside the loop stays the authority on
    whether a pass happens, so starting the scheduler unconditionally here is
    safe: a disabled notebook just sleeps.
    """
    try:
        autonomous.reset_state()  # a new app is a new notebook: not the last one's Quit
        autonomous.start()
    except Exception:  # noqa: BLE001  # same rule as the three above
        logging.getLogger("tessellate.startup").warning(
            "the autonomous scheduler didn't start", exc_info=True
        )


#: PLAN.md §3 B3. Every one of the ~200 `HTTPException(status_code=..., ...)`
#: call sites across the routers picks a status and a human message; none of
#: them picks a machine-readable `code`, and there are too many to touch by
#: hand without risking exactly the kind of drive-by rewrite CLAUDE.md warns
#: against ("Do NOT rewrite the 400+ raise sites"). Deriving `code` from the
#: status here, once, gets every existing raise a stable code for free and
#: means a *new* route never has to remember to set one.
_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "too_large",
    415: "unsupported_media_type",
    422: "invalid",
    423: "locked",
    429: "rate_limited",
    500: "internal",
    502: "bad_gateway",
    503: "unavailable",
}


def _code_for_status(status_code: int) -> str:
    """A stable machine-readable name for an HTTP status this app raises.

    Falls back to `http_<code>` for anything not named above rather than
    raising or returning something empty, a status nobody has catalogued
    yet still gets a code a client can safely branch on, just not one with a
    friendly name.
    """
    return _STATUS_CODES.get(status_code, f"http_{status_code}")


def _register_error_handlers(app: FastAPI) -> None:
    """Make every failure this app returns machine-readable JSON.

    Before this, an `HTTPException` route returned `{"detail": ...}`, fine
    for the message, but the frontend had nothing to branch on except
    parsing that string, and a route that let an exception escape uncaught
    (the space-delete `IntegrityError`, found in the §40 audit) fell through
    to Starlette's default `ServerErrorMiddleware`, which in production mode
    answers with a bare `text/plain` "Internal Server Error", not JSON, no
    correlation id, and (worse) sometimes a raw traceback if debug ever got
    left on. Two handlers close both gaps:

    - Every `HTTPException` (FastAPI's own class subclasses Starlette's, so
      registering on the Starlette base catches both) gets `code` and `hint`
      added alongside its existing `detail`, `detail` is left exactly as
      the route set it, which is what keeps every existing
      `response.json()["detail"] == "..."` assertion passing unchanged.
      A route may already pass a *dict* detail (`{"detail": ..., "hint": ...,
      "code": ...}`) to override any of the three explicitly; nothing in
      this codebase does yet, but nothing has to change here the day one
      does.
    - Anything else, a bug, not a deliberately raised HTTP error, becomes
      `500 {"detail": <a plain sentence>, "code": "internal", "ref": <uuid>}`.
      The traceback goes to the log keyed by that same `ref` (`logger.exception`,
      so it's a full traceback, not just the one-line summary `.warning` would
      give) and never reaches the response body: a stack trace in an HTTP
      response is a real information leak (paths, versions, sometimes a
      query with a value in it) and this app has no other layer that would
      have stopped it reaching the client.
    """
    error_logger = logging.getLogger("tessellate.errors")

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        _request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail
        code = _code_for_status(exc.status_code)
        hint = None
        if isinstance(detail, dict):
            # A route opting into the richer shape directly, see the
            # docstring above. `.get("detail", detail)` means a dict that
            # forgot to include its own "detail" key still round-trips as
            # itself rather than silently becoming `None`.
            code = detail.get("code", code)
            hint = detail.get("hint", hint)
            detail = detail.get("detail", detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail, "code": code, "hint": hint},
            headers=getattr(exc, "headers", None),
        )

    #: **Out of space is the one failure the person can actually fix, so it
    #: says so.** Measured before this: with the store unable to take another
    #: page, `POST /entries` raised `sqlite3.OperationalError: database or
    #: disk is full` straight out of the route, and the handler below turned
    #: it into `{"detail": "Internal error"}` with a reference number. For a
    #: notebook whose whole promise is that your writing is safe on your own
    #: machine, "Internal error" after pressing save is the worst answer
    #: available: the text is still in the editor, nothing says why it would
    #: not save, and nothing suggests what to do. Reading kept working
    #: throughout, which is worth saying on the way past, because it means
    #: the notebook is intact and this is recoverable.
    #:
    #: Two shapes, one cause. SQLite answers `SQLITE_FULL` as an
    #: `OperationalError` whose message is "database or disk is full"; an
    #: upload, an export or a log write answers `OSError` with `ENOSPC`. Both
    #: mean the same thing to the person and get the same sentence.
    #:
    #: 507, which is what "Insufficient Storage" is for, rather than the 500
    #: this used to be: it is the status a client can branch on, and the
    #: frontend's error toast already shows `detail`.
    #:
    #: Deliberately narrow. `OperationalError` also covers a locked database
    #: and a missing table, and neither is this; matching the message is
    #: uglier than an error code and is what the driver actually gives us,
    #: since `sqlite3` exposes no stable constant for it.
    #: The recognition itself lives in `core/diskspace.py`, because the
    #: pre-write guard below and this after-the-fact handler have to agree
    #: about what "out of space" means, and a second copy of a two-shape
    #: match is exactly the kind of thing that drifts.
    _is_out_of_space = diskspace.out_of_space

    def _is_locked(exc: BaseException) -> bool:
        """SQLite's "database is locked" (or "busy"), through SQLAlchemy or
        the driver: the message is all `sqlite3` gives to tell it apart."""
        import sqlite3

        from sqlalchemy.exc import OperationalError as SAOperationalError

        if not isinstance(exc, (SAOperationalError, sqlite3.OperationalError)):
            return False
        text = str(exc).lower()
        return "database is locked" in text or "database is busy" in text

    @app.exception_handler(OSError)
    async def _os_error_handler(request, exc: OSError) -> JSONResponse:  # noqa: ANN001
        if not _is_out_of_space(exc):
            return await _unhandled_exception_handler(request, exc)
        return _out_of_space_response(exc)

    def _out_of_space_response(exc: BaseException | None = None) -> JSONResponse:
        error_logger.error("out of disk space", exc_info=exc)
        return JSONResponse(status_code=507, content=out_of_space_body())

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request, exc: RequestValidationError) -> JSONResponse:
        """**One error shape for a request that did not validate** (audit
        2026-10-05, ARCH-12). FastAPI's own answer was `{"detail": [{type,
        loc, msg, input}]}`: no `code`, a list where every other error has a
        sentence, and `input` echoed back, so `POST /auth/unlock` with a
        password sent as a list returned the password in the response body.
        Now the sentence the frontend already built from that list
        (`plainHttpError`), `code: "invalid"`, and the fields, never the input.
        """
        fields = []
        for error in exc.errors():
            loc = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path")]
            fields.append({"field": ".".join(loc), "message": str(error.get("msg", ""))[:200]})
        named = fields[0]["field"].rsplit(".", 1)[-1].replace("_", " ") if fields and fields[0]["field"] else ""
        detail = f"Check the {named} and try again." if named else "That was not accepted. Check what you entered and try again."
        return JSONResponse(
            status_code=422,
            content={"detail": detail, "code": "invalid", "hint": None, "fields": fields},
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_request, exc: Exception) -> JSONResponse:
        if _is_out_of_space(exc):
            return _out_of_space_response(exc)
        if _is_locked(exc):
            # **A busy notebook is a wait, not a bug.** SQLite has one write
            # lock; a write that waited out the busy timeout behind another
            # (a background pass, an import) used to answer "Something went
            # wrong" with a ref number (ARCH-01). 503 with `busy` is a status
            # a client can retry on and a sentence the person can act on.
            error_logger.warning("database busy: %s", exc)
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "The notebook is busy for a moment. Try again.",
                    "code": "busy",
                    "hint": None,
                },
                headers={"Retry-After": "2"},
            )
        # A fresh id per failure, logged next to the real traceback and
        # handed back to the user, "it broke" with no ref is unreportable;
        # this ref is the thing a bug report can actually be filed against.
        ref = uuid.uuid4().hex
        error_logger.exception("Unhandled exception (ref=%s)", ref, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": (
                    "Something went wrong inside Tessellate. Try again, and if it "
                    "keeps happening, check Settings > Logs."
                ),
                "code": "internal",
                "ref": ref,
            },
        )


#: **"The disk is full" is not something a person can act on; "your notebook
#: is on /home/you/.local/share, which has 4.2 MB left, free about 46 MB" is.**
#: The owner asked for exactly that (INBOX 266, item 6: "which disk, roughly
#: how much is needed, what to delete"), so the sentence is built from the
#: numbers rather than written once and frozen. One function, because the
#: guard that refuses a write before it starts and the handler that catches
#: one that already failed have to say the same thing.
def out_of_space_body(wanted: int | None = None) -> dict:
    data_dir = None
    try:
        data_dir = str(deps.get_config().data_dir)
    except Exception:  # noqa: BLE001  # pragma: no cover - only before the config exists
        pass
    free = diskspace.free_bytes(data_dir) if data_dir else None
    where = f" Your notebook is in {data_dir}." if data_dir else ""
    room = f" There is {diskspace.human_bytes(free)} free there." if free is not None else ""
    need = ""
    if wanted is not None and data_dir:
        short = diskspace.shortfall(data_dir, wanted)
        if short:
            need = f" Free up about {diskspace.human_bytes(short)} and try again."
    return {
        "detail": "This computer has run out of disk space, so that could not be saved.",
        "code": "out_of_space",
        "hint": (
            f"{where}{room}{need or ' Free some space and try again.'}"
            " Nothing already in your notebook has been lost, and you can still"
            " read and export it. Emptying the trash, or deleting old backups"
            " and exports in Settings, is usually the quickest space to find."
        ).strip(),
        #: The numbers as numbers too, so the Settings panel and any future
        #: caller are not reduced to parsing the sentence.
        "free_bytes": free,
        "data_dir": data_dir,
    }


class SpaceGuard:
    """Refuse a write that cannot fit, before a byte of it is read.

    **Where it cannot be forgotten**, which is the whole point: every write
    in this app arrives as one non-GET request with a `Content-Length`, so
    one ASGI middleware covers the routes that exist, the routes added
    tomorrow, and the ones nobody remembered to check. A per-call-site check
    would have to be remembered fifty times.

    What it buys over letting the write fail: the failure happens without
    consuming the last megabyte. Measured (INBOX 266): a 50 MB upload onto a
    nearly-full disk used to write until the filesystem was at zero, and at
    zero even `POST /auth/unlock` answered 507, so the person could not open
    their notebook at all. Refusing the upload up front leaves the disk
    exactly as full as it was and the notebook exactly as usable.

    GET and HEAD are never touched: reading a notebook needs no space, and
    that stays true right down to the last byte.
    """

    #: Bodies below this are never weighed. A note, a preference, a
    #: whiteboard stroke: at this size the arithmetic is noise next to the
    #: 2 MB headroom, and weighing them only adds a way to refuse work the
    #: disk could plainly do.
    SMALL_BODY_BYTES = 64 * 1024

    def __init__(self, app) -> None:  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope.get("type") != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        wanted = _content_length(scope)
        if wanted is not None and wanted > self.SMALL_BODY_BYTES:
            try:
                config = deps.get_config()
            except Exception:  # noqa: BLE001  # pragma: no cover - before the config exists
                config = None
            if config is not None and not diskspace.has_room_for(config.data_dir, wanted):
                logging.getLogger("tessellate.errors").error(
                    "refused a %s-byte write: %s has %s free",
                    wanted,
                    config.data_dir,
                    diskspace.free_bytes(config.data_dir),
                )
                response = JSONResponse(status_code=507, content=out_of_space_body(wanted))
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _content_length(scope) -> int | None:  # noqa: ANN001
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


#: How long shutdown waits for the background pool's workers. Short: the only
#: thing that can still be running is one job (a Tesseract pass or a model
#: call), the workers are daemons, and a quit that waits for a vision read of
#: a 20-page scan is the hang `core/bgtasks.py` was written to prevent.
_JOB_SHUTDOWN_SECONDS = 3.0


#: A request that changes something: someone at this computer acting.
_ACTS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestPulse:
    """Pure ASGI, one line of work per request: tells the embedding warm-up
    that the app is busy, so the model load waits for a quiet moment rather
    than landing on top of the dashboard's first fetches
    (`ai.embeddings.note_request`)."""

    def __init__(self, app) -> None:  # noqa: ANN001
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        embeddings.note_request()
        #: Which device this request is for (core/origin.py): carried into
        #: the jobs it queues, so a phone's save cannot start an install here.
        another = is_another_device(Request(scope))
        if not another and scope.get("method") in _ACTS and origin.has_deferred():
            origin.run_deferred(jobs.enqueue)
        #: The request's endpoint names a model call no run owns (INBOX 805).
        with origin.acting_for(another), jobruns.for_request(scope):
            await self.app(scope, receive, send)


def _start_services() -> Path:
    """`create_app`'s first step: the logs, the egress ledger, the app's
    state, interrupted jobs, the launcher's choices and the local services,
    in the order they always started. Returns the ledger's path, which the
    lifespan flushes at shutdown. Lifted with no behaviour change (audit
    2026-10-05, ARCH-22: create_app was 354 lines)."""
    pin_static_mime_types()
    logbuffer.install()  # start capturing logs for the Settings viewer
    # The privacy receipt's record (core/egress.py): before anything below
    # can open a socket, so a startup download or a warmup that phones home
    # is on the receipt too. Idempotent, and permanent by design.
    egress.install()
    # Coarse phase markers for the desktop launcher's loading window
    # (core/startup_status.py): the only reader, and a no-op for every
    # other way this app runs (the web build, tests, `python -m tessellate`
    # without `--desktop`), since nothing else ever calls get_phase().
    startup_status.set_phase("Setting up your notebook…")
    init_app_state()
    # A job record still saying "running" belongs to the process that just
    # ended; say so before anything new can be mistaken for it.
    jobruns.mark_interrupted()
    # The durable jobs (core/jobstore.py): the readings and filings a closed
    # or killed process left queued or half done are queued again, once.
    jobs.resume()
    ledger_path = deps.get_config().data_dir / egress.LEDGER_NAME
    # Keep the ledger current as connections happen, not only on a receipt
    # read and at a clean shutdown, so a killed process loses at most
    # `egress.FLUSH_DELAY` of what it saw.
    egress.configure(ledger_path)
    # The bin purge, the event-log compaction and the daily backup used to
    # run here, before the port opened: measured 4.45 s from launch to first
    # byte at 5,000 notes, the day's first launch copying the whole database
    # first (audit 2026-10-05, ARCH-19). They start from `lifespan` below, on
    # a thread, once the server is answering; each is safe beside requests
    # (a backup is SQLite's online backup, the purge and the compaction are
    # ordinary transactions).
    # The terminal's answer to "check for updates automatically?" (start.sh
    # asks before there is a Python to write it down; routes_update).
    routes_update.apply_launcher_choice(deps.get_config())
    startup_status.set_phase("Starting local services…")
    _start_searxng_if_asked()
    _start_autonomous_loop()
    startup_status.set_phase("Warming up search…")
    # The session factory is handed in so embeddings never has to import the
    # dependency container that imports it.
    # INBOX 509: off loads it on first use instead (a lighter start; the
    # first note waits the model's cold load, about 7 s, to be filed).
    if deps.get_config().get_preference("warm_search_model_at_launch", True):
        embeddings.start_warmup(deps.get_embeddings(), deps.get_db().session)
        #: The speller's lists and the UK/US pairs (INBOX 895), about a
        #: second built once on the job pool, so the first question does not
        #: wait for them.
        from tessellate.ai import spelling

        spelling.warm_in_background()
    # The filing model's warm-up and the retry of stand-ins are *not* started
    # here: `create_app` runs for every test app too, and a model call at
    # construction was an extra round on every fake model in the suite. The
    # page asks for both once it is unlocked (`POST /models/warm-filing`).
    startup_status.set_phase("Starting the server…")
    return ledger_path


def _add_middleware(app: FastAPI) -> None:
    """The middleware stack, in the order it is added (the last added runs
    first, so the order is load-bearing; each block says why). ARCH-22."""

    # Middleware is added inside-out: the LAST one added is the outermost, so
    # the headers below are stamped on the origin check's own 403 too.
    #
    # **Compression goes on FIRST, which means innermost, and the ordering is
    # load-bearing rather than stylistic.** Both middlewares below are
    # `BaseHTTPMiddleware`, and that base class re-wraps every response it
    # handles as a *streaming* response. Starlette's gzip only consults
    # `minimum_size` on a response it can measure, a stream has no length to
    # measure: so a gzip layer placed outside either of them compresses
    # everything regardless of size. Measured while adding this: with gzip
    # outermost, `GET /health` (70 bytes) and `GET /tags` (2 bytes) both came
    # back `content-encoding: gzip`, i.e. spending CPU to make small responses
    # larger, with `minimum_size` silently doing nothing. Innermost, gzip sits
    # against the routers and the static mount and sees real `Content-Length`
    # headers, so the threshold works.
    #
    # **Why compression matters here at all, given it is localhost.**
    # `app.js` is over a megabyte of unminified source and there is no bundler
    # and no minifier by design (CLAUDE.md: "no build step"), so this is the
    # only remaining lever on transfer size. It is not really about the wire:
    # the desktop shell is a WebView with its own cache, and `GET /entries`
    # hands back up to a thousand full note bodies per page.
    #
    # **Streaming was checked, not assumed**, this app has three streaming
    # endpoints (chat in `routes_chat`, the weekly digest in `routes_insights`,
    # the live log in `routes_settings`), and "gzip buffers a stream into
    # uselessness" is true of some implementations. Starlette's is not one:
    # `GZipResponder._compress_body` flushes with `Z_SYNC_FLUSH` on every chunk
    # carrying `more_body`, so each chunk still leaves the server as it is
    # produced. `text/event-stream` is already in Starlette's own exclusion
    # list; the two NDJSON streams are not, so they are named explicitly, 
    # which keeps those two responses byte-identical to what they were before
    # this existed.
    #
    # `compresslevel=6`, not the library default of 9: 9 costs meaningfully
    # more CPU for a few percent of size on text, and this is a single process
    # serving one user who is usually running a local model on the same machine.
    #
    # On BREACH: the attack needs compression *plus* a secret in the response
    # *plus* attacker-controlled reflection, and the last two legs are absent
    # here: the auth token travels in a header rather than a cookie (see this
    # module's docstring) and `OriginCheckMiddleware` already refuses
    # cross-origin requests outright, so there is no third party in a position
    # to make the guesses the attack is built from.
    app.add_middleware(
        GZipMiddleware,
        minimum_size=500,
        compresslevel=6,
        exclude_content_types=(
            *DEFAULT_EXCLUDED_CONTENT_TYPES,
            "application/x-ndjson",
            # The grammar checker's 15.9 MB binary (INBOX 401). Measured on
            # loopback: 755 ms to gzip it on every cold fetch against 60 ms
            # to send it as it is, so compressing it made the first check
            # slower by the whole difference. Never compressed *here*: the
            # precompressed cache (`RevalidatedStatic._precompressed`) gzips
            # it once per version and this middleware passes that through.
            "application/wasm",
        ),
    )
    app.add_middleware(security.OriginCheckMiddleware)
    # Who is asking, for the vault's per-session grants (routes_auth.VaultScope).
    app.add_middleware(routes_auth.VaultScope)
    # LAN mode's rebinding guard: a no-op on loopback (core/netbind.py).
    app.add_middleware(security.HostCheckMiddleware)
    app.add_middleware(SpaceGuard)
    app.add_middleware(RequestPulse)
    # Outside the Host and Origin checks, so a refused request is never read
    # either; inside the security headers, so a 413 still carries them (SEC-06).
    app.add_middleware(security.BodyCapMiddleware)
    app.add_middleware(
        security.SecurityHeadersMiddleware,
        # Tracks index.html rather than freezing one policy at startup, see
        # CspForPage for the reported bug that caused ("blocked
        # script-src-elem: inline" after any frontend update, until restart).
        csp=security.CspForPage(FRONTEND_DIR / "index.html"),
    )
    # Outermost, so every check above sees the path without its `/api/v1`
    # and an agent-named request is named for everything inside it (H4).
    app.add_middleware(versioning.ApiVersionMiddleware)


def _include_routers(app: FastAPI, locked: list) -> None:
    """Every API router, behind `locked` unless it says otherwise. ARCH-22."""
    app.include_router(routes_auth.router)
    app.include_router(routes_entries.router, dependencies=locked)
    app.include_router(routes_mentions.router, dependencies=locked)
    app.include_router(routes_meetings.router, dependencies=locked)
    app.include_router(routes_inbox.router, dependencies=locked)
    app.include_router(routes_entities.router, dependencies=locked)
    app.include_router(routes_relations.router, dependencies=locked)
    app.include_router(routes_properties.router, dependencies=locked)
    app.include_router(routes_chat.router, dependencies=locked)
    app.include_router(routes_ask_history.router, dependencies=locked)
    app.include_router(routes_models.router, dependencies=locked)
    app.include_router(routes_settings.router, dependencies=locked)
    app.include_router(routes_maintenance.router, dependencies=locked)
    # The browser's own crash reports, which have to reach the log *before*
    # unlock: that is when the failure they describe happens. One route, and
    # `routes_settings.open_router`'s own comment says why it is separate.
    app.include_router(routes_settings.open_router)
    # The Run button's sandbox page: no data, its own sandboxing policy, and
    # registered before the documents router so `/documents/{id}` does not
    # claim the path (`api/run_sandbox.py`).
    app.include_router(run_sandbox.router)
    # A long run's row in Activity (DOCUMENTS_PLAN 25 row 9): locked.
    app.include_router(run_sandbox.jobs_router, dependencies=locked)
    # The offline translator (WORLD_CLASS_PLAN 28.5 row 10): what is
    # installed is behind the unlock; the engine and model files are open,
    # like the Python runtime's, because a Worker's fetch carries no token.
    app.include_router(routes_translate.router, dependencies=locked)
    app.include_router(routes_translate.files_router)
    app.include_router(routes_update.router, dependencies=locked)
    app.include_router(routes_websearch.router, dependencies=locked)
    app.include_router(routes_webclip.router, dependencies=locked)
    app.include_router(routes_backups.router, dependencies=locked)
    app.include_router(routes_spaces.router, dependencies=locked)
    app.include_router(routes_files.router, dependencies=locked)
    # A plain `<img src>` (or a note's own inline `![]()` markdown) never
    # attaches the X-Auth-Token header, so only these routes also accept the
    # media cookie, on their own gate rather than widening `locked` for every
    # route. See require_unlock_media's docstring.
    app.include_router(
        routes_files.media_router, dependencies=[Depends(routes_auth.require_unlock_media)]
    )
    app.include_router(routes_search.router, dependencies=locked)
    app.include_router(routes_tags.router, dependencies=locked)
    app.include_router(routes_categories.router, dependencies=locked)
    app.include_router(routes_conversations.router, dependencies=locked)
    app.include_router(routes_documents.router, dependencies=locked)
    app.include_router(routes_duplicates.router, dependencies=locked)
    app.include_router(routes_tidy.router, dependencies=locked)
    app.include_router(routes_drafts.router, dependencies=locked)
    app.include_router(routes_learned.router, dependencies=locked)
    app.include_router(routes_night.router, dependencies=locked)
    app.include_router(routes_bench.router, dependencies=locked)
    app.include_router(routes_editor.router, dependencies=locked)
    app.include_router(routes_import.router, dependencies=locked)
    app.include_router(routes_usage.router, dependencies=locked)
    app.include_router(routes_usage.capture_router, dependencies=locked)
    app.include_router(routes_questions.router, dependencies=locked)
    app.include_router(routes_resurface.router, dependencies=locked)
    app.include_router(routes_insights.router, dependencies=locked)
    app.include_router(routes_graph.router, dependencies=locked)
    app.include_router(routes_help.router, dependencies=locked)
    app.include_router(routes_reminders.router, dependencies=locked)
    # A notification's Done and Snooze, pressed by the service worker with a
    # token scoped to one reminder and those two actions (core/reminder_token.py)
    # instead of a session: the one route here outside the gate, and why is in
    # `routes_reminders.act_from_notification` and tests/test_every_route_is_locked.py.
    app.include_router(routes_reminders.open_router)
    app.include_router(routes_bookmarks.router, dependencies=locked)
    app.include_router(routes_voice.router, dependencies=locked)
    app.include_router(routes_recordings.router, dependencies=locked)
    app.include_router(
        routes_recordings.media_router,
        dependencies=[Depends(routes_auth.require_unlock_media)],
    )
    app.include_router(routes_captions.router, dependencies=locked)
    app.include_router(routes_tasks.router, dependencies=locked)
    app.include_router(routes_timeline.router, dependencies=locked)
    app.include_router(routes_library.router, dependencies=locked)
    app.include_router(routes_whiteboard.router, dependencies=locked)
    app.include_router(routes_board_library.router, dependencies=locked)
    app.include_router(routes_code_snippets.router, dependencies=locked)
    app.include_router(routes_code_assist.router, dependencies=locked)
    app.include_router(routes_board_history.router, dependencies=locked)
    app.include_router(routes_map_suggest.router, dependencies=locked)
    app.include_router(routes_map_from_notes.router, dependencies=locked)
    app.include_router(routes_debug.router, dependencies=locked)
    app.include_router(routes_privacy.router, dependencies=locked)
    app.include_router(routes_capabilities.router, dependencies=locked)
    app.include_router(routes_read.router, dependencies=locked)
    app.include_router(routes_statistics.router, dependencies=locked)
    app.include_router(routes_utilities.router, dependencies=locked)
    #: WORLD_CLASS_PLAN section 17: the review queue, most opened, tidy proposals, charts.
    app.include_router(routes_vision.router, dependencies=locked)


def _add_system_routes(app: FastAPI, locked: list) -> None:
    """The few routes the app answers itself: the schema, the static cache,
    health, the single-instance focus and the changelog. ARCH-22."""

    @app.get("/openapi.json", include_in_schema=False, dependencies=locked)
    def openapi_schema() -> JSONResponse:
        """The API schema, for whoever has unlocked the notebook.

        `openapi_url=None` above stops FastAPI serving it to the whole
        network; this is the same document, behind the unlock. Tooling that
        wants it sends `X-Auth-Token` like every other call.
        """
        return JSONResponse(app.openapi())

    @app.post("/system/clear-static-cache", tags=["system"], dependencies=locked)
    def system_clear_static_cache() -> dict[str, bool | int]:
        """Settings, Data, Clear app cache: the server's half (its compressed
        copies of the page's own files). Defined here, not in routes_settings,
        because `RevalidatedStatic` lives here and that import would be a cycle."""
        return {"cleared": True, "files": clear_static_cache()}

    @app.get("/health", tags=["system"])
    def health(request: Request) -> dict[str, str | bool]:
        from tessellate.core import reminder_notifier

        #: The desktop shell and its notifier belong to this computer. A phone
        #: that read `desktop: true` saved its exports onto this disk and
        #: offered "Open folder", which opened Explorer here (the owner,
        #: 2026-10-11); now it downloads to itself like any browser tab.
        here = not is_another_device(request)
        return {
            "status": "ok",
            "app": "Tessellate",
            "version": __version__,
            # Whether we are being viewed through the pywebview window rather
            # than a browser tab. The frontend needs to know because a
            # `<a download>` click does nothing there, pywebview has no
            # download handler: so exports have to be written by the server
            # instead (§35E). Set by `python -m tessellate --desktop`.
            "desktop": here and os.getenv("TESSELLATE_DESKTOP") == "1",
            # The launcher posts the system notification for a due reminder
            # (core/reminder_notifier.py), so the page does not post a second.
            "os_notify": here and reminder_notifier.active(),
            #: Whether controls that act on this computer apply to this page.
            "this_computer": here,
        }

    @app.get("/instance", tags=["system"])
    def instance() -> dict[str, str]:
        """Which notebook this server is serving, for a launch deciding
        whether a Tessellate already on its port is *this* one (WORLD_CLASS 423
        g). Open like `/health`: the asking process has no session. It carries
        a hash of the resolved data directory (`instance_lock.data_dir_id`),
        never the path."""
        from tessellate.core import instance_lock

        return {
            "app": "Tessellate",
            "data_dir_id": instance_lock.data_dir_id(deps.get_config().data_dir),
        }

    @app.post("/instance/focus", include_in_schema=False)
    def instance_focus(x_instance_token: str | None = Header(default=None)) -> dict[str, bool]:
        """A second launch asking this one to bring its window forward.

        Open like `/health` because the asking process has no session, and
        guarded by something better than one: the token in this server's own
        `instance.lock` (core/instance_lock.py), which only someone who can
        read the data directory has. Compared in constant time. `focused` is
        False on a server started in browser mode, which has no window, and
        the second launch then opens a window onto this server instead.
        """
        from tessellate.core import instance_lock

        expected = instance_lock.current_token()
        if not expected or not x_instance_token or not hmac.compare_digest(
            expected.encode(), x_instance_token.encode()
        ):
            raise HTTPException(status_code=403, detail="Not this instance's token.")
        return {"focused": instance_lock.focus()}

    # GET /update/check, /update/releases, /update/source-status, and
    # POST /update/apply all live in routes_update.py now, this endpoint
    # used to be defined inline here, but it feeds and is fed by the rest
    # of that module's update machinery, so it moved to sit next to it.

    @app.get("/changelog", tags=["system"], dependencies=locked)
    def changelog() -> dict:
        """CHANGELOG.md, so "what changed?" is answerable inside the app.

        Behind the unlock like everything else. It was the one route outside
        `/health`, `/auth` and the lock screen's own assets that answered an
        unauthenticated caller, found by the walk in
        `tests/test_every_route_is_locked.py` rather than by review, which is
        exactly what that test is for. Nothing needs it before unlock: the
        only caller is the About panel (`settings.js`), which opens inside an
        unlocked notebook. It reads a file off disk and hands back its
        contents, so leaving it open on a LAN would be a file read for
        anybody who could reach the port, for a file nobody outside has a
        reason to want.

        The file already exists and is written for people, which is the whole
        argument for serving it rather than maintaining a second in-app list
        that would drift from it (§36E). Read per request rather than cached:
        it changes when the app is updated, and an update replaces the process
        anyway: so a cache would only ever be stale in development.
        """
        # BUNDLE_ROOT rather than three levels up: a packaged build keeps its
        # files in the bundle's own folder, and `tessellate.spec` puts this
        # file there, so the About panel's notes are not empty on Windows.
        path = BUNDLE_ROOT / "CHANGELOG.md"
        try:
            # A response built here is encoded on the worker thread; a returned
            # dict would be encoded on the event loop, and this one is 750 KB
            # (audit 2026-10-05, ARCH-25: 132 ms p50 a call).
            return JSONResponse({"markdown": path.read_text(encoding="utf-8")})
        except OSError:
            # A packaged build may not ship it. Missing notes are not an error
            # worth a 500: the About panel just doesn't offer them.
            return {"markdown": ""}


def create_app() -> FastAPI:
    # First, before any singleton is built. This catches `uvicorn … --workers 4`
    # run directly against this factory, which is the only way the app can be
    # started multi-worker: `python -m tessellate` hands uvicorn an app object
    # rather than an import string, and uvicorn cannot fork that.
    deps.refuse_multiple_workers()
    ledger_path = _start_services()

    # **Nothing stopped background work when the app quit, and that was the
    # whole of the bug.** Reported directly: "make sure that if the app is
    # quit, all ai tasks and bg tasks stop as well." `/shutdown`'s own
    # docstring already promised that "lifespan handlers run, and the SearXNG
    # subprocess this app may own is torn down by the code that already knows
    # how", accurately describing a handler that did not exist. Daemon
    # threads do die with the process; a pip subprocess and a SearXNG server
    # do not, and an autonomous pass part-way through writing to the notebook
    # was cut off wherever it happened to be.
    #
    # An async lifespan rather than the deprecated `@app.on_event`, and it
    # yields immediately: everything above already ran at import time, and
    # moving it in here would change when the singletons exist for every
    # caller of `create_app()`, tests included.
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # On the pool, not a thread of its own (the THREAD_SITES ratchet in
        # tests/test_flaw_class_lints.py): it is the app's housekeeping, a
        # quiet kind, after the server is up (ARCH-19).
        jobs.enqueue("maintenance", _startup_maintenance, name="startup maintenance")
        yield
        # Never raises: `stop_all` swallows per-job failures itself, and a
        # shutdown that fails to shut down is worse than one that leaves a
        # line in the log.
        bgtasks.stop_all()
        # The registry of threads that are not jobs (`core/background.py`):
        # its watchers name how they stop, and quitting is when to ask.
        from tessellate.core import background

        background.stop_all()
        # The reminder notifier's loop is a job on that pool, so it is told to
        # end first: otherwise a quit waits the pool's whole deadline for it.
        from tessellate.core import reminder_notifier

        reminder_notifier.stop_running()
        # The bounded pool (core/jobs.py) is the other half: `stop_all`
        # handles the jobs that own something interruptible, and this one
        # drops the queue of captions and OCR passes behind it. A deadline
        # rather than a join, because the job in flight may be inside a model
        # call that cannot be interrupted and the workers are daemons: see
        # `jobs.Pool.shutdown`.
        jobs.shutdown(deadline=_JOB_SHUTDOWN_SECONDS)
        # The receipt's ledger keeps what this launch saw; the writer thread
        # (`egress.configure`) flushes within a second of a connection and the
        # route on every read, so this is the last drain on a clean quit.
        # The path was taken at startup: by now the app state may be gone.
        egress.flush(ledger_path)

    # No auto-mounted `/docs`, `/redoc` or `/openapi.json`. Two reasons, and
    # the second is the one that matters. The Swagger and ReDoc pages load
    # their scripts from a CDN, which this offline app's own CSP refuses, so
    # they never rendered anyway. And the schema: every route, parameter and
    # model name, 238 paths, was served to anyone who could reach the port,
    # before the unlock: MODERNISATION_AUDIT.md D5, the one security finding
    # in that audit not already handled. The schema is mounted again below,
    # behind the same `locked` dependency every data route carries.
    app = FastAPI(
        title="Tessellate",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    _register_error_handlers(app)
    _add_middleware(app)

    # Everything that touches the user's data sits behind the unlock
    # gate; /auth itself and /health stay open.
    locked = [Depends(require_unlock)]
    _include_routers(app, locked)
    _add_system_routes(app, locked)

    # The owner's benches (tools/avatar-lab.html, tools/companion-sim.html)
    # are served beside the app so they can load its own renderers from
    # "/"; plain static files, no data behind them.
    tools_dir = FRONTEND_DIR.parent / "tools"
    if tools_dir.is_dir():
        app.mount("/tools", _UnversionedStatic(directory=tools_dir), name="tools")

    # Mounted last so the API routes above always win; html=True makes
    # "/" serve frontend/index.html.
    if FRONTEND_DIR.is_dir():
        app.mount(
            "/", RevalidatedStatic(directory=FRONTEND_DIR, html=True), name="frontend"
        )

    return app
