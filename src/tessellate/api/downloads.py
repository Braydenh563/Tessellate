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
