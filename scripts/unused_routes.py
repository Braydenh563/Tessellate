#!/usr/bin/env python3
"""List API routes with no reference in frontend/, the MCP server or docs.

A route counts as referenced when its static path (path parameters match any short text)
appears in frontend/ (JS, HTML), src/tessellate/mcp_server.py, docs/ (not
CODEMAP, which lists every route), README or SECURITY. Run:
    PYTHONPATH=src python scripts/unused_routes.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _corpus(docs: bool = True) -> str:
    parts = []
    for base, globs in (("frontend", ("*.js", "*.html")), ("docs", ("*.md",) if docs else ())):
        for pattern in globs:
            for path in (ROOT / base).rglob(pattern):
                if path.name != "CODEMAP.md":
                    parts.append(path.read_text(errors="ignore"))
    for rel in ("src/tessellate/mcp_server.py", "README.md", "SECURITY.md"):
        parts.append((ROOT / rel).read_text(errors="ignore"))
    return "\n".join(parts)


#: Routes with a caller this text search cannot see, each with where it is.
#: A path built from a variable base (`${base}/page-reads`), a verb
#: (`${verb}`) or a string replace, a URL the server hands out, or a caller
#: outside this repository. Every entry must still be a route
#: (tests/test_lazy_routes.py).
_FILES_OR_MEDIA = "library.js and lightbox-view.js build it on `${base}` (`ocrBase`, /files or /media)"
ALLOWED: dict[str, str] = {
    "/.well-known/oauth-protected-resource/mcp": "OAuth discovery, read by a remote MCP client (RFC 9728)",
    "/oauth/authorize/wait": "the page /oauth/authorize redirects to, and refreshes itself (routes_mcp_oauth.py)",
    "/mcp-oauth/requests/{request_id}/approve": "settings-controls.js builds it as `${verb}`",
    "/mcp-oauth/requests/{request_id}/deny": "settings-controls.js builds it as `${verb}`",
    "/mcp-clients/{client_id}/restore": "settings-controls.js `mcpLinkSet`, `${path}/restore`",
    "/auth/lan-networks/{key}/untrust": "settings-controls.js `path(network, \"untrust\")`",
    "/bookmarks/{bookmark_id}/icon": "the URL in a bookmark's `favicon` field (routes_bookmarks.py)",
    "/conversations/{conversation_id}/truncate/restore": "chat-undo.js, `${id}/truncate/restore`",
    "/documents/pyodide/{name}": "the run sandbox page's Pyodide base URL (run_sandbox.py PYODIDE_PATH)",
    "/export/csv": "settings-panes.js `downloadExport`, `/export/${kind}`",
    "/insights/confirmed/{fact_id}/dismiss": "confirmed-patterns.js, `${at}/dismiss`",
    "/insights/confirmed/{fact_id}/restore": "confirmed-patterns.js, `${at}/restore`",
    "/tidy/{key}/undismiss": "tidy.js `send(\"undismiss\")`",
    "/files/{attachment_id}/pdf-unlock": "lightbox-view.js and library.js, the pdf-info URL with /pdf-unlock",
    "/media/pdf-unlock/{filename}": "lightbox-view.js, the pdf-info URL with /pdf-unlock",
    "/media/{upload_id}/vision-ocr": "lightbox-view.js, the read-text action's `/vision-ocr` on the media URL",
    **{
        f"/{kind}/{{{key}}}/{tail}": _FILES_OR_MEDIA
        for kind, key in (("files", "attachment_id"), ("media", "upload_id"))
        for tail in ("ocr-page-read", "ocr-range-read", "page-reads", "page-reads/{page}", "region-read")
    },
    "/files/{attachment_id}/readings/{source}": _FILES_OR_MEDIA,
}


def unreferenced(app, corpus: str) -> list[tuple[str, str, str]]:  # noqa: ANN001
    """(path, methods, name) of every route the corpus never mentions."""
    from tessellate.api.lazy_routes import flat_routes

    found = []
    for path, route in flat_routes(app):
        if not path.startswith("/") or path.startswith(("/docs", "/openapi", "/redoc")) or path in ALLOWED:
            continue
        pieces = [re.escape(piece) for piece in re.split(r"\{[^}]*\}", path)]
        #: A path parameter is a template expression in the caller, which may hold
        #: spaces (`${window.currentBoardId ?? 0}`), or a bare name.
        if re.search(r"(?:\$\{[^}]{0,80}\}|[^\s]{0,80}?)".join(pieces).rstrip("/") or "/", corpus):
            continue
        methods = ",".join(sorted(getattr(route, "methods", None) or []))
        found.append((path, methods, getattr(route, "name", "")))
    return sorted(set(found))


def main() -> None:
    from tessellate.api.app import create_app

    found = unreferenced(create_app(), _corpus("--no-docs" not in sys.argv))
    for path, methods, name in found:
        print(f"{methods:12} {path}  ({name})")
    print(f"{len(found)} unreferenced routes", file=sys.stderr)


if __name__ == "__main__":
    main()
