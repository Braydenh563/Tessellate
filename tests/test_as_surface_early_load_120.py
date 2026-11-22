"""L-documents-120: `asSurface` can run before documents.js has declared `docCmView`.

documents-surface.js loads ahead of documents.js in the Library bundle, and the
selection bar asks for a surface on the first selection after load. A bare read
of a `let` another classic script has not yet declared throws a ReferenceError,
so the read goes through `typeof`, which is safe for a name not yet declared.
"""

from __future__ import annotations

import re

from tests._app_js import documents_text


def _as_surface() -> str:
    text = documents_text()
    start = text.index("function asSurface(box)")
    return text[start : text.index("\n  }\n", start)]


def test_as_surface_reads_the_view_through_typeof() -> None:
    body = _as_surface()
    assert 'typeof docCmView !== "undefined"' in body
    # Every read of the view in the function sits behind that guard.
    bare = [m.start() for m in re.finditer(r"(?<![\w.])docCmView\b", body)]
    guard = body.index('typeof docCmView !== "undefined"')
    assert all(i >= guard for i in bare)
