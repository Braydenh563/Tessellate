"""Source text: L-ui-modernisation-6, "Quiet the Activity count beside
Everything 0 on a new Library" (scratchpad/first-run-472.md row 14: ""Activity
2" beside "Everything 0" on a notebook with nothing in it"). Measured after:
a new notebook's row is "Everything 0" alone; the probe notebook keeps
"Activity 200" beside "Everything 116"."""
from tests._app_js import frontend_text


def _body():
    src = frontend_text("library.js")
    start = src.index("function renderLibraryFilters(")
    return src[start : src.index("\n}\n", start)]


def test_activity_is_empty_while_nothing_is_made():
    body = _body()
    assert "const everything = " in body
    assert 'kind.key === "activity" && !everything' in body
    assert body.index("const everything = ") < body.index("for (const kind of LIBRARY_KINDS)")
