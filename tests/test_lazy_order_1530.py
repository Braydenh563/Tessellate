"""Two lazy-load faults found on 2026-11-01 (INBOX 1530): a board restored with its
Library side open drew tiles before whiteboard-templates.js ran (`wbThumbSvg is not
defined`), and a card file that loaded without defining `entryItem` made the notes
list ask for its own draw forever."""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"


def test_the_board_library_waits_for_its_bundle_before_drawing_tiles():
    lib = (JS / "whiteboard-library.js").read_text(encoding="utf-8")
    body = lib[lib.index("async function wbLoadLibrary"):].split("\n}\n")[0]
    assert body.index('await ensureModule("library");') < body.index("wbRenderLibrary();")


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
# the caller does, not callbacks) may not, after its first await, read a name
# only a LATER file of the bundle defines, unless `await ensureModule("<bundle>")`
# or a `typeof` test comes first in the function.

import re  # noqa: E402

from tests import test_lazy_bundle_calls as _bundles  # noqa: E402

_CALL = re.compile(r"(?<![\w$.])(?<!function )(?<!function\* )([A-Za-z_$][\w$]*)\s*\(")
_DECLARATION = re.compile(r"^(?:async )?function\*? ([A-Za-z_$][\w$]*)", re.M)
_IDENT = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)")
_COMMENT = re.compile(r"(?m)^\s*//.*$|(?<=\s)//\s.*$")


def _split_functions(source: str) -> tuple[dict[str, str], str]:
    """The column-zero functions of a file by name, and what is left of the file."""
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


def _opens_a_callback(line: str, depth: int) -> bool:
    if "=>" in line:
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
        if re.search(r"[{(\[]\s*$", line.rstrip()):
            stack.append((depth, _opens_a_callback(line, depth)))
    return kept


def _before_first_await(body: str) -> str:
    """What a function runs before it first yields: the part that runs inside its caller's turn."""
    at = body.find("await ")
    return body if at < 0 else body[:at]


def _reachable_at_load(functions: dict[str, str], rest: str) -> set[str]:
    """Functions a file's top level starts (a statement beginning in column zero), and those they call."""
    top = [ln for ln in _runs_with_the_block(rest) if ln[:1] not in (" ", "\t", "}", ")", "]", "")]
    pending = [m.group(1) for ln in top for m in _CALL.finditer(ln) if m.group(1) in functions]
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        for ln in _runs_with_the_block(_before_first_await(functions[name])):
            pending += [m.group(1) for m in _CALL.finditer(ln) if m.group(1) in functions and m.group(1) != name]
    return seen


def _late_name_in(text: str, late: dict[str, str], every: dict[str, str], seen: set[str]) -> tuple[str, str] | None:
    """A later-file name `text` reads, directly or through the functions of this bundle it calls."""
    for m in _IDENT.finditer(text):
        name = m.group(1)
        if name in late:
            return name, late[name]
        if name in every and name not in seen and re.match(r"\s*\(", text[m.end() :]):
            seen.add(name)
            hit = _late_name_in(_COMMENT.sub("", every[name]), late, every, seen)
            if hit:
                return hit
    return None


def _first_late_read(body: str, late: dict[str, str], every: dict[str, str], bundle: str) -> tuple[str, str] | None:
    """The first later-file name read after the function's first await finishes, unless guarded
    by `await ensureModule("<bundle>")` or a `typeof` test earlier in the function."""
    body = _COMMENT.sub("", body)
    if "await " not in body:
        return None
    start = body.find("\n", body.index("await "))
    lines = body[start:].split("\n")
    before = body[:start]
    for line in lines:
        if f'ensureModule("{bundle}")' in before or re.search(r"typeof\s+\w+", before + line):
            return None
        hit = _late_name_in(line, late, every, {m.group(1) for m in [re.match(r"\s*(?:async )?function (\w+)", body)] if m})
        if hit:
            return hit
        before += "\n" + line
    return None


def _top_level_names(source: str) -> set[str]:
    names = set(re.findall(r"^(?:async )?function\*? ([A-Za-z_$][\w$]*)", source, re.M))
    return names | set(re.findall(r"^(?:const|let|class) ([A-Za-z_$][\w$]*)", source, re.M))


def in_bundle_order_gaps(bundles: dict[str, list[tuple[str, str]]], always: set[str]) -> list[str]:
    """`bundles`: bundle to its `(file name, source)` in load order. `always`: names that are there
    before any bundle loads (boot files, stand-ins)."""
    gaps = []
    for bundle, files in bundles.items():
        split = [_split_functions(source) for _, source in files]
        bound = [_top_level_names(source) for _, source in files]
        every = {name: body for functions, _ in split for name, body in functions.items()}
        reached: set[str] = set()
        for _, rest in split:
            reached |= _reachable_at_load(every, rest)
        for index, (file_name, _) in enumerate(files):
            early = set().union(*bound[: index + 1])
            late = {n: files[j][0] for j in range(index + 1, len(files)) for n in bound[j] if n not in early and n not in always}
            for name, body in split[index][0].items():
                hit = _first_late_read(body, late, every, bundle) if name in reached and body.startswith("async") else None
                if hit:
                    gaps.append(f"{file_name}: {name} reads {hit[0]} (defined in {hit[1]}, later in the {bundle} bundle) after an await, with no ensureModule(\"{bundle}\") first")
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


def test_no_bundle_file_reads_a_later_file_after_an_await_without_the_bundle():
    bundles, always = _real_bundles()
    assert not in_bundle_order_gaps(bundles, always)


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
