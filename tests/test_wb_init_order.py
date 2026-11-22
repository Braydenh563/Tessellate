"""A boards file never reaches, while it loads, a name a later boards file declares.

The `boards` bundle (lazy-entries.js) runs its files one after another, and a
board restored with the page is opened between them: `openWhiteboardBoard`
(whiteboard.js) is there before whiteboard-format.js has run. The owner's report
on #222 was that path: `initWhiteboard` ran, reached `wbFmtState` (declared in
whiteboard-format.js), threw, and left the board with no handler wired, stuck on
one tool. Two halves hold it:

- `initWhiteboard` waits for the whole bundle before it wires anything;
- no file's load-time code (outside every function body) names a top-level
  declaration or a `window` export of a file later in the bundle, unless behind
  `typeof`.

`scratchpad/ui-sweeps/wbfmtrace.js` drives the restored-board path in the app.
"""

from __future__ import annotations

import re

from tests import test_lazy_boards_split as split
from tests._js_functions import blank, function_spans

JS = split.JS
_DECL = re.compile(
    r"^(?:const|let|var|class|function\*?|async\s+function)\s+([A-Za-z_$][\w$]*)", re.M
)
_IDENT = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)")


def _declared(code: str) -> set[str]:
    return set(_DECL.findall(code)) | _exports(code)


def _load_time(code: str) -> str:
    """`code` with every function body blanked, except a file's own `(() => {...})();` wrapper."""
    spans = function_spans(code)
    wrapper = None
    head = re.match(r"\s*\(\s*\(\s*\)\s*=>\s*\{", code)
    if head:
        wrapper = head.end() - 1
    out = list(code)
    for start, end, _name in spans:
        if start == wrapper:
            continue
        for i in range(_params_start(code, start), end):
            if out[i] != "\n" and i != start:
                out[i] = " "
    return _blank_expression_arrows("".join(out))


def _params_start(code: str, brace: int) -> int:
    """Where a function's parameter list opens: its defaults run at the call too."""
    j = brace - 1
    while j >= 0 and code[j].isspace():
        j -= 1
    if code[j - 1 : j + 1] == "=>":
        j -= 2
        while j >= 0 and code[j].isspace():
            j -= 1
    if code[j] != ")":
        return brace + 1
    level = 0
    while j >= 0:
        level += {")": 1, "(": -1}.get(code[j], 0)
        if level == 0:
            return j + 1
        j -= 1
    return brace + 1


def _exports(code: str) -> set[str]:
    """The top-level keys of each `Object.assign(window, { ... })`."""
    names = set()
    for m in re.finditer(r"Object\.assign\(\s*window\s*,\s*\{", code):
        depth, i, top = 1, m.end(), []
        while i < len(code) and depth:
            c = code[i]
            depth += {"{": 1, "}": -1}.get(c, 0)
            top.append(c if depth == 1 else " ")
            i += 1
        names.update(re.findall(r"([A-Za-z_$][\w$]*)\s*(?=[:,]|$)", "".join(top[:-1]).strip()))
    return names


def _blank_expression_arrows(code: str) -> str:
    """Blank each `=> expr` body (no brace): it runs when called, not when the file loads."""
    out = list(code)
    for m in re.finditer(r"=>(?!\s*\{)\s*", code):
        depth, i = 0, m.end()
        while i < len(code):
            c = code[i]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if depth < 0:
                    break
            elif depth == 0 and c in ",;":
                break
            if c != "\n":
                out[i] = " "
            i += 1
    return "".join(out)


def early_reaches(files: dict[str, str]) -> list[str]:
    """`file: name` for each load-time use of a name only a later file declares; `files` in load order."""
    codes = {name: blank(text) for name, text in files.items()}
    order = list(codes)
    found = []
    for i, name in enumerate(order):
        earlier = set().union(*(_declared(codes[f]) for f in order[: i + 1]))
        later = set().union(*(_declared(codes[f]) for f in order[i + 1 :])) - earlier
        load = _load_time(codes[name])
        for m in _IDENT.finditer(load):
            ident = m.group(1)
            if ident in later and not re.search(
                r"typeof\s*$", load[max(0, m.start() - 12) : m.start()]
            ):
                found.append(f"{name}: {ident}")
    return sorted(set(found))


def _bundle() -> dict[str, str]:
    return {
        f: (JS / f).read_text(encoding="utf-8") for f in split._boards_only() if f.endswith(".js")
    }


def test_no_boards_file_reaches_a_later_file_while_loading():
    bundle = _bundle()
    assert len(bundle) > 60, "the scan must read the whole boards bundle"
    assert early_reaches(bundle) == []


def test_init_waits_for_the_whole_bundle():
    code = (JS / "whiteboard.js").read_text(encoding="utf-8")
    start = code.index("async function initWhiteboard(")
    body = code[start : code.index("wbInitPan(", start)]
    assert 'await ensureModule("boards")' in body, (
        "initWhiteboard must wait for the bundle before it wires the board"
    )


def test_opening_a_board_waits_for_the_whole_bundle_first():
    code = (JS / "whiteboard.js").read_text(encoding="utf-8")
    start = code.index("async function openWhiteboardBoard(")
    body = code[start : code.index("wbShowCanvasView();", start)]
    assert 'await ensureModule("boards")' in body, (
        "a restored board opens mid-bundle: its timers and Library side are in later files"
    )


def test_the_detector_sees_an_early_reach_and_not_its_guard():
    files = {
        "a.js": "const early = laterState.x;\nconst ok = typeof laterState;\nfunction f() { return laterState; }\n",
        "b.js": "(() => { function wbInitB() {} const inside = laterThing; Object.assign(window, { wbInitB }); })();\n",
        "c.js": "const laterState = {};\n(() => { function laterThing() {} Object.assign(window, { laterThing }); })();\n",
    }
    assert early_reaches(files) == ["a.js: laterState", "b.js: laterThing"]
