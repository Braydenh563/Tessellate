"""Two lazy-load faults found on 2026-11-01 (INBOX 1530): a board restored with its
Library side open drew tiles before whiteboard-templates.js ran (`wbThumbSvg is not
defined`), and a card file that loaded without defining `entryItem` made the notes
list ask for its own draw forever."""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_board_library_waits_for_its_bundle_before_drawing_tiles():
    lib = (JS / "whiteboard-library.js").read_text(encoding="utf-8")
    body = lib[lib.index("async function wbLoadLibrary"):].split("\n}\n")[0]
    assert body.index('await ensureModule("boards");') < body.index("wbRenderLibrary();")


def test_a_card_file_without_its_name_is_a_failure_not_a_redraw():
    notes = (JS / "notes-list.js").read_text(encoding="utf-8")
    waiting = notes[notes.index("renderEntries.waiting ||="):][:600]
    assert "if (!ok || !window.entryItem)" in waiting
    phone = (JS / "phone-shell.js").read_text(encoding="utf-8")
    for call in ("openNotePage(entry, returnFocus)", "refreshNotePage(ids)"):
        assert f"ok && window.entryItem ? {call}" in phone


# --- the class: an earlier bundle file's async continuation reaching a later file's name ------------
#
# A bundle's files run in order, and an `await` in the middle of one can return
# before the next file has run. `wbLoadLibrary` (whiteboard-library.js) fetched
# the library, then drew tiles with `wbThumbSvg` from whiteboard-templates.js,
# later in the bundle: a board restored with its Library side open got there
# while the bundle was still loading. `test_lazy_bundle_calls.py` reads names
# across bundles; this reads the order inside one.
#
# The rule: an async function that can run while its bundle loads (reachable
# from a statement a file runs at its top level, through calls that run when
# the caller does, before or after its awaits, not callbacks) may not, after
# its first await, read a name only a LATER file of the bundle defines, unless
# `await ensureModule("<bundle>")` or a `typeof` test comes first in the function.
#
# What runs with a block (lzo16-1102): a call after an await still runs while
# the bundle loads (that is the 1530 fault itself), so the closure follows it.
# A callback does not run with its block: an arrow (its body on the same line
# or the next), a `function` expression, and a method (`mousedown(event) {` in
# an object or a class), which runs when whatever holds it calls it. A file
# wrapped in one closure (`(() => {`, documents-embeds.js) is read as if it
# were not wrapped: its body runs at load and its functions are in the closure.

import re  # noqa: E402

from tests import test_lazy_bundle_calls as _bundles  # noqa: E402

_CALL = re.compile(r"(?<![\w$.])(?<!function )(?<!function\* )([A-Za-z_$][\w$]*)\s*\(")
_DECLARATION = re.compile(r"^(?:async )?function\*? ([A-Za-z_$][\w$]*)", re.M)
_IDENT = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)")
_COMMENT = re.compile(r"(?m)^\s*//.*$|(?<=\s)//\s.*$")


_WRAP_OPEN = re.compile(r"^\((?:async )?(?:\(\) =>|function\b[^(]*\(\))\s*\{\n", re.M)


def _unwrapped(source: str) -> str:
    """A file (or a run of it) wrapped in one immediately run closure, `(() => {` to `})();`
    at column zero, read with the wrapper gone and its body dedented: the body runs at load."""
    out, last = [], 0
    for m in _WRAP_OPEN.finditer(source):
        if m.start() < last:
            continue
        end = source.find("\n})();", m.end() - 1)
        if end < 0:
            continue
        inner = source[m.end() : end + 1]
        lines = inner.split("\n")
        if any(ln and not ln.startswith("  ") for ln in lines):
            continue
        out += [source[last : m.start()], "\n", "\n".join(ln[2:] for ln in lines)]
        last = end + len("\n})();")
    out.append(source[last:])
    return "".join(out)


def _split_functions(source: str) -> tuple[dict[str, str], str]:
    """The column-zero functions of a file by name, and what is left of the file."""
    source = _unwrapped(source)
    functions, pieces = {}, []
    for m in _DECLARATION.finditer(source):
        end = source.find("\n}\n", m.start())
        end = len(source) if end < 0 else end + 3
        functions[m.group(1)] = source[m.start() : end]
        pieces.append((m.start(), end))
    rest, last = [], 0
    for start, end in pieces:
        rest.append(source[last:start])
        last = end
    rest.append(source[last:])
    return functions, "".join(rest)


_METHOD = re.compile(r"\s*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?\*?([A-Za-z_$][\w$]*)\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*\{\s*$")
_NOT_A_METHOD = {"if", "for", "while", "switch", "catch", "with", "function", "return", "await", "typeof"}


#: A callback that runs on its own soon after its block, with nothing clicked: a timer, a
#: frame, an idle slot, a microtask, a promise's continuation. It can run between two files
#: of a bundle, so the closure follows it, and its body counts as after an await.
_SOON = re.compile(
    r"(?:\b(?:setTimeout|setInterval|requestAnimationFrame|requestIdleCallback|queueMicrotask)|\.(?:then|catch|finally))"
    r"\(\s*(?:async\s+)?(?:function\b|\([^()]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
)


def _opener_at(line: str) -> int:
    """Where the first callback of a line opens: its `=>` or its `function`, or -1."""
    at = [m.start() for m in (re.search(r"=>", line), re.search(r"\bfunction\b", line)) if m]
    return min(at) if at else -1


def _opens_soon(line: str) -> bool:
    """The line's first callback is one `_SOON` names."""
    at = _opener_at(line)
    return at >= 0 and any(m.start() < at < m.end() for m in _SOON.finditer(line))


def _opens_a_callback(line: str, depth: int) -> bool:
    if _opens_soon(line):
        return False
    if "=>" in line:
        return True
    method = _METHOD.match(line)
    if method and method.group(1) not in _NOT_A_METHOD:
        return True
    return re.search(r"\bfunction\b", line) is not None and (depth > 0 or not re.match(r"\s*(?:async )?function ", line))


def _runs_with_the_block(text: str) -> list[str]:
    """The lines of `text` that run when `text` does: nothing inside a callback or a nested
    function, and nothing after the `=>` of a one-line arrow."""
    stack: list[tuple[int, bool]] = []
    kept = []
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("//"):
            kept.append("")
            continue
        depth = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= depth:
            stack.pop()
        cut = re.split(r"=>|\bfunction\b", line, maxsplit=1)[0] if _opens_a_callback(line, depth) else line
        kept.append("" if any(inside for _, inside in stack) else cut)
        if re.search(r"(?:[{(\[]|=>)\s*$", line.rstrip()):
            stack.append((depth, _opens_a_callback(line, depth)))
    return kept


def _reachable_at_load(functions: dict[str, str], rest: str) -> set[str]:
    """Functions a file's top level starts, and those they call."""
    top = _runs_with_the_block(rest)
    pending = [m.group(1) for ln in top for m in _CALL.finditer(ln) if m.group(1) in functions]
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for ln in _runs_with_the_block(functions[name]):
            pending += [m.group(1) for m in _CALL.finditer(ln) if m.group(1) in functions and m.group(1) != name]
    return seen


def _late_name_in(text: str, late: dict[str, str], every: dict[str, str], seen: set[str]) -> tuple[str, str] | None:
    """A later-file name `text` reads, directly or through the functions of this bundle it calls
    (only what runs when each is called: a callback it hands out is not followed)."""
    for m in _IDENT.finditer(text):
        name = m.group(1)
        if name in late:
            return name, late[name]
        if name in every and name not in seen and re.match(r"\s*\(", text[m.end() :]):
            seen.add(name)
            hit = _late_name_in("\n".join(_runs_with_the_block(_COMMENT.sub("", every[name]))), late, every, seen)
            if hit:
                return hit
    return None


def _first_wait(body: str) -> int:
    """Where `body` first lets other work run: its first await, or its first soon callback."""
    at = [m.start() for m in [re.search(r"\bawait ", body)] if m]
    offset = 0
    for line in body.split("\n"):
        if _opens_soon(line):
            at.append(offset)
            break
        offset += len(line) + 1
    return min(at) if at else -1


def _first_late_read(body: str, late: dict[str, str], every: dict[str, str], bundle: str) -> tuple[str, str] | None:
    """The first later-file name read after the function's first await finishes (or inside its
    first soon callback, and after), unless guarded by `await ensureModule("<bundle>")` or a
    `typeof` test earlier in the function."""
    body = _COMMENT.sub("", body)
    wait = _first_wait(body)
    if wait < 0:
        return None
    #: After an await, from the next line; a soon callback's body starts on its own line.
    soon = not body.startswith("await ", wait)
    start = body.rfind("\n", 0, wait) if soon else body.find("\n", wait)
    start = len(body) if start < 0 and not soon else max(start, 0)
    lines = _runs_with_the_block(body)[body.count("\n", 0, start) + (0 if soon and start == 0 else 1) :]
    before = body[:start]
    for line in lines:
        if f'ensureModule("{bundle}")' in before + line or re.search(r"typeof\s+\w+", before + line):
            return None
        hit = _late_name_in(line, late, every, {m.group(1) for m in [re.match(r"\s*(?:async )?function (\w+)", body)] if m})
        if hit:
            return hit
        before += "\n" + line
    return None


def _top_level_names(source: str) -> set[str]:
    """The globals a file binds: column-zero declarations, and a wrapped file's window exports."""
    names = set(re.findall(r"^(?:async )?function\*? ([A-Za-z_$][\w$]*)", source, re.M))
    names |= set(re.findall(r"^(?:const|let|class) ([A-Za-z_$][\w$]*)", source, re.M))
    return names | _bundles._window_exports(source)


def in_bundle_order_gaps(bundles: dict[str, list[tuple[str, str]]], always: set[str]) -> list[str]:
    """`bundles`: bundle to its `(file name, source)` in load order. `always`: names that are there
    before any bundle loads (boot files, stand-ins)."""
    gaps = []
    for bundle, files in bundles.items():
        split = [_split_functions(source) for _, source in files]
        bound = [_top_level_names(source) for _, source in files]
        every = {name: body for functions, _ in split for name, body in functions.items()}
        #: A function started from file k's top level runs no earlier than file k: the names of
        #: files up to k are there, so "later" is counted from its own file or k, whichever is later.
        started: dict[str, int] = {}
        for k, (_, rest) in enumerate(split):
            for name in _reachable_at_load(every, rest):
                started.setdefault(name, k)

        def late_after(index: int) -> dict[str, str]:
            early = set().union(*bound[: index + 1])
            return {n: files[j][0] for j in range(index + 1, len(files)) for n in bound[j] if n not in early and n not in always}

        for index, (file_name, _) in enumerate(files):
            for name, body in split[index][0].items():
                hit = _first_late_read(body, late_after(max(index, started[name])), every, bundle) if name in started else None
                if hit:
                    gaps.append(f"{file_name}: {name} reads {hit[0]} (defined in {hit[1]}, later in the {bundle} bundle) after an await, with no ensureModule(\"{bundle}\") first")
            hit = _first_late_read(split[index][1], late_after(index), every, bundle)
            if hit:
                gaps.append(f"{file_name}: its top level reads {hit[0]} (defined in {hit[1]}, later in the {bundle} bundle) in a soon callback, with no ensureModule(\"{bundle}\") first")
    return gaps


def _real_bundles() -> tuple[dict[str, list[tuple[str, str]]], set[str]]:
    lazy = _bundles._lazy_files()
    bundles = {
        bundle: [(f, (_bundles.FRONTEND / "js" / f).read_text(encoding="utf-8")) for f in files if f.endswith(".js") and (_bundles.FRONTEND / "js" / f).exists()]
        for bundle, files in lazy.items()
    }
    always = set().union(*_bundles._entry_points().values())
    for name in _bundles._boot_scripts():
        always |= _bundles._defined_any_form(_bundles.FRONTEND / "js" / name)
    return bundles, always


#: Reached at load but held by a value only the later file makes; each says what holds it.
ONLY_ONCE_THE_LATER_FILE_RAN = {
}


def test_no_bundle_file_reads_a_later_file_after_an_await_without_the_bundle():
    bundles, always = _real_bundles()
    gaps = in_bundle_order_gaps(bundles, always)
    assert not [g for g in gaps if g.split(" reads ")[0] not in ONLY_ONCE_THE_LATER_FILE_RAN]
    held = {g.split(" reads ")[0] for g in gaps}
    assert set(ONLY_ONCE_THE_LATER_FILE_RAN) <= held, "an entry the lint no longer flags is stale: remove it"


def test_only_atlas_life_gives_a_figure_its_tail():
    """The one allowed entry above holds while `.atlasTail =` is written in atlas-life.js alone."""
    writers = [p.name for p in sorted(JS.glob("*.js")) if re.search(r"\.atlasTail\s*=[^=]", p.read_text(encoding="utf-8"))]
    assert writers == ["atlas-life.js"]


_EARLY = "async function loadTiles() {\n  const lib = await apiJson(\"/lib\");\n  drawTiles(lib);\n}\n"
_LATE = "function drawTiles(lib) {\n  return thumb(lib);\n}\nfunction thumb(x) {\n  return x;\n}\n"


def test_the_lint_sees_the_board_library_fault_and_not_its_fix():
    """The shape of 1530: the early file starts `loadTiles` at its top level, awaits, then calls a function the late file defines."""
    start = "loadTiles();\n"
    fault = {"library": [("early.js", _EARLY + start), ("late.js", _LATE)]}
    assert len(in_bundle_order_gaps(fault, set())) == 1
    fixed = {"library": [("early.js", _EARLY.replace("  drawTiles", "  await ensureModule(\"library\");\n  drawTiles") + start), ("late.js", _LATE)]}
    assert not in_bundle_order_gaps(fixed, set())
    never_started = {"library": [("early.js", _EARLY), ("late.js", _LATE)]}
    assert not in_bundle_order_gaps(never_started, set()), "a function nothing starts during the load cannot run early"
    boot_has_it = {"library": [("early.js", _EARLY + start), ("late.js", _LATE)]}
    assert not in_bundle_order_gaps(boot_has_it, {"drawTiles", "thumb"}), "a name the boot files define is there already"
    in_a_callback = {"library": [("early.js", _EARLY + "button.onclick = () => loadTiles();\n"), ("late.js", _LATE)]}
    assert not in_bundle_order_gaps(in_a_callback, set()), "a callback runs when it is clicked, not when the file loads"


def _wrapped(source: str) -> str:
    return "(() => {\n" + "".join(f"  {ln}\n" if ln else "\n" for ln in source.rstrip("\n").split("\n")) + "})();\n"


def test_the_closure_follows_a_call_after_an_await_and_not_a_callback():
    """lzo16-1102. A call after an await in a function started at load still runs while the
    bundle loads, so it is followed. The 16 the looser closure flagged (`saveDocument`,
    `fetchWhiteboardState`, `wbLoadShapeSets`, ...) were all reached through two callbacks
    read as running with their block: a click arrow whose body is on the next line
    (`docProseGroupList`) and a `mousedown(event) {` method (`docLivePlugin`)."""
    start = 'async function boot() {\n  await apiJson("/me");\n  loadTiles();\n}\nboot();\n'
    after_await = {"library": [("early.js", _EARLY + start), ("late.js", _LATE)]}
    assert any(g.startswith("early.js: loadTiles reads drawTiles") for g in in_bundle_order_gaps(after_await, set())), "a call after an await runs while the bundle loads"
    next_line = 'function row(li) {\n  li.addEventListener("click", (event) =>\n    loadTiles(event));\n}\nrow(li);\n'
    assert not in_bundle_order_gaps({"library": [("early.js", _EARLY + next_line), ("late.js", _LATE)]}, set()), "an arrow's body on the next line is still the callback"
    method = "function plugin() {\n  return {\n    eventHandlers: {\n      mousedown(event) {\n        loadTiles(event);\n      },\n    },\n  };\n}\nplugin();\n"
    assert not in_bundle_order_gaps({"library": [("early.js", _EARLY + method), ("late.js", _LATE)]}, set()), "a method runs when its holder calls it"
    klass = "function widget() {\n  return class extends Widget {\n    toDOM() {\n      loadTiles(this);\n    }\n  };\n}\nwidget();\n"
    assert not in_bundle_order_gaps({"library": [("early.js", _EARLY + klass), ("late.js", _LATE)]}, set()), "a class method too"
    called = "function plugin() {\n  if (ready(x)) {\n    loadTiles(x);\n  }\n}\nplugin();\n"
    assert len(in_bundle_order_gaps({"library": [("early.js", _EARLY + called), ("late.js", _LATE)]}, set())) == 1, "an `if (...) {` block is not a method"


def test_a_wrapped_file_is_read_inside_its_closure():
    """documents-embeds.js and five more are one `(() => {` closure: their functions are in
    the closure, their body runs at load, and their window exports are names a later file binds."""
    early = _wrapped(_EARLY + "loadTiles();\nObject.assign(window, { loadTiles });\n")
    assert len(in_bundle_order_gaps({"library": [("early.js", early), ("late.js", _LATE)]}, set())) == 1
    late = _wrapped(_LATE + "Object.assign(window, { drawTiles });\n")
    assert len(in_bundle_order_gaps({"library": [("early.js", _EARLY + "loadTiles();\n"), ("late.js", late)]}, set())) == 1


def test_a_soon_callback_runs_between_two_files():
    """A timer, a frame or a promise's continuation runs with nothing clicked, so its body
    counts as after an await; one started from a later file's top level runs after that file."""
    top = {"library": [("early.js", "setTimeout(() => {\n  drawTiles(1);\n}, 0);\n"), ("late.js", _LATE)]}
    assert len(in_bundle_order_gaps(top, set())) == 1
    frame = "function soon() {\n  requestAnimationFrame(() => drawTiles(1));\n}\nsoon();\n"
    assert len(in_bundle_order_gaps({"library": [("early.js", frame), ("late.js", _LATE)]}, set())) == 1
    loaded = 'function soon() {\n  ensureModule("library").then(() => drawTiles(1));\n}\nsoon();\n'
    assert not in_bundle_order_gaps({"library": [("early.js", loaded), ("late.js", _LATE)]}, set()), "after the bundle, not between its files"
    clicked = 'function soon() {\n  button.addEventListener("click", () => setTimeout(() => drawTiles(1)));\n}\nsoon();\n'
    assert not in_bundle_order_gaps({"library": [("early.js", clicked), ("late.js", _LATE)]}, set()), "a timer a click starts waits for the click"
    from_late = {"library": [("early.js", _EARLY), ("late.js", _LATE + "loadTiles();\n")]}
    assert not in_bundle_order_gaps(from_late, set()), "started from late.js's top level, late.js's names are there"
    third = {"library": [("early.js", _EARLY.replace("drawTiles", "lastTiles")), ("late.js", "loadTiles();\n"), ("last.js", "function lastTiles(x) {\n  return x;\n}\n")]}
    assert len(in_bundle_order_gaps(third, set())) == 1, "but not a file after it"
