"""The one place a download gets its file name (notes audit 1031, N31).

A `Content-Disposition` header is latin-1 on the wire, a title is any script,
so a Japanese title used to be a 500. `attachment_headers` writes a plain
ASCII `filename` for old clients and an RFC 5987 `filename*` that carries the
real name; `safe_filename` turns a title into a name that cannot steer a path.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote


def safe_filename(title: str, extension: str, fallback: str = "note", limit: int = 60) -> str:
    """A title is user text; it must not steer where the file lands."""
    cleaned = re.sub(r"[^\w\s-]", "", title or "").strip() or fallback
    cleaned = re.sub(r"[\s_]+", "-", cleaned)[:limit]
    return f"{cleaned}.{extension}" if extension else cleaned


def _ascii_fallback(name: str) -> str:
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    plain = re.sub(r"[^A-Za-z0-9._ -]", "", stem).strip(" .")
    plain = plain or "download"
    return f"{plain}.{re.sub(r'[^A-Za-z0-9]', '', ext)}" if ext else plain


def attachment_headers(name: str, disposition: str = "attachment") -> dict[str, str]:
    """Headers for a file the person saves: ASCII fallback plus `filename*`."""
    name = re.sub(r"[\x00-\x1f\x7f\"\\/]", "", name or "") or "download"
    fallback = _ascii_fallback(name)
    value = f'{disposition}; filename="{fallback}"'
    if fallback != name:
        value += f"; filename*=UTF-8''{quote(name, safe='')}"
    return {"Content-Disposition": value}


_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


def _span(request_range: str | None, total: int) -> tuple[int, int] | None | bool:
    """A single `bytes=` range as (start, end); None to send the whole file
    (no range, or one RFC 9110 says to ignore, such as `bytes=5-2`); False
    when it cannot be satisfied (416)."""
    found = _RANGE.match((request_range or "").strip())
    if not found or not (found.group(1) or found.group(2)):
        return None
    first, last = found.group(1), found.group(2)
    if first and last and int(first) > int(last):
        return None
    if not first:
        size = int(last)
        return (max(0, total - size), total - 1) if size and total else False
    start = int(first)
    if start >= total:
        return False
    return start, min(int(last), total - 1) if last else total - 1


def sealed_http(exc: Exception):  # noqa: ANN201
    """A sealed file this caller cannot read: 423 while locked, 409 when damaged."""
    from fastapi import HTTPException

    from tessellate.core import sealed_files

    if isinstance(exc, sealed_files.SealedLocked):
        return HTTPException(status_code=423, detail=sealed_files.LOCKED_DETAIL)
    return HTTPException(status_code=409, detail=sealed_files.DAMAGED_DETAIL)


@contextmanager
def unsealed(path: Path, *, write: bool = False) -> Iterator[Path]:
    """A path a file reader can open, sealed or not (L-world-class-52); with
    `write`, what the block wrote goes back sealed. 423 while locked, 409 when
    damaged. Every route that hands a stored file to a reader goes through
    this or `sealed_files` (`tests/test_sealed_readers.py`)."""
    from tessellate.core import sealed_files

    try:
        with sealed_files.readable(path, write=write) as plain:
            yield plain
    except sealed_files.SealedError as exc:
        raise sealed_http(exc) from exc


def sealed_aware(path, media_type=None, headers=None, filename=None, request_range=None):  # noqa: ANN001, ANN201
    """A file response for a file that may be sealed (L-world-class-52).

    A plain file is a `FileResponse` as before (Range included). A sealed one
    is unsealed in memory, never to disk: streamed a frame at a time whole, or
    a single `bytes=` Range answered from only the frames it touches, so an
    `<audio>` element still seeks. 423 while its key is not loaded for this
    caller, 409 when it is damaged.
    """
    from fastapi.responses import FileResponse, Response, StreamingResponse

    from tessellate.core import sealed_files

    headers = dict(headers or {})
    if not sealed_files.is_sealed(path):
        return FileResponse(path, media_type=media_type, headers=headers, filename=filename)
    if filename is not None:
        headers.update(attachment_headers(filename))
    headers["Accept-Ranges"] = "bytes"
    try:
        total = sealed_files.plain_size(path)
        span = _span(request_range, total)
        if span is None:
            body = sealed_files.iter_plain(path)
            return StreamingResponse(body, media_type=media_type, headers={**headers, "Content-Length": str(total)})
        if span is False:
            return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{total}"})
        start, end = span
        headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        return Response(sealed_files.read_range(path, start, end), status_code=206, media_type=media_type, headers=headers)
    except sealed_files.SealedError as exc:
        raise sealed_http(exc) from exc
