"""No CodeMirror plugin requests a measure from inside a measure (INBOX 1492).

CodeMirror runs `read` then `write` in a loop and sets `geometryChanged`,
`viewportChanged` and `heightChanged` on the updates that loop produces. A
plugin whose `update` calls `requestMeasure` on one of those flags adds a pass
to the loop it is already in, so a document whose line heights take four
passes to settle reaches "Measure loop restarted more than 5 times". The
class: a plugin asks for its measure on a document, selection or focus change
(outside the loop) directly, and on a geometry flag only through
`docMeasureNextFrame`, which coalesces to one request per frame. A `read` or
`write` of a plugin never requests one at all.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR

IN_LOOP_FLAGS = ("geometryChanged", "viewportChanged", "heightChanged")


def _blank_noise(text: str) -> str:
    """Comments and string contents to spaces (same length), so braces count."""
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        two = text[i : i + 2]
        if two == "//":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r"[^\n]", " ", text[i:j]))
            i = j
        elif c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(c + re.sub(r"[^\n]", " ", text[i + 1 : j - 1]) + c)
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    raise AssertionError("unbalanced")


def _plugin_methods():
    """(file, method name, body) for update/read/write inside each fromClass."""
    for path in sorted(JS_DIR.glob("*.js")):
        raw = path.read_text(encoding="utf-8")
        if "ViewPlugin.fromClass(" not in raw:
            continue
        text = _blank_noise(raw)
        for m in re.finditer(r"ViewPlugin\.fromClass\(", text):
            end = _balanced(text, m.end() - 1, "(", ")")
            cls = text[m.end() : end]
            for meth in re.finditer(r"\n\s+(update|read|write)\s*\([^)]*\)\s*\{", cls):
                close = _balanced(cls, meth.end() - 1, "{", "}")
                yield path.name, meth.group(1), cls[meth.end() : close]


def test_the_scan_finds_the_plugins():
    names = {(f, k) for f, k, _ in _plugin_methods()}
    assert any(k == "update" for _, k in names)
    assert len({f for f, _ in names}) >= 3


def _requests_on_loop_flag(body: str) -> list[str]:
    """Flags in an `if` condition whose branch calls requestMeasure directly."""
    hits = []
    starts = [m for m in re.finditer(r"\bif\s*\(", body)]
    for i, m in enumerate(starts):
        close = _balanced(body, m.end() - 1, "(", ")")
        cond = body[m.end() : close]
        branch_end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        branch = body[close + 1 : branch_end]
        if "requestMeasure" in branch:
            hits += [flag for flag in IN_LOOP_FLAGS if flag in cond]
    # An unconditional request in update() runs on the loop's updates too.
    if not starts and "requestMeasure" in body:
        hits.append("(unconditional)")
    return hits


def test_no_plugin_update_requests_a_measure_on_a_loop_flag():
    bad = [
        f"{f}: update() calls requestMeasure on {flag}"
        for f, kind, body in _plugin_methods()
        if kind == "update"
        for flag in _requests_on_loop_flag(body)
    ]
    assert not bad, "\n".join(bad) + "\nuse docMeasureNextFrame(plugin, view, spec) for those flags"


def test_the_lint_sees_the_old_shape():
    old = "if (u.docChanged || u.geometryChanged) { u.view.requestMeasure(this.m); }"
    assert _requests_on_loop_flag(old) == ["geometryChanged"]
    ok = "if (u.docChanged) u.view.requestMeasure(m); else if (u.geometryChanged) docMeasureNextFrame(this, v, m);"
    assert _requests_on_loop_flag(ok) == []


def test_no_plugin_read_or_write_requests_a_measure():
    bad = [f"{f}: {kind}() calls requestMeasure" for f, kind, body in _plugin_methods() if kind in ("read", "write") and "requestMeasure" in body]
    assert not bad, "\n".join(bad)


def test_the_helper_is_one_request_per_frame():
    src = "\n".join(p.read_text(encoding="utf-8") for p in JS_DIR.glob("documents*.js"))
    m = re.search(r"function docMeasureNextFrame\([^)]*\) \{", src)
    assert m, "docMeasureNextFrame is missing"
    body = src[m.end() : m.end() + 600]
    assert "requestAnimationFrame" in body and "requestMeasure" in body
    assert "measureFrame" in body, "the pending frame must be remembered so a second call is a no-op"
