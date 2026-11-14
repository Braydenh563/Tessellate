"""The one place a download gets its file name (notes audit 1031, N31).

A `Content-Disposition` header is latin-1 on the wire, a title is any script,
so a Japanese title used to be a 500. `attachment_headers` writes a plain
ASCII `filename` for old clients and an RFC 5987 `filename*` that carries the
real name; `safe_filename` turns a title into a name that cannot steer a path.
"""

from __future__ import annotations

import re
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


def sealed_aware(path, media_type=None, headers=None, filename=None, request_range=None):  # noqa: ANN001, ANN201
    """A file response for a file that may be sealed (L-world-class-52).

    A plain file is a `FileResponse` as before (Range included). A sealed one
    is unsealed in memory, never to disk, and a single `bytes=` Range is
    answered from only the frames it touches, so an `<audio>` element still
    seeks. 423 while its key is not loaded for this caller.
    """
    from fastapi import HTTPException
    from fastapi.responses import FileResponse, Response

    from tessellate.core import sealed_files

    headers = dict(headers or {})
    if not sealed_files.is_sealed(path):
        return FileResponse(path, media_type=media_type, headers=headers, filename=filename)
    if filename is not None:
        headers.update(attachment_headers(filename))
    headers["Accept-Ranges"] = "bytes"
    try:
        total = sealed_files.plain_size(path)
        found = _RANGE.match((request_range or "").strip())
        if not found or not (found.group(1) or found.group(2)):
            return Response(sealed_files.read(path), media_type=media_type, headers=headers)
        first, last = found.group(1), found.group(2)
        start = int(first) if first else max(0, total - int(last))
        end = min(int(last), total - 1) if first and last else total - 1
        if start >= total or start > end:
            return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{total}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        return Response(sealed_files.read_range(path, start, end), status_code=206, media_type=media_type, headers=headers)
    except sealed_files.SealedLocked as exc:
        raise HTTPException(status_code=423, detail=sealed_files.LOCKED_DETAIL) from exc
