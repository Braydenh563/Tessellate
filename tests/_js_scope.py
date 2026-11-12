"""What a frontend script puts in the one shared scope (ranked row 37a).

A classic script's top-level `function`, `let`, `var`, `const` and `class`
are globals every other script can call or overwrite. A script wrapped whole
in one closure (`(() => {` on its first code line, `})();` on its last) keeps
its names to itself and puts on `window` only what its foot lists:

    Object.assign(window, { renderEmbedChoices });

Not named `test_*.py` on purpose, as `_app_js.py` and `_repo_files.py`.
"""

from __future__ import annotations

import re

from tessellate.api.asset_strip import strip_js_comments

_OPEN = re.compile(r"^\(\(\) => \{$")
_CLOSE = re.compile(r"^\}\)\(\);$")
_EXPORT = re.compile(r"^  Object\.assign\(window, \{ ([\w$, ]+) \}\);$", re.M)
_WINDOW_SET = re.compile(r"^  window\.([A-Za-z_$][\w$]*) =", re.M)
_TOP_LEVEL = re.compile(
    r"^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)|^(?:let|var|const|class)\s+([A-Za-z_$][\w$]*)",
    re.M,
)


def is_wrapped(source: str) -> bool:
    """The whole script is one closure: nothing but comments before its opening
    line, nothing after its closing one."""
    lines = [line for line in strip_js_comments(source).split("\n") if line.strip()]
    return bool(lines) and bool(_OPEN.match(lines[0])) and bool(_CLOSE.match(lines[-1]))


def listed(source: str) -> set[str]:
    """The names a wrapped script's `Object.assign(window, {...})` foot lists."""
    if not is_wrapped(source):
        return set()
    return {n.strip() for match in _EXPORT.findall(source) for n in match.split(",")} - {""}


def exported(source: str) -> set[str]:
    """Every name a wrapped script puts on `window`: its listed foot, and a
    namespace object set whole (`window.SketchPad = {...}`)."""
    if not is_wrapped(source):
        return set()
    return listed(source) | set(_WINDOW_SET.findall(source))


def global_names(source: str) -> set[str]:
    """What the script adds to the shared scope: a wrapped script's exports,
    any other script's top-level declarations."""
    if is_wrapped(source):
        return exported(source)
    return {a or b for a, b in _TOP_LEVEL.findall(strip_js_comments(source))}


def template_lines(src: str) -> set[int]:
    """The 0-based lines that begin inside a multi-line template literal: a wrapper
    indents the code, never a string's own text."""
    inside = set()
    stack = []
    i = 0
    line = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            if stack and stack[-1] == "T":
                inside.add(line)
            i += 1
            continue
        top = stack[-1] if stack else None
        if top == "T":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                stack.pop()
            elif c == "$" and src[i + 1 : i + 2] == "{":
                stack.append("B")
                i += 1
            i += 1
            continue
        if c == "/" and src[i + 1 : i + 2] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and src[i + 1 : i + 2] == "*":
            j = src.index("*/", i + 2)
            line += src.count("\n", i, j)
            i = j + 2
            continue
        if c == "/" and src[:i].rstrip()[-1:] in "(,=:[!&|?{};+" or (c == "/" and not src[:i].strip()):
            # a regex literal: its quotes and backticks are not string starts
            j = i + 1
            in_class = False
            while src[j] != "\n" and (in_class or src[j] != "/"):
                if src[j] == "\\":
                    j += 1
                elif src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                j += 1
            i = j + 1
            continue
        if c in "'\"":
            j = i + 1
            while src[j] != c:
                if src[j] == "\\":
                    j += 1
                j += 1
            i = j + 1
            continue
        if c == "`":
            stack.append("T")
        elif c == "{" and top == "B":
            stack.append("B")
        elif c == "}" and top == "B":
            stack.pop()
        i += 1
    return inside


def unwrapped(source: str) -> str:
    """A wrapped script's text as it was before it was wrapped: the closure
    lines off and the two-space indent taken back (not inside a template
    literal, which the wrapper never indented), so a test that slices a
    function by its head and `\n}\n` tail, or runs it in a vm and calls a
    private name, checks the same code. Any other script is returned as it is.
    Only the wrapper changed, so nothing a test asserts is weaker; the closure
    itself is covered by the ratchet. The foot's `Object.assign(window, ...)`
    goes too: unwrapped, every name is a global already."""
    if not is_wrapped(source):
        return source
    lines = source.split("\n")
    first = next(i for i, line in enumerate(lines) if _OPEN.match(line))
    last = max(i for i, line in enumerate(lines) if _CLOSE.match(line))
    inside = template_lines(source)
    body = [
        line if n in inside or not line.startswith("  ") else line[2:]
        for n, line in enumerate(lines)
        if first < n < last
    ]
    body = [
        line for line in body if not re.match(r"Object\.assign\(window, \{ [\w$, ]+ \}\);$", line)
    ]
    return "\n".join([*lines[:first], *body, *lines[last + 1 :]])


_COPIES: dict = {}


def unwrapped_copy(path):
    """The path of a copy of a script as `unwrapped` gives it, for a test that
    hands a node harness the file's path or reads it with `Path.read_text`.
    The copy lives in a temp directory made once per run."""
    import tempfile
    from pathlib import Path

    path = Path(path)
    if path not in _COPIES:
        folder = _COPIES.setdefault("dir", Path(tempfile.mkdtemp(prefix="unwrapped-")))
        copy = folder / path.name
        copy.write_text(unwrapped(path.read_text(encoding="utf-8")), encoding="utf-8")
        _COPIES[path] = copy
    return _COPIES[path]


#: `gcDraw` hands one frame to these, in the order they follow it in graph-canvas.js
#: (L14 split the 855-line function; nothing in them is new).
GC_FRAME_PIECES = (
    "gcDraw",
    "gcDrawEdges",
    "gcCollectNodes",
    "gcAddLandmarkLabels",
    "gcPaintNodes",
    "gcDrawRings",
    "gcLabelAlts",
    "gcLabelItems",
    "gcSeatLabels",
    "gcDrawScorePills",
    "gcFrameEnd",
)


def gc_fns(canvas: str, *names: str) -> str:
    """The text of the named (unwrapped) functions of graph-canvas.js, joined."""
    out = []
    for name in names:
        start = re.search(rf"^function {name}\(", canvas, re.M).start()
        out.append(canvas[start : canvas.index("\n}\n", start) + 2])
    return "\n".join(out)


def gc_frame(canvas: str) -> str:
    """The text of `gcDraw` and the helpers it hands the frame to, for a test that
    asserts a string was drawn somewhere in a frame and not where in the split."""
    return gc_fns(canvas, *GC_FRAME_PIECES)


#: `gcStartWorker` and the pieces of it split out in L14 (the worker's tick and end
#: handlers, the fit on a tick, the `init` message).
GC_WORKER_PIECES = ("gcStartWorker", "gcOnWorkerTick", "gcFitOnTick", "gcOnWorkerEnd", "gcWorkerInit")


def gc_worker(canvas: str) -> str:
    return gc_fns(canvas, *GC_WORKER_PIECES)
