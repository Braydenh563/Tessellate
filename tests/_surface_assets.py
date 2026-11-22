"""Where a surface's markup lives when it is fetched, not shipped in the page.

Settings' body (`<script type="text/x-surface" data-surface="settings" data-src="/surfaces/settings.html?v=...">`,
L-world-class-760) is a file of its own under `frontend/surfaces/`, fetched when Settings first opens
(settings-body.js). The lints that read the page for ids, classes, `data-help-for` and structure mean the markup
wherever it sits, so `inline_surfaces` puts each fetched surface's text back inside its script, as it was
before the move: conftest applies it whenever a test reads `frontend/index.html`, and `surface_text` is the
direct read for a test that means the file itself.

Not named `test_*.py` on purpose, as `_app_js.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
SURFACES_DIR = FRONTEND_DIR / "surfaces"

#: A surface script that names its file: the opening tag only (the stub's body is empty).
_FETCHED = re.compile(
    r'(<script type="text/x-surface"[^>]*?\sdata-src="(/surfaces/[A-Za-z0-9_.-]+)(?:\?[^"]*)?"[^>]*>)(</script>)'
)


def surface_text(name: str) -> str:
    """The text of `frontend/surfaces/<name>.html`, exactly as on disk."""
    return (SURFACES_DIR / f"{name}.html").read_text(encoding="utf-8")


def inline_surfaces(page: str) -> str:
    """`page` with every fetched surface's markup back inside its script, as one file once held it."""
    return _FETCHED.sub(
        lambda m: (
            m.group(1)
            + (FRONTEND_DIR / m.group(2).lstrip("/")).read_text(encoding="utf-8")
            + m.group(3)
        ),
        page,
    )
