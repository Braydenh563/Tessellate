"""documents.js runs code at its load (`setDocView(docDefaultView())`), so every shared name it
calls there must already be defined by a boot script or by a file loaded before it in the
library bundle. The owner's log, 2026-11-22: "Uncaught ReferenceError: setDocView is not
defined" at documents.js:235, after the idle warm-up fetched documents.js on its own, ahead of
documents-surface.js, which defines it.
"""

from __future__ import annotations

import re

from tessellate.api.asset_strip import strip_js_comments
from tests._app_js import JS_DIR, app_js_files, lazy_modules_source
from tests._js_scope import global_names

#: Names the browser gives every script, and the language's own.
_BUILTINS = {
    "Object", "Array", "Math", "JSON", "String", "Number", "Boolean", "Date", "Promise", "Set", "Map",
    "WeakMap", "WeakSet", "Symbol", "Error", "RegExp", "parseInt", "parseFloat", "isNaN", "setTimeout",
    "clearTimeout", "setInterval", "clearInterval", "requestAnimationFrame", "cancelAnimationFrame",
    "queueMicrotask", "matchMedia", "getComputedStyle", "fetch", "structuredClone", "encodeURIComponent",
    "decodeURIComponent", "requestIdleCallback", "CustomEvent", "Event", "URL", "Blob", "MutationObserver",
    "ResizeObserver", "IntersectionObserver",
}
_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "typeof", "function", "await", "new", "of", "in", "do"}


def _library_order() -> list[str]:
    block = lazy_modules_source()
    body = block[block.index("library: [") :]
    body = body[: body.index("],")]
    return re.findall(r'"/js/([A-Za-z0-9_.-]+\.js)"', body)


_BLOCK_WORDS = ("if", "for", "while", "catch", "switch")


def _runs_now(text: str, at: int) -> bool:
    """A `{` that opens a block run in place (`try`, `else`, `if (...)`), not a function body or literal."""
    head = text[:at].rstrip()
    if re.search(r"(?<![\w$])(try|else|finally)$", head):
        return True
    if not head.endswith(")"):
        return False
    depth, j = 0, len(head) - 1
    while j >= 0:
        depth += {")": 1, "(": -1}.get(head[j], 0)
        if depth == 0:
            break
        j -= 1
    return bool(re.search(r"(?<![\w$.])(" + "|".join(_BLOCK_WORDS) + r")\s*$", head[:j]))


def _calls_at_load(source: str) -> set[str]:
    """Bare names called outside any function body (blocks run in place count), strings blanked first."""
    text = strip_js_comments(source)
    text = re.sub(r"`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", '""', text)
    calls, stack, top = set(), [], []
    for i, ch in enumerate(text):
        if ch == "{":
            stack.append(_runs_now(text, i))
        elif ch == "}" and stack:
            stack.pop()
        top.append(ch if all(stack) or ch == "\n" else " ")
    flat = "".join(top)
    for m in re.finditer(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(", flat):
        name = m.group(1)
        before = flat[max(0, m.start() - 9) : m.start()]
        if name in _KEYWORDS or name in _BUILTINS or before.rstrip().endswith("function"):
            continue
        calls.add(name)
    return calls


def test_every_name_documents_js_calls_at_load_is_defined_before_it() -> None:
    order = _library_order()
    assert "documents.js" in order and "documents-surface.js" in order
    defined: set[str] = set()
    for path in app_js_files():
        defined |= global_names(path.read_text(encoding="utf-8"))
    for name in order[: order.index("documents.js")]:
        defined |= global_names((JS_DIR / name).read_text(encoding="utf-8"))
    own = (JS_DIR / "documents.js").read_text(encoding="utf-8")
    defined |= set(re.findall(r"^(?:async\s+)?function\s+([\w$]+)", own, re.M))
    calls = _calls_at_load(own)
    assert "setDocView" in calls, "the check no longer sees the call that broke (documents.js's view choice at load)"
    missing = sorted(calls - defined)
    assert not missing, f"called at documents.js's load, defined by no file before it: {missing}"


def test_nothing_fetches_documents_js_outside_its_bundle() -> None:
    """The warm-up loads the whole bundle (`ensureModule("library")`), in its order."""
    for path in sorted(JS_DIR.glob("*.js")):
        text = strip_js_comments(path.read_text(encoding="utf-8"))
        assert not re.search(r"lazyScript\(\s*[\"'`]/js/documents\.js", text), path.name
