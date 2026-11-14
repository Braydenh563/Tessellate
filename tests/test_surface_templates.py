"""Audit 1031 row 21: surfaces as templates, stamped on first need.

A surface the page shows only on request sits in an inert
`<template data-surface="NAME">` inside its live root; `surfaceBuild(name)`
(settings-body.js) puts it in the page once, at the open or at the first `$`
of one of its ids (`surfaceFind`), and `onSurface(name, run)` runs wiring that
needs its elements once they exist. The markup stays in index.html, so ids,
help anchors and chord titles are read where they always were. This holds the
shape per surface, and the rule that keeps a template cheap: nothing that runs
at load wires its elements except through `onSurface`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
JS = FRONTEND / "js"
INDEX = (FRONTEND / "index.html").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

#: surface -> (its live root's id, globs of the files whose load-time wiring may
#: reach it, the function(s) that open it and must build it first, ids it must hold).
SURFACES = {
    "board": (
        "wb-canvas-view",
        ("whiteboard*.js",),
        ("wbShowCanvasView", "initWhiteboard"),
        ("whiteboard-container", "wb-tools-panel", "wb-format", "wb-outline-tree", "wb-back-to-boards"),
    ),    "ocr": ("ocr-workspace", ("library.js",), ("openOcrWorkspace",), ("ocr-close", "ocr-stage", "ocr-rail", "ocr-page-pane")),
    "quickNote": (
        "quick-note",
        ("quick-note.js", "field-clear.js", "editor.js", "capture-ask.js"),
        ("openQuickNote",),
        ("quick-note-text", "quick-note-status", "quick-note-private", "quick-note-save", "quick-note-more", "quick-note-close", "quick-note-clear"),
    ),
    "atlasChat": (
        "atlas-host",
        ("help-chat.js",),
        ("openHelpChat",),
        ("help-chat-group", "help-chat-messages", "help-chat-form", "help-chat-input", "help-chat-send", "help-chat-menu", "help-chat-starters"),
    ),
    "reminders": (
        "tab-reminders",
        ("shell-reminders.js", "reminder-*.js", "quickadd.js", "phone-shell.js", "dashboard.js", "palette.js", "wiring.js", "navigation.js"),
        ("switchTab",),
        ("reminder-compose", "reminder-magic", "reminder-groups", "reminders-empty"),
    ),
    "timeline": (
        "tab-timeline",
        ("timeline*.js", "quickadd.js", "skills.js", "wiring.js", "navigation.js", "phone-shell.js", "dashboard.js", "palette.js"),
        ("switchTab",),
        ("timeline-scroll", "timeline-scrubber", "timeline-view-seg", "timeline-search", "timeline-table-head", "timeline-jump-today"),
    ),
    "graph": (
        "tab-graph",
        ("wiring.js", "navigation.js", "settings-wiring.js", "reveal-targets.js", "phone-shell.js", "dashboard.js", "palette.js"),
        ("switchTab",),
        ("graph-card", "graph-box", "graph-options", "graph-layout", "graph-popup", "graph-refresh"),
    ),
    "documents": (
        "tab-documents",
        ("wiring.js", "navigation.js", "settings-wiring.js", "reveal-targets.js", "phone-shell.js", "dashboard.js", "palette.js", "editor.js", "chat.js", "notes-list.js", "capture-ask.js", "menus.js", "skills.js", "status.js"),
        ("switchTab",),
        ("doc-editor", "doc-title", "doc-list", "doc-toolbar", "doc-new"),
    ),
    "chat": (
        "tab-chat",
        ("*.js",),
        ("switchTab",),
        ("chat-input", "chat-send", "chat-sidebar", "chat-new", "chat-compress", "chat-fork"),
    ),
    "library": (
        "tab-library",
        ("<boot>",),
        ("switchTab",),
        ("library-subtabs", "library-boards-grid", "library-bulk-delete", "library-binbar", "library-activitybar"),
    ),
    "notes": (
        "tab-notes",
        ("<boot>",),
        ("switchTab",),
        ("entry-content", "entry-list", "sidebar", "category-list", "note-sort"),
    ),
    "palette": (
        "command-palette-overlay",
        ("palette.js", "app-palette.js", "editor.js", "field-clear.js", "status.js", "wiring.js", "settings-wiring.js", "lazy-entries.js", "dashboard.js", "navigation.js"),
        ("toggleAgentPalette",),
        ("command-palette-close", "command-palette-input", "command-palette-send", "command-palette-results", "command-palette-status"),
    ),
    "meeting": (
        "meeting-overlay",
        ("meetings.js", "router-overlays.js", "reveal-targets.js", "settings-wiring.js", "phone-shell.js"),
        ("openMeetingRecorder",),
        ("meeting-card", "meeting-close", "meeting-title", "meeting-transcript", "meeting-done"),
    ),
    "shortcuts": (
        "shortcuts-overlay",
        ("reveal-targets.js", "settings-wiring.js"),
        ("openShortcuts",),
        ("shortcuts-card", "shortcuts-close", "shortcut-list", "shortcut-list-whiteboard"),
    ),
}


#: (file, surface) of a partial IIFE the lint reads whole but whose chat-pane ids sit only inside
#: functions that run later (atlas.js `retireOlder` reads the bubbles when a face rests, never at load)
#: or inside `onSurface("chat", ...)` (answer-kit.js watches the message list once the pane is built).
#: meetings.js loads on first use and builds the meeting card as its first statement, so its wiring reads it built.
#: vault-unlock.js reads TYPED_IDS (chat, library, notes fields) only at lock time, inside functions.
INSIDE_FUNCTIONS = {("meetings.js", "meeting"), ("atlas.js", "chat"), ("answer-kit.js", "chat"), ("vault-unlock.js", "chat")}


def _template(name: str) -> tuple[str, str]:
    """(the markup just before the template, the template's body)."""
    m = re.search(rf'<template data-surface="{name}"[^>]*>(.*?)</template>', INDEX, re.S)
    assert m, f"no <template data-surface=\"{name}\"> in index.html"
    return INDEX[: m.start()], m.group(1)


def _ids(markup: str) -> set[str]:
    return set(re.findall(r'(?<![-\w])id="([^"]+)"', markup))


def _boot_scripts() -> tuple[str, ...]:
    """The scripts index.html loads at boot; the lazy modules load when a surface is opened, so they may reach it."""
    return tuple(re.findall(r'<script src="/js/([\w-]+\.js)', INDEX))


def _files(globs: tuple[str, ...]) -> list[Path]:
    if globs == ("<boot>",):
        globs = _boot_scripts()
    return sorted({p for g in globs for p in JS.glob(g)})


def _src(name: str) -> str:
    return (JS / name).read_text(encoding="utf-8")


def _unwrapped(path: Path) -> str:
    """The file with its one outer `(() => {` ... `})();` wrapper taken off and its body dedented, so the
    statements that run at load, and the functions they call, are top-level again for the checks below."""
    return _js_scope.unwrapped(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SURFACES)
def test_the_surface_sits_in_one_template_inside_its_live_root(name):
    root, _, _, wanted = SURFACES[name]
    before, body = _template(name)
    # The root stays live (checks of "is it open" never build it); the template
    # is its first child, comments aside.
    opening = re.search(rf'<(?:div|dialog)\b[^>]*\bid="{root}"[^>]*>\s*(?:<!--.*?-->\s*)*$', before, re.S)
    assert opening, f"the {name} template is not the first child of #{root}"
    ids = _ids(body)
    assert root not in ids
    missing = [i for i in wanted if i not in ids]
    assert not missing, f"{missing} are not in the {name} template"
    assert INDEX.count(f'data-surface="{name}"') == 1


def test_dollar_falls_back_to_every_surface():
    assert re.search(r"^const \$ = \(id\) => document\.getElementById\(id\) \|\| surfaceFind\(id\);$", _src("app.js"), re.M)


@pytest.mark.parametrize("name", SURFACES)
def test_opening_the_surface_builds_it_before_reading_it(name):
    _, globs, openers, _ = SURFACES[name]
    text = "".join(_unwrapped(p) for p in _files(globs))
    for opener in openers:
        m = re.search(rf"^(?:async )?function {opener}\([^)]*\) \{{\n(.*?)^\}}", text, re.S | re.M)
        assert m, f"{opener} not found"
        body = m.group(1)
        call = f'surfaceBuild("{name}");'
        if opener == "switchTab" and "surfaceBuild(name);" in body:
            call = "surfaceBuild(name);"  # a tab pane is a surface named like its tab
        assert call in body, f"{opener} does not build the {name} surface"
        reads = [i for i in (body.find('$("'), body.find("getElementById(")) if i != -1]
        assert not reads or body.index(call) < min(reads), f"{opener} reads an element before it builds the {name} surface"


def _load_time_blocks(text: str):
    """Top-level statements that run when the file loads: `onDomReady(...)`
    blocks, bare `document.getElementById(...)` and `$(...)` lines and IIFEs, with their text."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(("onDomReady(", "document.getElementById(", "$(", "onSurface(", "(function", "(() =>", "try {")):
            # The statement ends at the first unindented line closing it (a `try`, at its closing brace).
            j = i
            if line.startswith("try {"):
                while j < len(lines) - 1 and not (lines[j] == "}" and j > i):
                    j += 1
            else:
                while j < len(lines) - 1 and not (
                    re.search(r"\);\s*$", lines[j]) and (j == i or not lines[j].startswith((" ", "\t")))
                ):
                    j += 1
            yield i + 1, line, "\n".join(lines[i : j + 1])
            i = j + 1
        else:
            i += 1


def _template_only_classes(name: str) -> set[str]:
    """Classes the surface's template uses that the live page (everything outside every template) never does."""
    _, body = _template(name)
    live = re.sub(r"<template data-surface.*?</template>", "", INDEX, flags=re.S)
    def classes(markup):
        return {c for v in re.findall(r'\bclass="([^"]*)"', markup) for c in v.split()}
    return classes(body) - classes(live)


def _top_level_functions(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"^(?:async )?function (\w+)\([^)]*\) \{\n(.*?)^\}", text, re.S | re.M)}


def _selector_hits(block: str, ids: set[str], classes: set[str]) -> list[str]:
    """Ids named in quotes, and classes or ids inside the selector strings of `querySelector(All)`."""
    hits = {i for i in re.findall(r"""["'#]([\w-]+)["')\s]""", block) if i in ids}
    for selector in re.findall(r"""querySelector(?:All)?\(\s*(["'`])(.*?)\1""", block):
        hits |= {c for c in re.findall(r"\.([\w-]+)", selector[1]) if c in classes}
        hits |= {i for i in re.findall(r"#([\w-]+)", selector[1]) if i in ids}
    return sorted(hits)


@pytest.mark.parametrize("name", SURFACES)
def test_load_time_wiring_of_the_surface_waits_for_it(name):
    """A load-time block (and the top-level functions it calls) may not name an id, or select a class,
    that exists only in the surface's template: the selector finds nothing and the wiring is silently
    dropped (row 21 review: the board's More menu and colour wells)."""
    _, globs, _, _ = SURFACES[name]
    _, body = _template(name)
    ids = _ids(body)
    classes = _template_only_classes(name)
    found = []
    for path in _files(globs):
        text = _unwrapped(path)
        functions = _top_level_functions(text)
        for number, head, block in _load_time_blocks(text):
            if head.startswith(f'onSurface("{name}"'):
                continue
            if (path.name, name) in INSIDE_FUNCTIONS:
                continue
            reached = block + "".join(functions.get(f, "") for f in set(re.findall(r"\b(\w+)\(", block)))
            if head.startswith("onSurface("):
                # Another surface's hook runs later, when a user opens it, and what its handlers call runs later
                # still: only the hook's own text counts. `document.getElementById` never builds this one, so only `$` is the harm.
                reached = block
                reached = re.sub(r"document\.getElementById\(\s*[\"'][\w-]+[\"']\s*\)", "", reached)
            named = _selector_hits(reached, ids, classes)
            if named:
                found.append(f"{path.name}:{number} {named[:3]}")
    assert not found, f"wiring at load reaches the {name} template before it is built: " + "; ".join(found)


def _run(body: str) -> dict:
    parts = [
        "const log = []; const live = new Set();",
        "function tpl(name, ids) { const host = { name }; return { dataset: { surface: name }, parentNode: host,"
        + " content: { getElementById: (id) => (ids.includes(id) ? { id } : null) },"
        + " replaceWith() { ids.forEach((i) => live.add(i)); log.push('stamp ' + name); } }; }",
        "const tpls = [tpl('settings', ['sync-now']), tpl('board', ['whiteboard-container'])];",
        "const document = { querySelectorAll: () => tpls, getElementById: (id) => (live.has(id) ? { id, live: 1 } : null) };",
        "const window = { initHelpToggles: (h) => log.push('help ' + h.name), hideClosedDockMenuLists: (h) => log.push('dock ' + h.name),"
        + " localizeStaticChords: (h) => log.push('chords ' + h.name), stampShortcutTitles: (h) => log.push('titles ' + h.name) };",
        _src("settings-body.js"),
        body,
    ]
    out = subprocess.run(["node", "-e", "\n".join(parts)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@needs_node
def test_build_is_once_per_surface_find_builds_only_the_one_asked_and_the_queue_runs_after():
    result = _run(
        """
        const miss = surfaceFind('no-such-id');
        onSurface('board', () => log.push('board wiring'));
        const found = surfaceFind('whiteboard-container');
        const again = surfaceBuild('board');
        onSurface('board', () => log.push('board now'));
        const unknown = surfaceBuild('nothing');
        console.log(JSON.stringify({ miss, found, again, unknown, log }));
        """
    )
    assert result["miss"] is None
    assert result["found"]["live"] == 1, "the element, from the page, after the build"
    assert result["again"] is False and result["unknown"] is False
    assert result["log"] == [
        "stamp board", "help board", "dock board", "chords board", "titles board", "board wiring", "board now",
    ], result["log"]


@needs_node
def test_one_wiring_hook_that_throws_does_not_strand_the_rest_of_the_surface():
    """INBOX 1747: the queue was spliced out before it ran, so a hook that threw dropped every hook
    after it for good (their buttons dead) and made the `$` that built the surface throw."""
    result = _run(
        """
        onSurface('board', () => { throw new Error('boom'); });
        onSurface('board', () => log.push('second wiring'));
        let thrown = null;
        try { surfaceFind('whiteboard-container'); } catch (error) { thrown = error.message; }
        console.log(JSON.stringify({ thrown, log }));
        """
    )
    assert result["thrown"] is None and "second wiring" in result["log"], result


def test_the_sweeps_the_page_runs_at_boot_take_the_stamped_host():
    """Row 21 review: a stamped surface got the help sweep only. The closed dock-menu lists (the OCR reader
    menu), the Mac chord on static titles and the table-driven shortcut titles (the board's tooltips) are
    swept over the host that just arrived, so each takes a root and defaults to the document."""
    nav = _src("navigation.js")
    assert "function hideClosedDockMenuLists(root = document) {" in nav
    wiring = _src("settings-wiring.js")
    assert "function stampShortcutTitles(root = document) {" in wiring
    assert "function localizeStaticChords(root = document) {" in wiring
    for fn in ("hideClosedDockMenuLists", "localizeStaticChords", "stampShortcutTitles"):
        assert f"window.{fn}?.(host);" in _src("settings-body.js"), f"surfaceBuild does not sweep {fn} over the host"


def test_a_resize_before_the_first_board_open_does_not_read_the_unbuilt_canvas():
    """e2e editor-keys at 700 px: a window resize ran `wbScheduleCull`, whose canvas read threw on the board's
    template not yet stamped (`getBoundingClientRect` of null, two page errors per resize)."""
    js = (ROOT / "frontend" / "js" / "whiteboard.js").read_text(encoding="utf-8")
    body = js[js.index("function wbCanvasOriginRect() {") :][:500]
    assert 'getElementById("whiteboard-container")?.getBoundingClientRect() ?? null' in body
    assert "if (rect) wbCullNow(undefined, { width: rect.width, height: rect.height });" in js


def test_unlocking_does_not_build_the_notes_pane_to_look_at_its_strip():
    """audit 1030 Y5: `resetNavigationToDefaults` runs from `lockOpened` and asked `$("notes-subtabs")`, which builds
    the Notes template (about 1,000 nodes) on every unlock. A strip that is not in the page is not built, so there
    is nothing to put back on its front page: the question is `getElementById`, which builds nothing."""
    nav = _src("navigation.js")
    body = nav[nav.index("function resetNavigationToDefaults() {") :][:1400]
    assert 'document.getElementById("notes-subtabs")?.dataset.ready' in body
    assert '$("notes-subtabs")' not in body
