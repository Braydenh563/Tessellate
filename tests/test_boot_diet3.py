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


class _Count(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements = 0

    def handle_starttag(self, tag, attrs):
        self.elements += 1

    def handle_startendtag(self, tag, attrs):
        self.elements += 1


#: The elements `index.html` itself carries: 7,879 on 2026-11-01. Live, after a
#: sign-in on an empty notebook, 8,038 (the rest is what the first draw adds);
#: with a notebook of notes and a dashboard of widgets it is more (11,168 in the
#: audit). Every surface's DOM is in this page, so each tab pays on open: the
#: next step is surfaces as `<template>`s stamped on first visit (row 21), and
#: this number only goes down when that lands.
BOOT_ELEMENTS_CAP = 7_879


def test_the_boot_document_does_not_grow():
    counter = _Count()
    counter.feed((FRONTEND / "index.html").read_text(encoding="utf-8"))
    assert counter.elements <= BOOT_ELEMENTS_CAP, (
        f"index.html carries {counter.elements} elements, cap {BOOT_ELEMENTS_CAP}: "
        "a new surface is built on first visit, not shipped in the page"
    )


# --- readers of what a lazy file draws -----------------------------------------

#: name -> a read of what it draws. A function that calls the name without
#: awaiting it (or returning its promise) and then reads the drawn output is
#: reading it before it is there.
DRAWN = {
    "renderEntries": re.compile(r"#entry-list (?:>|li)[^`\"']*li\[data-id|#entry-list li\[data-id"),
    "openNotePage": re.compile(r"data-sheet=\"note\""),
    "refreshNotePage": re.compile(r"data-sheet=\"note\""),
}
FUNCTION = re.compile(r"^(?:async )?function [A-Za-z_$][\w$]*", re.M)


def _functions(text: str):
    starts = [m.start() for m in FUNCTION.finditer(text)]
    for i, start in enumerate(starts):
        yield text[start : starts[i + 1] if i + 1 < len(starts) else len(text)]


def _rest_of_block(body: str, at: int, indent: int) -> str:
    """The lines after a call that stay in its block (as deep as the call's line)."""
    lines = body[at:].split("\n")
    kept = [lines[0]]
    for line in lines[1:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        kept.append(line)
    return "\n".join(kept)


def _unawaited_reads() -> list[str]:
    found = []
    for path in sorted(JS.glob("*.js")):
        for body in _functions(path.read_text(encoding="utf-8")):
            name_line = body.split("\n", 1)[0]
            for fn, read in DRAWN.items():
                if f"function {fn}(" in name_line:
                    continue
                for m in re.finditer(rf"(?<![\w$.])(?P<pre>(?:await |return )?){fn}\(", body):
                    line_start = body.rfind("\n", 0, m.start()) + 1
                    before_on_line = body[line_start : m.start()]
                    after = _rest_of_block(body, m.end(), len(before_on_line) - len(before_on_line.lstrip()))
                    if m.group("pre") or ".then(" in after.split("\n", 1)[0] or "await" in before_on_line:
                        continue
                    if "typeof" in before_on_line:
                        continue
                    if read.search(after):
                        found.append(f"{path.name}: {name_line.strip()} calls {fn}() and reads its output without awaiting it")
                        break
    return found


def test_no_caller_reads_a_card_before_the_file_that_draws_it_has_arrived():
    assert not _unawaited_reads()


def test_the_probe_for_that_lint_sees_the_old_fault():
    bad = "function open(id) {\n  renderEntries();\n  const c = document.querySelector(`#entry-list li[data-id=\"${id}\"]`);\n}\n"
    (body,) = list(_functions(bad))
    assert DRAWN["renderEntries"].search(body)


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
        ("phone-shell.js", 'ensureModule("entryCard").then((ok) => (ok ? openNotePage(entry, returnFocus) : lazyLoadFailed('),
        ("documents.js", 'ensureModule("entryCard").then((ok) => (ok ? list.appendChild(entryItem(target.entry)) : lazyLoadFailed('),
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
