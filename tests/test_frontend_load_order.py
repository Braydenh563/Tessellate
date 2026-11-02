"""A shared helper lives in a file every caller is loaded after.

There is no bundler and no module system here: `index.html` lists the scripts
and the browser runs them in that order. A `function` declaration is hoisted
inside its own file only, so code that runs while the page is still loading can
reach helpers from a script that has already run, and nothing else.

The report this exists for, from the running app:

    ReferenceError: apiPagedList is not defined
        at loadCaptureDocuments (app.js:10059)
        at showNotesSection (app.js:25240)
        at initNotesSubtabs (app.js:25290)
        at app.js:32441

`apiPagedList` was defined in documents.js, which index.html loads ten lines
after app.js. Its own comment argued the placement was safe because "both call
it from inside a function body, so load order is satisfied either way": true
when it was written, false the moment app.js called it from boot code. The
Notes tab died before drawing anything, and no other test here could see it,
because a Python test cannot run the page and every call site reads as correct
on its own.

**What this checks, and what it does not.** Two cheap rules: a call written as
a statement in a script's own top-level code, and the placement of the helpers
that are shared widely enough for the question to arise at all. The general
version, following the call graph from every top-level statement, was written
and then cut: the walk has to know which bodies are callbacks (a body handed to
`addEventListener` runs later, not now), and getting that right without a
parser took longer to run than the whole lint set. `errors.js` in the sweeps
catches the runtime half by loading the page and reading the console, which is
how this one would have been caught before it shipped. Recorded in BACKLOG.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests import _js_scope
from tests._app_js import app_js_files, app_js_text

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
INDEX = FRONTEND / "index.html"

#: Scripts that run before the app's own code and guard every cross-file call
#: they make (`typeof x === "function"`, `window.x?.()`). They are the boot
#: shims, and the guard is the point of them.
BOOT_SHIMS = {"boot-guard.js", "theme-boot.js"}

#: The bundles `ensureModule` fetches on the first visit to a tab that needs
#: them (WORLD_CLASS_PLAN row A1). They are not `<script>` tags in index.html
#: any more, but the rule this file exists for is unchanged for them: they run
#: after every script index.html lists, and inside a bundle they run in the
#: order the table gives, because `ensureModule` sets `async = false`. Reading
#: the table out of app.js rather than restating it here means a file moved
#: between bundles is checked in its new position on the next run.
LAZY_TABLE = re.compile(r"const LAZY_MODULES = \{(.*?)\n\};", re.S)


def _lazy_order() -> list[str]:
    app = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    table = LAZY_TABLE.search(app)
    assert table, "app.js has no LAZY_MODULES table; has the lazy loader moved?"
    names = [name for name in re.findall(r'"/js/([A-Za-z0-9_.-]+\.js)"', table.group(1))]
    assert names, "the LAZY_MODULES table lists no files"
    for name in names:
        assert (FRONTEND / "js" / name).exists(), f"LAZY_MODULES names {name}, which does not exist"
    return names


#: The stand-ins app.js installs for the lazy bundles' entry points. A name on
#: this table is bound by app.js's own top-level code (the loop under the
#: table replaces `window[name]` with a function that fetches the bundle and
#: then calls the real one), so for the purposes of the walk below it is
#: defined by app.js and not by the file it finally comes from.
ENTRY_POINT_TABLE = re.compile(r"const LAZY_ENTRY_POINTS = \{(.*?)\n\};", re.S)


def _stand_ins() -> set[str]:
    app = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    table = ENTRY_POINT_TABLE.search(app)
    assert table, "app.js has no LAZY_ENTRY_POINTS table; has the lazy loader moved?"
    names = set(re.findall(r'"([A-Za-z_$][\w$]*)"', table.group(1)))
    assert names, "the LAZY_ENTRY_POINTS table lists no names"
    return names


def _script_order() -> list[str]:
    html = INDEX.read_text(encoding="utf-8")
    names: list[str] = []
    for match in re.finditer(r'<script src="/js/([A-Za-z0-9_.-]+\.js)', html):
        name = match.group(1)
        if (FRONTEND / "js" / name).exists() and name not in names:
            names.append(name)
    assert names, "no local scripts found in index.html"
    for name in _lazy_order():
        if name not in names:
            names.append(name)
    return names


def _top_level(source: str) -> str:
    """Everything outside a top-level `function` declaration: the code that
    runs the moment the browser reaches the line."""
    out: list[str] = []
    depth = 0
    for line in source.split("\n"):
        stripped = line.strip()
        if depth == 0 and not stripped.startswith(("//", "/*", "*")):
            out.append(line)
        depth += line.count("{") - line.count("}")
        depth = max(depth, 0)
    return "\n".join(out)


STATEMENT_CALL = re.compile(r"^\s*(?:await\s+|void\s+)?([A-Za-z_$][\w$]*)\s*\(", re.M)
NOT_CALLS = {"if", "for", "while", "switch", "catch", "return", "typeof", "function"}


def test_no_script_calls_a_later_script_from_its_own_top_level():
    order = _script_order()
    sources = {name: (FRONTEND / "js" / name).read_text(encoding="utf-8") for name in order}
    defined_in: dict[str, str] = {}
    for name in order:
        for function in re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)\(", sources[name], re.M):
            defined_in.setdefault(function, name)
    #: A lazy bundle's entry point is reachable from the moment app.js installs
    #: its stand-in, which is what that table is for, so the walk must read it
    #: as app.js's own. Without this the walk would report every one of them and
    #: the only way to quiet it would be to load the bundles at boot again.
    for function in _stand_ins():
        defined_in[function] = "app.js"

    problems = []
    for index, name in enumerate(order):
        if name in BOOT_SHIMS:
            continue
        already = set(order[: index + 1])
        called = {m.group(1) for m in STATEMENT_CALL.finditer(_top_level(sources[name]))} - NOT_CALLS
        for function in sorted(called):
            home = defined_in.get(function)
            if home and home not in already:
                problems.append(f"{name} calls {function}() at load, defined in {home}")

    assert not problems, (
        "these calls run while the page is loading and name a helper from a "
        "script that has not run yet, which is a ReferenceError in the browser "
        "and invisible to every other test here: " + "; ".join(problems)
    )


def test_the_paging_helper_is_reachable_from_the_script_that_boots_with_it():
    """The specific case, named, because the walk above only sees the direct
    call and this one arrived three frames deep: `initNotesSubtabs()` at the
    bottom of app.js, into `showNotesSection`, into `loadCaptureDocuments`.

    Six frontend files call `apiPagedList` now. The one they are all loaded
    after is app.js, so that is where it lives.
    """
    order = [name for name in _script_order() if name not in BOOT_SHIMS]
    callers = [
        name
        for name in order
        if re.search(r"(?<![\w$.])apiPagedList\s*\(", (FRONTEND / "js" / name).read_text(encoding="utf-8"))
    ]
    assert callers, "nothing calls apiPagedList any more; is it still needed?"
    home = [
        name
        for name in order
        if re.search(r"^(?:async )?function apiPagedList\(", (FRONTEND / "js" / name).read_text(encoding="utf-8"), re.M)
    ]
    assert len(home) == 1, f"apiPagedList is defined in {home}"
    assert order.index(home[0]) <= order.index(callers[0]), (
        f"apiPagedList lives in {home[0]}, which index.html loads after "
        f"{callers[0]}, and app.js reaches it from `initNotesSubtabs` at load"
    )


def test_every_lazy_name_app_js_reads_at_load_has_a_stand_in():
    """The rule that replaced the `<script>` order for the lazy bundles.

    graph.js used to be loaded *before* app.js, because app.js's own top-level
    wiring reads eight of its functions as bare identifiers
    (`addEventListener("click", closeGraphPopup)`), and a `function`
    declaration hoists inside its own script element only. Now that the bundle
    arrives on the first visit to the tab, those reads are ReferenceErrors
    unless app.js has bound the name itself first, which is what
    `LAZY_ENTRY_POINTS` does.

    So: every function a lazy bundle defines and app.js names anywhere in its
    own top-level code has to be on that table. This is the half
    `test_no_script_calls_a_later_script_from_its_own_top_level` above cannot
    see, because that one only looks at calls written as statements, and most
    of these are references handed to `addEventListener`.
    """
    lazy_files = _lazy_order()
    lazy_functions: dict[str, str] = {}
    for name in lazy_files:
        source = (FRONTEND / "js" / name).read_text(encoding="utf-8")
        for function in re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)\(", source, re.M):
            lazy_functions.setdefault(function, name)

    #: "app.js" is the app's code, every piece of it (tests/_app_js.py): the
    #: split into files did not change which names are read at load, only
    #: where, so every piece's top level is read here.
    app = app_js_text()
    #: app.js's own declarations win: a name it defines is its, and the install
    #: loop skips it for exactly that reason.
    own = set(re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)\(", app, re.M))
    stand_ins = _stand_ins()

    missing: list[str] = []
    top = "\n".join(_top_level(path.read_text(encoding="utf-8")) for path in app_js_files())
    for line in top.split("\n"):
        code = re.sub(r'"[^"]*"|\'[^\']*\'|`[^`]*`', '""', line).split("//")[0]
        for match in re.finditer(r"[A-Za-z_$][\w$]*", code):
            function = match.group(0)
            if match.start() and code[match.start() - 1] == ".":
                continue
            if function in own or function in stand_ins:
                continue
            if function in lazy_functions:
                missing.append(f"{function} ({lazy_functions[function]}), app.js: {line.strip()[:80]}")

    assert not missing, (
        "app.js names these lazily-loaded functions in its own top-level code "
        "but has no stand-in for them, so the name is undefined until the tab "
        "is opened: " + "; ".join(sorted(set(missing)))
    )


def test_the_stand_ins_name_functions_that_exist():
    """A stand-in for a name nothing defines is a control that silently does
    nothing: `ensureModule` resolves, the lookup finds the stand-in itself, and
    the call returns undefined. Renaming a function in a lazy file without
    touching the table is how that happens."""
    lazy_functions: set[str] = set()
    for name in _lazy_order():
        source = (FRONTEND / "js" / name).read_text(encoding="utf-8")
        lazy_functions.update(re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)\(", source, re.M))
        lazy_functions.update(_js_scope.exported(source))  # a wrapped file's surface (row 37a)
    orphans = sorted(_stand_ins() - lazy_functions)
    assert not orphans, (
        "LAZY_ENTRY_POINTS names these, which no lazily-loaded file defines: " + ", ".join(orphans)
    )


def test_lazy_bundles_do_not_wait_for_domcontentloaded():
    """A file `ensureModule` inserts on first use arrives long after
    `DOMContentLoaded` fired, so a listener on that event never runs. Seven
    of library.js's top-level wirings were wrapped that way and every Library
    sub-tab lost its click handler the day the bundle went lazy. Lazy files
    wire through `onDomReady` (app.js), which runs at once when the document
    is already parsed."""
    for file in _lazy_order():
        text = (FRONTEND / "js" / file).read_text(encoding="utf-8")
        assert 'addEventListener("DOMContentLoaded"' not in text, (
            f"{file} waits for DOMContentLoaded; use onDomReady() so it wires when loaded on demand"
        )


def _function_body(source: str, name: str) -> str:
    match = re.search(r"^(?:async )?function " + re.escape(name) + r"\(", source, re.M)
    if not match:
        return ""
    depth = 0
    for index in range(match.start(), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    return source[match.start() :]


def test_app_js_does_not_read_a_later_scripts_constant_at_load():
    """`const` declarations are not hoisted across script elements either.
    settings.js declares `AI_NAME`; `renderPlanToggle()`, called from app.js's
    own top-level code, read it, threw `ReferenceError: AI_NAME is not
    defined` at boot, and the app never drew. The walk above only follows
    function *definitions*, so it could not see a constant. This looks at
    app.js's top-level lines and, one level down, the bodies of the functions
    those lines call as statements. A read inside a function that only runs
    later (a click handler, a renderer) is fine, and `typeof X` is the guard."""
    #: Since the app.js split, per piece: each piece of the app's code
    #: (tests/_app_js.py) against the constants of every script after it,
    #: the later pieces included, which is the split's own TDZ hazard
    #: (appjs-split.md hazard 2). Bodies are looked up in the whole of the
    #: app's code, since a piece may call a function an earlier one declared.
    app = app_js_text()
    order = _script_order()
    hits: list[str] = []
    for path in app_js_files():
        later: set[str] = set()
        for name in order[order.index(path.name) + 1 :]:
            later.update(re.findall(r"^const ([A-Z][A-Z0-9_]+) =", (FRONTEND / "js" / name).read_text(encoding="utf-8"), re.M))
        top = _top_level(path.read_text(encoding="utf-8"))
        at_load = top
        for function in {m.group(1) for m in STATEMENT_CALL.finditer(top)} - NOT_CALLS:
            at_load += "\n" + _function_body(app, function)
        if not later:
            continue
        #: One pattern for all of them: a search per name per line was 200
        #: seconds across 23 pieces, this is under two.
        names = "|".join(sorted(map(re.escape, later), key=len, reverse=True))
        read = re.compile(r"(?<![\w$.])(" + names + r")(?![\w$])")
        hits += [
            f"{path.name}: {line.strip()[:80]}"
            for line in at_load.split("\n")
            for name in {m.group(1) for m in read.finditer(line.split("//")[0])}
            if "typeof " + name not in line
        ]
    assert not hits, "app.js reads a later script's constant at load: " + "; ".join(hits)


def test_a_typeof_guard_at_load_cannot_see_a_later_scripts_constant():
    """`typeof X !== "undefined"` is the guard the test above accepts, and it
    is the right one inside a function that runs later. Written in a script's
    own top-level code against a constant of a *later* script, it is a
    different thing: the later script has not run, the binding does not exist
    yet, `typeof` says "undefined", and the guarded block never runs at all,
    in any build, for any value of the constant. Nothing throws, so no sweep
    sees it. settings-wiring.js did exactly this with `TOUR_ENABLED` (tour.js,
    the page's last script) around the code that greys out the About pane's
    "Take tour again" button while the tour is off: the fix the owner asked
    for on 2026-09-21 was on the branch and had never once executed. Work
    gated on a later script's constant waits for `DOMContentLoaded`
    (`onDomReady`), which fires after every classic script has run."""
    order = _script_order()
    guard = re.compile(r'typeof ([A-Z][A-Z0-9_]+) (?:!==|===) "undefined"')
    hits: list[str] = []
    for path in app_js_files():
        later: set[str] = set()
        for name in order[order.index(path.name) + 1 :]:
            later.update(re.findall(r"^const ([A-Z][A-Z0-9_]+) =", (FRONTEND / "js" / name).read_text(encoding="utf-8"), re.M))
        for line in _top_level(path.read_text(encoding="utf-8")).split("\n"):
            for name in {m.group(1) for m in guard.finditer(line.split("//")[0])}:
                if name in later:
                    hits.append(f"{path.name}: {line.strip()[:90]}")
    assert not hits, (
        "a top-level typeof guard names a later script's constant, so the block "
        "it guards can never run: " + "; ".join(hits)
    )
