"""Nothing in the browser calls a function that does not exist.

This exists because of a real, total outage that every other check in this
suite waved through. An outside change ran a regex over `whiteboard.js` to
move the board's undo history onto the app's stack; the pattern was lazy
across two hundred lines, so it deleted `WB_KIND_INFO` (26 call sites),
`wbItemTransform` (14), `wbBeginTextEdit` (9) and six more functions along
with the two it meant to replace. `wbItemTransform` is what positions every
card on the board, so the whiteboard threw a `ReferenceError` on its first
render and drew nothing at all. `node --check` passed. `ruff` passed. Every
lint in this directory passed. Nothing in `tests/` opens a browser, so the
suite passed too.

A `ReferenceError` is the one class of frontend defect that can be found
without running anything, because the app's files are classic scripts
sharing one global scope (index.html loads them in order, and the surface
bundles are fetched into that same scope later). So the union of every
declaration across `frontend/js/*.js` is the namespace, and a bare `name(`
that resolves nowhere in it is a crash waiting for whoever opens that
screen.

Deliberately narrow, to stay at zero false alarms:

* **Call sites only.** `foo(` counts, a bare mention of `foo` does not,
  except for SCREAMING_SNAKE constants, which are distinctive enough to
  check on sight and are how `WB_KIND_INFO` would have been caught.
* **Bare names only.** `thing.foo(` is a property, and whether it exists is
  a question about an object this file cannot see.
* Declarations are collected from anywhere, not just the top level. A
  function nested three deep still proves the name is not a typo, and
  proving *reachability* is a different, much harder question than the one
  this file answers.

A hit here is real. Fix the call or restore the definition; adding the name
to `KNOWN_GLOBALS` is only right when it genuinely comes from the browser
or from `frontend/vendor/`.
"""
from __future__ import annotations

import re
from pathlib import Path
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

#: JS keywords that are followed by `(` and are not calls.
KEYWORDS = frozenset(
    """
    if else for while switch catch return typeof instanceof new delete void
    do try finally throw function class var let const await async yield in of
    case break continue default this super export import extends get set
    """.split()
)

#: Names that come from the browser, the platform, a worker, or
#: `frontend/vendor/`, rather than from this app's own files. Kept explicit
#: rather than guessed at from a prefix, because the whole value of this
#: check is that an unknown name is treated as a mistake.
KNOWN_GLOBALS = frozenset(
    """
    Array ArrayBuffer AudioContext BigInt MathfieldElement Blob Boolean BroadcastChannel CSS ClipboardItem
    CSSStyleSheet CustomEvent DataView Date DecompressionStream DOMMatrix DOMParser Error EvalError Event MouseEvent
    EventSource File FileReader Float32Array Float64Array Int16Array FormData Function
    InputEvent KeyboardEvent WheelEvent
    Headers Image Infinity Int32Array Intl IntersectionObserver JSON Map Math
    MediaRecorder MutationObserver NaN Notification Number Object Option Path2D
    Performance PerformanceObserver Promise Proxy Range RangeError
    ReadableStream ReferenceError Reflect RegExp Request ResizeObserver Response ScrollTimeline Set
    SpeechSynthesisUtterance String Symbol SyntaxError TextDecoder TextEncoder
    TypeError URIError URL URLSearchParams Uint8Array Uint32Array WeakMap
    WeakRef WeakSet Worker XMLHttpRequest XMLSerializer AbortController
    AbortSignal
    alert atob btoa clearInterval clearTimeout confirm createImageBitmap
    decodeURI decodeURIComponent encodeURI encodeURIComponent fetch
    getComputedStyle importScripts isFinite isNaN matchMedia parseFloat
    parseInt prompt queueMicrotask requestAnimationFrame requestIdleCallback
    cancelAnimationFrame cancelIdleCallback setInterval setTimeout
    structuredClone
    caches console crypto customElements document history indexedDB
    localStorage location navigator performance screen self sessionStorage
    speechSynthesis window
    d3 p5 CodeMirror
    """.split()
)

#: `/` is division after a value and a regular-expression literal otherwise.
#: These are the characters that end a value.
_VALUE_END = frozenset(")]}_$" + "abcdefghijklmnopqrstuvwxyz"
                       + "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
#: …except the keywords that look like identifiers but are not values, so a
#: `/` right after one of them still opens a pattern.
_NOT_A_VALUE = frozenset(
    "return typeof instanceof in of case delete void throw new do else yield await".split()
)


def _strip(source: str) -> str:
    """Comments, string bodies and regex literals out; newlines kept.

    Hand-scanned rather than pattern-matched. The regex version of this
    could not survive a template literal holding an object (`${a ? {b: 1} :
    2}` closes the wrong brace) or an apostrophe ("Couldn't ${label}"), and
    when one of those swallowed a thousand lines of `app.js` the check went
    quiet about exactly the region it was written to watch. A lint that
    fails silently is worse than no lint, so this walks the file.
    """
    out: list[str] = []
    i = 0
    length = len(source)
    # One entry per open template literal, holding the brace depth its
    # backtick was found at. That is what tells the `}` closing an object
    # inside a `${…}` from the one closing the substitution itself.
    templates: list[int] = []
    depth = 0
    last_char = ""
    last_word = ""

    def value(char: str) -> None:
        nonlocal last_char, last_word
        last_char = char
        last_word = ""

    while i < length:
        char = source[i]
        two = source[i : i + 2]

        # Inside a template literal's own text, where nothing else is
        # punctuation: not a quote, not a comment, not a slash. Checked
        # first for exactly that reason.
        if templates and depth == templates[-1]:
            if char == "\\":
                i += 2
                continue
            if two == "${":
                depth += 1
                out.append("${")
                i += 2
                value("{")
                continue
            if char == "`":
                templates.pop()
                out.append('""')
                i += 1
                value('"')
                continue
            out.append("\n" if char == "\n" else "")
            i += 1
            continue
        if templates and char == "}" and depth == templates[-1] + 1:
            depth -= 1
            out.append("}")
            i += 1
            value("}")
            continue

        if two == "//":
            while i < length and source[i] != "\n":
                i += 1
            continue
        if two == "/*":
            end = source.find("*/", i + 2)
            end = length if end == -1 else end + 2
            out.append("\n" * source.count("\n", i, end))
            i = end
            continue
        if char in "\"'":
            quote = char
            i += 1
            while i < length and source[i] != quote and source[i] != "\n":
                i += 2 if source[i] == "\\" else 1
            i += 1
            out.append('""')
            value('"')
            continue
        if char == "`":
            templates.append(depth)
            out.append('""')
            i += 1
            value('"')
            continue
        if char == "/" and (last_char not in _VALUE_END or last_word in _NOT_A_VALUE):
            # A regular-expression literal. Its body is skipped for the same
            # reason a string's is: `/(function|class)/` declares nothing and
            # `/foo(/` calls nothing.
            i += 1
            in_class = False
            while i < length and source[i] != "\n":
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == "[":
                    in_class = True
                elif source[i] == "]":
                    in_class = False
                elif source[i] == "/" and not in_class:
                    i += 1
                    break
                i += 1
            while i < length and source[i].isalpha():  # the flags
                i += 1
            out.append('""')
            value('"')
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif source[i : i + 3] == "...":
            # Spread and rest, blanked so the name after it is bare. Without
            # this, `...docCmKeymap(CM)` reads as a property access and a
            # function called only that way looks unused to the scan below,
            # which is how three of this app's largest keymaps first appeared
            # to be dead code.
            out.append("   ")
            i += 3
            last_char = " "
            last_word = ""
            continue
        out.append(char)
        if not char.isspace():
            last_char = char
            last_word = last_word + char if (char.isalnum() or char in "_$") else ""
        i += 1
    return "".join(out)


#: Every way a name enters scope. Nested or not: this file asks whether a
#: name exists at all, never where.
DECLARATIONS = (
    re.compile(r"\b(?:function|class)\s*\*?\s*([A-Za-z_$][\w$]*)"),
    re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)"),
    # Destructuring and the comma-separated tails of the above:
    # `const {a, b} = x`, `let [c, d] = y`, `var e, f`.
    re.compile(r"[,{[]\s*(?:\.\.\.)?\s*([A-Za-z_$][\w$]*)\s*(?=[,}\]:=)])"),
    # Parameters, of both function shapes, plus `catch (err)`.
    re.compile(r"\(\s*(?:\.\.\.)?\s*([A-Za-z_$][\w$]*)\s*(?=[,)=])"),
    re.compile(r",\s*(?:\.\.\.)?\s*([A-Za-z_$][\w$]*)\s*(?=[,)=])"),
    # `name =>`, the single-parameter arrow with no brackets.
    re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=>"),
    # `window.foo = …`: an assignment is a definition for scripts that share
    # the global object, which is how the surfaces reach each other here.
    re.compile(r"\b(?:window|globalThis)\.([A-Za-z_$][\w$]*)\s*="),
    # Methods and accessors, in an object literal or a class body: `foo() {`,
    # `get bar() {`, `static baz() {`. A class body's previous member ends in
    # `}` or `;`, which is why those are in the leading set.
    re.compile(
        r"(?:^|[,{};])\s*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?\*?\s*"
        r"([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*\{"
    ),
    # Renamed destructuring: `const { payload: toPayload } = …`.
    #
    # This also matches the value half of a plain object literal (`{a: b}`
    # counts `b` as declared), which cannot be told apart by a per-line
    # pattern. The cost is that this check goes slightly *quieter*, never
    # louder: it can only ever forgive a name, never invent a hit. That is
    # the right direction for a lint whose findings are meant to be real.
    re.compile(r":\s*([A-Za-z_$][\w$]*)\s*(?=[,}])"),
    # `foo: function`, `foo: (…) =>`, and any `name = function`.
    re.compile(r"([A-Za-z_$][\w$]*)\s*[:=]\s*(?:async\s+)?function\b"),
)

CALL = re.compile(r"(?<![\w$.?])([A-Za-z_$][\w$]*)\s*\(")
SCREAMING = re.compile(r"(?<![\w$.?])([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b")


def _sources() -> dict[str, str]:
    return {
        path.name: _strip(path.read_text(encoding="utf-8"))
        for path in sorted((FRONTEND / "js").glob("*.js"))
    }


def _declared(sources: dict[str, str]) -> set[str]:
    names: set[str] = set()
    for text in sources.values():
        for pattern in DECLARATIONS:
            names.update(pattern.findall(text))
    return names


def _report(missing: dict[str, list[str]]) -> str:
    return "\n".join(
        f"  {name}: {len(where)} site(s), first at {where[0]}"
        for name, where in sorted(missing.items())
    )


def _undeclared(pattern: re.Pattern[str], extra_known: frozenset[str]) -> dict[str, list[str]]:
    sources = _sources()
    known = _declared(sources) | KNOWN_GLOBALS | extra_known
    missing: dict[str, list[str]] = {}
    for name, text in sources.items():
        for number, line in enumerate(text.splitlines(), 1):
            for used in pattern.findall(line):
                if used not in known:
                    missing.setdefault(used, []).append(f"{name}:{number}")
    return missing


def test_the_scanner_still_sees_the_whole_file():
    """A stripper that loses its place goes quiet rather than loud, so the
    two things that would hide a real hit are checked directly: the line
    count has to survive, and a declaration late in the largest file has to
    still be visible after stripping."""
    raw = app_js_text()
    stripped = _strip(raw)
    assert stripped.count("\n") == raw.count("\n")
    assert "function round2" in stripped  # app.js, past a thousand templates
    # A name that exists only inside a string or a comment is not a
    # declaration, and must not be counted as one.
    assert "notADeclaration" not in _strip(
        'const s = "function notADeclaration() {}"; // function notADeclaration\n'
    )


def test_every_function_the_browser_calls_exists():
    missing = _undeclared(CALL, KEYWORDS)
    assert not missing, (
        "a call to a function declared nowhere in frontend/: on the surface "
        "that runs this line the browser raises a ReferenceError and the "
        "screen stops. Restore the definition or fix the call; only add a "
        "name to KNOWN_GLOBALS if it really comes from the browser or "
        "frontend/vendor/.\n" + _report(missing)
    )


#: The files that share the page's one global scope. `graph-worker.js` runs
#: in a `Worker`, which has a scope of its own, so a name it declares cannot
#: collide with the page's.
WORKER_FILES = frozenset({"graph-worker.js", "harper-worker.js", "translate-worker.js", "sw.js"})

#: A top-level declaration, which is what the global scope actually holds.
#: Not the nested ones `DECLARATIONS` collects: a `const` inside a function
#: is that function's, and two of those are not a collision.
TOP_LEVEL = re.compile(
    r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)|^(?:const|let|var)\s+([A-Za-z_$][\w$]*)",
    re.M,
)


def _top_level_declarations() -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for path in sorted((FRONTEND / "js").glob("*.js")):
        if path.name in WORKER_FILES:
            continue
        text = _strip(path.read_text(encoding="utf-8"))
        for match in TOP_LEVEL.finditer(text):
            name = match.group(1) or match.group(2)
            line = text.count("\n", 0, match.start()) + 1
            owners.setdefault(name, []).append(f"{path.name}:{line}")
    return owners


def test_no_top_level_name_is_declared_twice():
    """Two declarations of one name, and the later script silently wins.

    This is the tax on the app's shape: `index.html` loads six classic
    scripts into one global scope, so `function foo()` in app.js and
    `function foo()` in dashboard.js are the same binding, and whichever
    parses last is the one that runs. Nothing warns. `node --check` is
    per-file and cannot see it, and the only symptom is that a feature
    behaves like a different feature.

    It found one on the day it was written: `renderOnThisDayWidget` was
    declared twice in `dashboard.js`, once fetching `/insights/on-this-day`
    from the server and once building the list from `allEntries`. The second
    won, so the first was dead and so was the endpoint it called.

    A `function` redeclaration is legal JavaScript and a `const` one is a
    SyntaxError only within a single file, which is why the same-file case
    has to be checked here too rather than left to the parser.
    """
    clashes = {
        name: where for name, where in _top_level_declarations().items() if len(where) > 1
    }
    assert not clashes, (
        "a top-level name declared more than once. Every file in frontend/ "
        "shares one global scope, so the later declaration silently replaces "
        "the earlier one and the code under it becomes unreachable. Rename "
        "one, or delete the copy that lost:\n"
        + "\n".join(f"  {name}: {', '.join(where)}" for name, where in sorted(clashes.items()))
    )


def test_every_shared_constant_exists():
    """The same question for SCREAMING_SNAKE names, which are never called
    and so are invisible to the check above. `WB_KIND_INFO`, the table undo
    and redo both read, is one of these."""
    missing = _undeclared(SCREAMING, frozenset())
    assert not missing, (
        "a shared constant read in frontend/ but declared nowhere:\n" + _report(missing)
    )
