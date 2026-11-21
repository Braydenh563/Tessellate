"""Turning a PDF page into an image, so a vision model can read it.

This is the piece `core/docview.py`'s docstring described as missing: a scanned
PDF has no text layer, `ai/vision_ocr.py` reads *images*, and nothing here
turned one into the other. The seam was built and the plug was not.

**Why pypdfium2 and not the alternatives.** Measured rather than assumed, 
installed into this project's own venv and run:

- ``pypdfium2`` + ``Pillow``: ~16 MB on disk, installs in seconds from a
  self-contained wheel, no system packages, **no torch**, and renders a page in
  about 20 ms. It is Google's PDFium, the renderer in Chrome, under a BSD
  licence.
- ``PyMuPDF`` renders just as well but is AGPL, which for this project is a
  licensing decision rather than a dependency (see ANALYSIS.md).
- ``pdf2image`` shells out to Poppler, a system package the user has to install
  by hand: the opposite of what a local-first app that must "just run" wants.

Optional, and it stays optional. Everything here degrades to "no pages" if the
library is absent, and `core/extras.py` carries the install button. The rule
that made the extras catalogue exist applies to this too: a new dependency is a
decision, not a side effect.

Deliberately not Tesseract, by direct instruction: *"I basically dont want to
download tesseract and only want to use an ai vision learning and ocr model for
images and scanned documents."* Nothing here reads text. It produces pixels and
hands them to the model.

**PDFium runs in a child process** (L-world-class-321, SECURITY.md T19):
every open, count and render here is a `core/parse_sandbox.py` call into
`core/parse_jobs.py`, with a time and memory limit, so a crafted PDF that
crashes or hangs PDFium costs one child, not the server. The child serves one
job at a time, which is also what PDFium needs: several threads in it at once
corrupted its heap (`corrupted double-linked list`, SIGABRT, from a browser
fetching every page of a PDF at once), which is why this module held a lock
before the child existed.
"""

from __future__ import annotations

import importlib.util
import logging
import threading
import time
from collections import OrderedDict
from pathlib import Path

from tessellate.core import parse_sandbox
from tessellate.core.deps import register_cache_reset

logger = logging.getLogger(__name__)

_JOBS = "tessellate.core.parse_jobs"

#: How many pages of one PDF are ever rendered.
#:
#: A vision model reads a page in seconds, not milliseconds, so a 300-page scan
#: is an hour of GPU time nobody asked for. Eight pages is enough to answer
#: "what is this document", which is what the viewer is for, and the message
#: says plainly when there was more.
MAX_PAGES = 8

#: Render scale. PDF user units are 1/72 inch, so 2.0 is ~144 DPI.
#:
#: Chosen against what OCR models actually want rather than what looks nice:
#: below about 150 DPI small type stops being legible to them, and above 300
#: the image gets large enough that the *model* becomes the bottleneck twice
#: over: more pixels to encode, and a longer prompt to hold them.
RENDER_SCALE = 2.0

#: Refuse to rasterise anything larger. A PDF is a container format and can
#: hold a single 20,000 x 20,000 page; rendering that at 2x is several
#: gigabytes of bitmap in one allocation. The limit is on the rendered pixel
#: count rather than the file size, because those are unrelated, a 40 KB PDF
#: can declare a page a metre wide.
MAX_PIXELS = 40_000_000

#: Seconds one page may take in the child before it is killed. A letter page
#: at 2x draws in ~116 ms; a page that takes this long is a file built to hang.
PAGE_TIMEOUT = 30.0
COUNT_TIMEOUT = 15.0


def available() -> bool:
    """Is there a rasteriser the child can import?

    `find_spec`, not an import: the server process no longer loads PDFium at
    all, and the child sees the server's `sys.path` (`parse_sandbox`).
    """
    return all(importlib.util.find_spec(name) is not None for name in ("pypdfium2", "PIL"))


def page_count(path: Path) -> int:
    """How many pages, or 0 if it cannot be read at all."""
    if not available():
        return 0
    try:
        return int(parse_sandbox.call(f"{_JOBS}:pdf_page_count", str(path), timeout=COUNT_TIMEOUT))
    except parse_sandbox.ParseRefused as exc:  # a viewer must not 500 on a bad file
        # `%r`, not `%s`, on `path` throughout this file: flagged by CodeQL
        # (py/log-injection) even though `path` is always `attachment.stored_name`
        # (a hash this app generated itself, see routes_files.py), never the
        # uploaded file's own name. `%r` closes the gap for free either way:
        # repr() escapes newlines and control characters.
        logger.debug("couldn't count pages in %r: %s (%s)", path, exc.kind, exc.detail)
        return 0


def _draw(path: Path, index: int, *, greyscale: bool, scale: float = RENDER_SCALE) -> bytes | None:
    """One page to PNG bytes in the child, or None (past the end, or over
    `MAX_PIXELS`). Raises `ParseRefused`. Shared by `render_pages` (the
    vision-OCR batch) and `render_page` (the viewer)."""
    png = parse_sandbox.call(
        f"{_JOBS}:pdf_page", str(path), int(index), bool(greyscale), float(scale), MAX_PIXELS,
        timeout=PAGE_TIMEOUT,
    )
    if png is None:
        logger.info("page %d of %r was not drawn: past the end or over the pixel limit", index + 1, path.name)
    return png if isinstance(png, bytes) else None


def render_pages(path: Path, limit: int = MAX_PAGES) -> list[bytes]:
    """The first ``limit`` pages as PNG bytes, or [].

    Never raises. Every caller is a viewer or a background job, and a
    malformed, encrypted or truncated PDF is an ordinary thing to be handed, 
    the honest answer is "no pages", which the caller already has a message
    for.

    **One page per child job, not the whole batch** (attach-1026 O2, the
    owner: "I think it waits for rapid ocr or tesserract to read the whole
    document first before loading the other pages"). Each page is its own
    call, and the thread yields between pages, so a page view or a rail
    thumbnail takes its turn in the child instead of waiting behind the lot.
    """
    if not available():
        return []
    pages: list[bytes] = []
    count = min(page_count(path), max(0, limit))
    for index in range(count):
        try:
            png = _draw(path, index, greyscale=True)
        except parse_sandbox.ParseRefused as exc:  # see the docstring
            logger.info("couldn't rasterise %r: %s (%s)", path, exc.kind, exc.detail)
            return pages
        if png is not None:
            pages.append(png)
        time.sleep(0.001)
    return pages


#: Pages already drawn, so a page seen again (the rail, a flip back, the
#: regions request that draws the same page to read it) costs a dictionary
#: look-up instead of a render behind the lock. Keyed by the file's identity
#: (path, mtime, size), so a replaced file is never served stale. Bounded by
#: bytes, least recently used first; one answer over the whole budget is not
#: kept.
_CACHE_BYTES = 48 * 1024 * 1024
_page_cache: OrderedDict[tuple, bytes] = OrderedDict()
_page_cache_bytes = 0
_page_cache_lock = threading.Lock()

#: A rail thumbnail: a quarter of the width, a sixteenth of the pixels, which
#: is ~7 ms a page where the full page is ~116 ms.
THUMB_SCALE = RENDER_SCALE / 4


def _cache_get(key: tuple) -> bytes | None:
    with _page_cache_lock:
        png = _page_cache.get(key)
        if png is not None:
            _page_cache.move_to_end(key)
        return png


def _cache_put(key: tuple, png: bytes) -> None:
    global _page_cache_bytes
    if len(png) > _CACHE_BYTES:
        return
    with _page_cache_lock:
        old = _page_cache.pop(key, None)
        if old is not None:
            _page_cache_bytes -= len(old)
        _page_cache[key] = png
        _page_cache_bytes += len(png)
        while _page_cache_bytes > _CACHE_BYTES and _page_cache:
            _, dropped = _page_cache.popitem(last=False)
            _page_cache_bytes -= len(dropped)


def _cache_clear() -> None:
    global _page_cache_bytes
    with _page_cache_lock:
        _page_cache.clear()
        _page_cache_bytes = 0


#: Dropped with the app's singletons, so one test's pages never answer the next
#: (review, 2026-10-27; tests used to clear it by hand).
register_cache_reset(_cache_clear)


def render_page(path: Path, index: int, thumb: bool = False) -> bytes | None:
    """One page, by number, as PNG bytes, for *viewing* a PDF rather than
    reading it with a model. Kept apart from `render_pages`/`MAX_PAGES`
    deliberately: that cap exists to bound vision-model cost, and has nothing
    to do with how many pages a person can scroll past for free. In colour,
    unlike `render_pages`.

    None on any failure (page out of range, a file PDFium can't open, an
    oversized page, a child stopped at its limit): the caller,
    `routes_files.pdf_page`, turns that into a 404, the same "no pages"
    contract `render_pages` already keeps.
    """
    # CodeQL (py/log-injection) flags `index` itself here: it can't see that
    # FastAPI's `index: int` route parameter already rejects anything
    # non-numeric. An explicit int() re-cast into a fresh local breaks that
    # taint chain for CodeQL and costs nothing at runtime.
    try:
        safe_index = int(index)
    except (TypeError, ValueError):
        return None
    if not available() or safe_index < 0:
        return None
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size, safe_index, bool(thumb))
    except OSError:
        key = None
    if key is not None:
        hit = _cache_get(key)
        if hit is not None:
            return hit
    try:
        png = _draw(path, safe_index, greyscale=False, scale=THUMB_SCALE if thumb else RENDER_SCALE)
    except parse_sandbox.ParseRefused as exc:  # a viewer must not 500 on a bad file
        logger.info("couldn't rasterise page %d of %r: %s (%s)", safe_index, path, exc.kind, exc.detail)
        return None
    if png is not None and key is not None:
        _cache_put(key, png)
    return png
