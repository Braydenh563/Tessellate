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


def main() -> None:
    from tessellate.api.app import create_app
    from tessellate.api.lazy_routes import load_all_routes

    corpus = _corpus("--no-docs" not in sys.argv)
    found = []
    app = create_app()
    load_all_routes(app)
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/") or path.startswith(("/docs", "/openapi", "/redoc")):
            continue
        pieces = [re.escape(piece) for piece in re.split(r"\{[^}]*\}", path)]
        if re.search(r"[^\s]{0,80}?".join(pieces).rstrip("/") or "/", corpus):
            continue
        methods = ",".join(sorted(getattr(route, "methods", None) or []))
        found.append((path, methods, getattr(route, "name", "")))
    for path, methods, name in sorted(found):
        print(f"{methods:12} {path}  ({name})")
    print(f"{len(found)} unreferenced routes", file=sys.stderr)


if __name__ == "__main__":
    main()
