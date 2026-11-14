"""Boot diet 3 (audit row 21, 2026-11-01): what the boot scripts no longer carry,
and the boot document's size, held down.

`buildTableBlock`, `paletteCommands` and `entryItem` (with the Quick access
draw that reads the palette's rows) were 8 to 9 KB, 5 KB and 3 KB gzipped of
script that nothing needs before the first input. They live in lazy files now;
this fails if one comes back to a boot script, or a boot script reads one
without a way to wait for it (the lazy-bundle lints say how:
`test_lazy_bundle_calls.py`), or a caller reads what a moved function draws
(a note's card, a table's bar) in the same breath, before the file that draws
it has arrived: the deep link `#/notes/12` on a fresh load found no card and
said "No such note.", and a table's source line was lost in a swap.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from tests._app_js import app_js_files

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
JS = FRONTEND / "js"

#: function -> the lazy file that holds it, and the bundle that loads that file.
MOVED = {
    "buildTableBlock": ("table-block.js", "tableBlock"),
    "paletteCommands": ("app-features.js", "featureRows"),
    "quickCatalogue": ("app-features.js", "featureRows"),
    "renderQuickLinks": ("app-features.js", "featureRows"),
    "entryItem": ("entry-card.js", "entryCard"),
}


def _defines(text: str, name: str) -> bool:
    return re.search(rf"^(?:async )?function {name}\(", text, re.M) is not None


def test_the_moved_functions_are_in_lazy_files_and_not_at_boot():
    boot = {path.name: path.read_text(encoding="utf-8") for path in app_js_files()}
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8") + (JS / "app.js").read_text(encoding="utf-8")
    for name, (file, bundle) in MOVED.items():
        assert _defines((JS / file).read_text(encoding="utf-8"), name), f"{name} is not in {file}"
        at_boot = [f for f, text in boot.items() if _defines(text, name)]
        assert not at_boot, f"{name} is back in a boot script: {at_boot}"
        assert file not in boot, f"{file} is a boot script"
        assert re.search(rf"\b{bundle}: \[[^\]]*\"/js/{re.escape(file)}\"", entries), f"bundle {bundle} does not load {file}"


def test_the_dashboards_quick_access_draw_waits_for_its_file_through_a_stand_in():
    entries = (JS / "lazy-entries.js").read_text(encoding="utf-8")
    assert 'featureRows: ["renderQuickLinks"]' in entries


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "param"}


class _Count(HTMLParser):
    """Elements the page parses into its live tree: what a `<template>` holds
    is an inert fragment until it is stamped (row 21), so it is not counted."""

    def __init__(self) -> None:
        super().__init__()
        self.elements = 0
        self.open: list[str] = []
        self.inert = 0

    def handle_starttag(self, tag, attrs):
        if not self.inert:
            self.elements += 1
        if tag == "template":
            self.inert += 1
        if tag not in _VOID:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if not self.inert:
            self.elements += 1

    def handle_endtag(self, tag):
        while self.open:
            last = self.open.pop()
            if last == "template":
                self.inert -= 1
            if last == tag:
                break


#: The elements `index.html` itself carries: 7,879 on 2026-11-01. Live, after a
#: sign-in on an empty notebook, 8,038 (the rest is what the first draw adds);
#: with a notebook of notes and a dashboard of widgets it is more (11,168 in the
#: audit). Every surface's DOM is in this page, so each tab pays on open: the
#: next step is surfaces as `<template>`s stamped on first visit (row 21), and
#: this number only goes down when that lands.
#: 7,879 to 7,897 on 2026-11-02: three audit 1028 fixes merged without moving it:
#: E71 Read aloud speed (14, inside the inert Settings body template), E47 the
#: saved-chat search (3), B34 an empty board's cue (1). To 7,901 the same day: INBOX
#: 1553's lock screen switch (4, inside the Settings body template). To 7,911 the
#: same day: INBOX 1544, which the owner asked for (more ways to open the insert
#: panels): Icon, Symbol and Calculator rows in the document's Insert menu and
#: Symbol and Equation on the note strip (10, five buttons and their icons).
#: To 7,921 the same day: audit 1028 S68 folds three imports on the settings-fold
#: recipe (11: a details, summary, help wrap and slot each; the pane 2,747 to 2,427 px).
#: To 7,923 on 2026-11-02: a phone's Documents kebab gains About these controls
#: (a button and its icon), since the dock's ? is hidden below 600 (a29h leftover).
#: To 7,945 on 2026-11-08: smalla-1108's Appearance rows, all inside the inert
#: Settings body template (22: Export and Import look with its file input, Mix
#: palette, accent and density, Line spacing and Line width with their options).
#: 7,948 on 2026-11-09 (INBOX 1717's three toolbar-word spans), and it counted
#: what sits in a `<template>` too, so no template could lower it, against the
#: intent above. It counts the live page now (row 21, row21-1109): 5,521 on head
#: with the Settings body already a template; the board canvas into
#: `<template data-surface="board">` (1,741 elements, built when a board opens)
#: took it to 3,782; the OCR workspace's card (`data-surface="ocr"`, 130) to 3,652;
#: the keyboard shortcuts sheet's card (`data-surface="shortcuts"`, 83) to 3,569.
#: 2026-11-13 (L621): measured 1,054 with the meeting recorder's card a surface too
#: (`data-surface="meeting"`, 61); the tab panes had gone to surfaces meanwhile.
BOOT_ELEMENTS_CAP = 1_054


def test_the_boot_document_does_not_grow():
    counter = _Count()
    counter.feed((FRONTEND / "index.html").read_text(encoding="utf-8"))
    assert counter.elements <= BOOT_ELEMENTS_CAP, (
        f"index.html parses {counter.elements} elements into the page, cap {BOOT_ELEMENTS_CAP}: "
        "a new surface is built on first visit, not shipped in the page"
    )


# --- readers of what a lazy file draws -----------------------------------------

#: name -> a read of what it draws. A function that calls the name without
#: awaiting it (or returning its promise) and then reads the drawn output is
#: reading it before it is there. A read is a card selector in a string
#: (`#entry-list li[data-id`, `#entry-list > li`), the list's element asked
#: for a card (`$("entry-list").querySelector(`, `.children`, a `const list =
#: $("entry-list")` alias asked the same), or a call to a helper that does one
#: of those (`focusNoteRow`, `flashEntry`: followed one level, see `_readers`).
_LIST_ASKS = r"\??\.(?:querySelector|querySelectorAll|children|firstElementChild|lastElementChild|getElementsBy\w+)"
_LIST_ALIAS = re.compile(r"(?:const|let|var)\s+([\w$]+)\s*=\s*(?:\$\(|document\.getElementById\()[\"']entry-list[\"']\)")
_CARD_STRING = re.compile(r"#entry-list\b")
_CARD_ELEMENT = re.compile(r"(?:\$\(|getElementById\()[\"']entry-list[\"']\)" + _LIST_ASKS)
_NOTE_SHEET = re.compile(r"data-sheet=\"note\"")


def _reads_a_card(code: str, whole: str = "") -> bool:
    """`code` reads a card; `whole` is the function it sits in, for an alias declared before it."""
    if _CARD_STRING.search(code) or _CARD_ELEMENT.search(code):
        return True
    return any(re.search(rf"(?<![\w$.]){re.escape(alias)}{_LIST_ASKS}", code) for alias in _LIST_ALIAS.findall(whole or code))


def _reads_the_sheet(code: str, whole: str = "") -> bool:
    return _NOTE_SHEET.search(code) is not None


DRAWN = {"renderEntries": _reads_a_card, "openNotePage": _reads_the_sheet, "refreshNotePage": _reads_the_sheet}
FUNCTION = re.compile(r"^(?:async )?function [A-Za-z_$][\w$]*", re.M)
_NAME = re.compile(r"(?:async )?function ([\w$]+)")


def _functions(text: str):
    starts = [m.start() for m in FUNCTION.finditer(text)]
    for i, start in enumerate(starts):
        yield text[start : starts[i + 1] if i + 1 < len(starts) else len(text)]


def _readers(fn: str, read) -> set[str]:
    """Functions (any file) whose own body reads what `fn` draws: a caller that
    reaches one of them right after an unawaited `fn()` reads it just the same."""
    found = set()
    for path in JS.glob("*.js"):
        for body in _functions(path.read_text(encoding="utf-8")):
            name = _NAME.match(body).group(1)
            #: A helper that itself waits for a draw still in flight (`await renderEntries.waiting`) is safe to call.
            if name != fn and read(body, body) and f"await {fn}" not in body:
                found.add(name)
    return found


def _is_callback(line: str) -> bool:
    return "=>" in line or (re.search(r"\bfunction\b", line) is not None and _NAME.match(line.strip()) is None)


def _runs_after(body: str, at: int, indent: int) -> str:
    """The code that runs after the call at `at`: the rest of its block, then the
    rest of each enclosing block, up to the first callback (a callback's end hands
    back to whoever called it, not to the next line) and minus a sibling `else`
    branch, which runs instead of the call, not after it."""
    stack: list[tuple[int, bool]] = []
    for line in body[:at].split("\n")[:-1]:
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if re.search(r"[{(\[]\s*$", line.rstrip()):
            stack.append((depth, _is_callback(line)))
    lines = body[at:].split("\n")
    kept, floor, skipping = [lines[0]], indent, None
    for line in lines[1:]:
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip())
        if skipping is not None:
            if depth > skipping:
                continue
            closes = line.lstrip().startswith("}") and "else" not in line
            skipping, floor = None, depth
            if closes or line.lstrip().startswith(("} else", "else")):
                skipping = None if closes else depth
                continue
        if depth < floor:
            gone = []
            while stack and stack[-1][0] >= depth:
                gone.append(stack.pop())
            if any(callback for _, callback in gone):
                break
            floor = depth
        if line.lstrip().startswith(("} else", "else")):
            floor = depth
            if line.rstrip().endswith("{"):
                skipping = depth
            continue
        kept.append(line)
    return "\n".join(kept)


def _unawaited_reads() -> list[str]:
    found = []
    helpers = {fn: _readers(fn, read) for fn, read in DRAWN.items()}
    for path in sorted(JS.glob("*.js")):
        for body in _functions(path.read_text(encoding="utf-8")):
            name_line = body.split("\n", 1)[0]
            for fn, read in DRAWN.items():
                if f"function {fn}(" in name_line:
                    continue
                for m in re.finditer(rf"(?<![\w$.])(?P<pre>(?:await |return )?){fn}\(", body):
                    line_start = body.rfind("\n", 0, m.start()) + 1
                    before_on_line = body[line_start : m.start()]
                    after = _runs_after(body, m.end(), len(before_on_line) - len(before_on_line.lstrip()))
                    if m.group("pre") or ".then(" in after.split("\n", 1)[0] or "await" in before_on_line:
                        continue
                    if "typeof" in before_on_line:
                        continue
                    calls = [h for h in helpers[fn] if re.search(rf"(?<![\w$.]){h}\(", after)]
                    if read(after, body) or calls:
                        found.append(f"{path.name}: {name_line.strip()} calls {fn}() and reads its output without awaiting it ({', '.join(calls) or 'directly'})")
                        break
    return found


def test_no_caller_reads_a_card_before_the_file_that_draws_it_has_arrived():
    assert not _unawaited_reads()


def test_the_probe_for_that_lint_sees_the_old_fault():
    bad = "function open(id) {\n  renderEntries();\n  const c = document.querySelector(`#entry-list li[data-id=\"${id}\"]`);\n}\n"
    (body,) = list(_functions(bad))
    assert DRAWN["renderEntries"](body, body)


def test_the_probe_sees_what_the_first_one_missed():
    """INBOX 1530 (e): the lint saw only `renderEntries();` then a literal
    `#entry-list li[data-id` in one block. It now also sees a helper that reads
    the card, a list element asked for a card (directly or through an alias),
    and a read after the block the call sits in; and it does not see a sibling
    branch, or the next callback."""
    def flagged(text):
        (body,) = list(_functions(text))
        at = body.index("renderEntries(") + len("renderEntries(")
        line = body[body.rfind("\n", 0, at) + 1 : at]
        indent = len(line) - len(line.lstrip())
        after = _runs_after(body, at, indent)
        calls = [h for h in ("focusNoteRow",) if re.search(rf"(?<![\w$.]){h}\(", after)]
        return bool(DRAWN["renderEntries"](after, body) or calls)

    helper = "function a(id) {\n  renderEntries();\n  focusNoteRow(id);\n}\n"
    element = "function a(id) {\n  renderEntries();\n  return $(\"entry-list\").querySelector(`li[data-id=\"${id}\"]`);\n}\n"
    alias = "function a(id) {\n  const list = $(\"entry-list\");\n  renderEntries();\n  return list.children[0];\n}\n"
    nested = "function a(id) {\n  if (id) {\n    renderEntries();\n  }\n  focusNoteRow(id);\n}\n"
    sibling = "function a(id) {\n  if (id) renderEntries();\n  else focusNoteRow(id);\n}\n"
    braced = "function a(id) {\n  if (id) {\n    renderEntries();\n  } else {\n    focusNoteRow(id);\n  }\n}\n"
    callback = "function a(items) {\n  items.push({\n    run: () => {\n      renderEntries();\n    },\n    other: () => focusNoteRow(1),\n  });\n}\n"
    assert flagged(helper) and flagged(element) and flagged(alias) and flagged(nested)
    assert not flagged(sibling) and not flagged(braced) and not flagged(callback)


def test_a_deep_link_paints_through_its_target_until_the_card_exists():
    asks = (JS / "capture-ask.js").read_text(encoding="utf-8")
    flash = asks[asks.index("async function flashEntry(") :].split("\n}\n", 1)[0]
    assert "(await renderEntries()) === false" in flash, "flashEntry draws without waiting for the card file"
    assert re.search(r"finally \{\s*noteEngine\.jumpId = null;", flash), "jumpId is cleared before the late draw"
    assert flash.index("await renderEntries()") < flash.index("querySelector(`#entry-list li[data-id")
    notes = (JS / "notes-list.js").read_text(encoding="utf-8")
    render = notes[notes.index("function renderEntries(") :].split("\n  const list =", 1)[0]
    assert "return renderEntries.waiting;" in render and "lazyLoadFailed(" in render and "return false;" in render


def test_a_file_that_never_arrives_says_so_instead_of_leaving_a_blank_list():
    for name, needle in (
        ("notes-list.js", 'lazyLoadFailed("Notes")'),
        ("phone-shell.js", 'ensureModule("entryCard").then((ok) => (ok && window.entryItem ? openNotePage(entry, returnFocus) : lazyLoadFailed('),
        ("documents-embeds.js", 'ensureModule("entryCard").then((ok) => (ok && window.entryItem ? list.appendChild(entryItem(target.entry)) : lazyLoadFailed('),
    ):
        assert needle in (JS / name).read_text(encoding="utf-8"), name


# --- the table -----------------------------------------------------------------


def test_a_table_is_one_element_from_the_render_to_its_bar():
    """The first table of a session was a host the bar later replaced: the host held
    the block's source line (`stampNewBlocks`) and the replacement did not."""
    nav = (JS / "navigation.js").read_text(encoding="utf-8")
    branch = nav[nav.index('shell.className = "code-block md-table-block"') - 200 :].split("continue;", 1)[0]
    assert "replaceWith" not in branch and "md-table-host" not in nav
    assert "buildTableBlock(scroller, headers, bodyRows, rawTable, shell)" in branch
    block = (JS / "table-block.js").read_text(encoding="utf-8")
    assert "function buildTableBlock(scroller, headers, bodyRows, rawTable, shell = null)" in block
    assert 'block.classList.add("code-block", "md-table-block")' in block
    assert "setTableView(block.dataset.tableView || bubbleView())" in block


def test_what_reads_a_tables_bar_waits_for_it():
    """Copy, CSV and the bar's label arrive with table-block.js: a reader of `.code-copy` or
    `.code-bar` outside it waits (`ensureModule("tableBlock")`) or it misses the first table."""
    readers = []
    for path in sorted(JS.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        code = "\n".join(line for line in text.split("\n") if not line.lstrip().startswith(("//", "*")))
        if path.name != "table-block.js" and re.search(r"querySelector(?:All)?\([^)]*\.code-(?:copy|bar)", code):
            if 'ensureModule("tableBlock")' not in code:
                readers.append(path.name)
    assert not readers, f"read a table's bar without waiting for it: {readers}"


def test_the_comments_panels_parts_are_built_on_the_first_draw() -> None:
    """The Comments section's heading, list, resolved toggle and shelf (5
    elements) were in the page, though nobody sees them until a remark exists
    (the cap went 7,923 to 7,927 with them). The page keeps the wrap; the file
    that draws the panel makes the rest, and one listener on the wrap serves the
    toggle."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    wrap = html[html.index('id="doc-comments-wrap"') :]
    assert wrap[wrap.index(">") + 1 :].lstrip().startswith("</div>"), "the wrap is empty in the page"
    for ident in ("doc-comments", "doc-comments-count", "doc-comments-resolved-toggle", "doc-comments-resolved"):
        assert f'id="{ident}"' not in html, ident
    comments = (FRONTEND / "js" / "documents-comments.js").read_text(encoding="utf-8")
    assert "if (wrap) docCommentsShell(wrap);" in comments
    for ident in ("doc-comments", "doc-comments-count", "doc-comments-resolved-toggle", "doc-comments-resolved"):
        assert f'"{ident}"' in comments[comments.index("function docCommentsShell") :], ident
