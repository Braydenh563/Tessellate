"""The frontend's one global scope, counted (audit 2026-10-05, FE-17).

Every script shares one scope (CLAUDE.md section 7: app.js is 25 files and
the lazy bundles join them), so a call across files is a call to a global,
and a call into a bundle that may not be loaded yet is guarded with
`typeof name === "function"`. The audit counted 3,950 top-level functions,
700 top-level `let`/`var` and 371 guards, with no duplicate function names.
Nothing is wrong with any one of them; the numbers are the coupling, and
nothing watched them. These are ratchets: they may only go down, or move
with a reason written here.
"""

from __future__ import annotations

import functools
import re
from collections import Counter, defaultdict
from pathlib import Path

from tessellate.api.asset_strip import strip_js_comments
from tests import _js_scope

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

#: 2026-10-05 (comments excluded; worker files included, they are few).
#: The same day, after six branches merged, 387 guards and 718 lets: 19
#: guards in documents.js on boot files' own functions (always defined by
#: the time a lazy bundle runs) came out, and twelve lets became fields of
#: one const per file (the palette, onboarding, the notes rail, the template
#: picker, the finder) or plain consts (`timelineZoom`, `notePanel`).
#: The integration branch after search-boot-1005 merged, 2026-10-05: 288
#: guards (63 same-bundle ones in boot files dropped to bring boot JS under its
#: cap) and 705 lets.
#: And after the Atlas merge: the companion's own toast and prefs guards gone.
#: After the E2E merges (280 and 706): the three `openTour` guards (a
#: LAZY_ENTRY_POINTS stand-in, always defined) came out, and four documents.js
#: lets became fields of two consts (the word list's loading and failed flags,
#: the dim and typewriter reading modes).
#: 2026-10-31, S3 (avatars.js and atlas.js left the boot): the boot files that
#: drew faces now wait with `afterCharacters` or a stand-in, so six guards
#: (276 to 270) came out.
GUARDS_CAP = 270
TOP_LEVEL_LETS_CAP = 699
#: Ranked row 37a, 2026-11-01: every name a script adds to the shared scope
#: (`tests/_js_scope.py`: a wrapped file's exports, any other file's top-level
#: declarations). 9,905 before; embed-choices.js, model-bench.js and
#: dash-night.js wrapped whole, one export each, freed 23. Z1 added
#: space-swap.js (two entry points, wrapped); run-debug.js wrapped: 9,875;
#: ai1518's companion-remark.js and attachment-actions.js wrapped, one export each: 9870.
#: gaps1521-1101: reminder-notify.js, dash-orphans.js, edit-conflict.js and attachment-peek.js
#: wrapped, one export each (measured 9,866). docs-1101: the version history dialog and the
#: line diff (documents-history.js, 710 lines) wrapped whole, seven exports (measured 9,848). doc22-1102:
#: the frontmatter model and properties panel (documents-props.js) wrapped whole, four exports; the
#: cap is set to the measured count (9,785). doc23-1102: the Mermaid
#: fences (documents-mermaid.js, 426 lines) wrapped whole, three exports; measured 9,775. doc23-1102: the TeX parser and MathML
#: renderer (documents-math.js, 400 lines) wrapped whole, two exports; measured 9,754. doc23-1102: the comments
#: model and panel (documents-comments.js, 436 lines) wrapped whole, five exports; measured 9,742. doc23-1102: embeds and wiki-link
#: targets (documents-embeds.js, 335 lines) wrapped whole, seven exports; measured 9,739. doc24-1102: the table
#: model (documents-tables.js, 676 lines) wrapped whole, 23 exports; measured 9,732. doc24-1102: the columns block
#: (documents-columns.js, 267 lines) wrapped whole, three exports; measured 9,726. doc24-1102: a plain Ctrl+P and the page setup
#: (documents-print.js, 186 lines) wrapped whole, six exports; measured 9,720. doc24-1102: the breadcrumb row and the outline's
#: folds and filter (documents-outline.js, 327 lines) wrapped whole, ten exports; measured 9,714. a28z-1102 (INBOX 1556): the
#: web panel's search and result rows (web-results.js, 400 lines) wrapped whole, eight exports, with the SearXNG start helper
#: and failure row added inside it; measured 9,708. 1546 P1 (D4): the board's `wbMermaidParse` and `wbMermaidText` go and
#: documents-mermaid.js exports `diagramModel`; measured 9,706. 2026-11-08 (after merges took it to 9,711): task-steps.js
#: (three exports) and obj-order.js (eight) wrapped whole; measured 9,701.  iife-1109: screen-context, load-failed, feature-model-sheet, phone-more,
#: extract-preview, timeline-detail, scroll-row, assistant-avatar and confirmed-patterns wrapped whole, one export each; measured 9,688. Then date-field, link-types, vault-unlock, offline-split and pick-row wrapped whole; measured 9,678. iife2-1109: twenty lazy files wrapped whole (see CHANGELOG); measured 9,598. iife3-1109: tidy, lan-watch, documents-ai and model-menu wrapped whole (six exports in all); measured 9,513. Then ocr-engine and note-properties wrapped whole; measured 9,490. iife4-1109: twenty-one files that tests reached privately wrapped whole (the tests read them through `_js_scope.unwrapped`, or run the vm with `window` as the context); measured 9,096. s58-1110 (W29 D24): settings-packages.js, appearance-panel.js and whiteboard-history.js wrapped whole; measured 9,044.
#: 2026-11-11, W29 carve 1: panel-movable.js wrapped whole, one export (panelId). Measured 8,966.
#: W29 carve 2: suggestions-inbox.js wrapped whole, one export (openSuggestionsInbox). Measured 8,940.
#: W29 carve 3: tour.js wrapped whole, exporting `TOUR_ENABLED`, `openTour` and `renderTourReplay`. Measured 8,883.
#: W29 carve 4: timeline-calendar.js wrapped whole, exporting ten names the timeline and its tests call. Measured 8,830.
#: W29 carve 5: quickadd.js wrapped whole, exporting eight names. Measured 8,782.
#: W29 carve 6: reply-kit.js wrapped whole, exporting five names. Measured 8,733.
#: W29 carve 7: app-palette.js wrapped whole, exporting six names. Measured 8,679.
#: 2026-11-11 W29 carve 8: documents-codekit.js wrapped whole, four exports. Measured 8,629.
#: 2026-11-11 W29 carve 9: categories-panel.js wrapped whole, 12 exports. Measured 8,609.
#: 2026-11-11 W29 carve 10: capture-card-more.js wrapped whole, 4 exports. Measured 8,592.
#: 2026-11-11 W29 carve 11: captions.js wrapped whole, 4 exports. Measured 8,576.
#: 2026-11-11 W29 carve 12: ask-chart.js wrapped whole. Measured 8,560.
#: 2026-11-11 W29 merge with the sweeps: cap to measured. Measured 8,559.
#: 2026-11-11 W29 carve 13: map-preview.js wrapped whole. Measured 8,538.
#: 2026-11-11 W29 carve 14: math-field.js wrapped whole. Measured 8,519.
#: 2026-11-11 W29 carve 15: icon-picker.js wrapped whole. Measured 8,503.
#: 2026-11-11 W29 merge with the hub head: one name added by the hub's atlas lag work (nameMarkBuddyFollowFrame / afterCalm area), cap to measured. Measured 8,504.
#: 2026-11-11 scope-wrap-1111: lag-watch.js (five exports) and agent-activity.js (eleven) wrapped whole; math-field.js, ask-chart.js and capture-card-more.js were already wrapped. Measured 8,454.
#: 2026-11-11 Q34 (offline studio, natural voice): studio.js wrapped whole, two exports (openStudio, speakNatural); sync-folder.js, one (openFolderSync). Measured 8,457.
#: 2026-11-11 D24 scope-wrap-1111b: avatars.js (113 exports) and graph-canvas.js (21) wrapped whole; the tests read them through `unwrapped`, and the shared readers in `tests/_app_js.py` unwrap every file. Measured 7,878.
#: 2026-11-11 D24 scope-wrap-1111b, second group: meetings.js, bg-art.js, settings-controls.js, settings-find.js, settings-models.js, atlas-life.js, companion-menu.js and companion-throw.js wrapped whole. Measured 7,406.
#: 2026-11-14 L286 (D24): whiteboard-export.js carved out of whiteboard.js and wrapped whole, 18 exports for 43 names. Measured 7,381.
#: 2026-11-14 L286 (D24): present, frames, comments and locks carved out of whiteboard.js and wrapped whole. Measured 7,353.
#: 2026-11-14 L286 (D24): search, connectors and arrange carved out of whiteboard.js and wrapped whole. Measured 7,303.
#: 2026-11-14 L286 (D24): navigator and sketch-text carved out of whiteboard.js and wrapped whole. Measured 7,279.
#: 2026-11-14 L286 (D24): textedit and ctxmenu carved out of whiteboard.js and wrapped whole. Measured 7,262.
#: 2026-11-14 L286 (D24): place, stacking and bar carved out of whiteboard.js and wrapped whole. Measured 7,234.
#: 2026-11-14 L286 (D24): map strip, waypoints and marks carved out of whiteboard-map.js and wrapped whole. Measured 7,203.
GLOBAL_NAMES_CAP = 7203


@functools.lru_cache(maxsize=None)
def _code() -> dict[str, str]:
    return {p.name: strip_js_comments(p.read_text(encoding="utf-8")) for p in sorted(JS.glob("*.js"))}


def test_cross_file_guards_only_go_down():
    count = sum(
        len(re.findall(r'typeof\s+[A-Za-z_$][\w$]*\s*===?\s*"function"', code))
        for code in _code().values()
    )
    assert count <= GUARDS_CAP, (
        f"{count} `typeof x === \"function\"` guards (cap {GUARDS_CAP}): a call across "
        "files that needs one is a lazy bundle's entry point; name it in app.js's "
        "stand-ins rather than guarding at each caller"
    )


def test_top_level_mutable_state_only_goes_down():
    count = sum(len(re.findall(r"^(?:let|var)\s", code, re.M)) for code in _code().values())
    assert count <= TOP_LEVEL_LETS_CAP, f"{count} top-level let/var (cap {TOP_LEVEL_LETS_CAP})"


def test_no_two_files_define_the_same_function():
    names: Counter = Counter()
    for name, code in _code().items():
        if name.endswith("-worker.js"):
            continue  # a worker has its own scope
        names.update(re.findall(r"^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)", code, re.M))
    twice = sorted(n for n, c in names.items() if c > 1)
    assert not twice, f"defined twice in the one global scope: {twice}"


@functools.lru_cache(maxsize=None)
def _sources() -> dict[str, str]:
    return {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted(JS.glob("*.js"))
        if not p.name.endswith("-worker.js")  # a worker has its own scope
    }


def test_global_names_only_go_down():
    count = sum(len(_js_scope.global_names(source)) for source in _sources().values())
    assert count <= GLOBAL_NAMES_CAP, (
        f"{count} names in the shared scope (cap {GLOBAL_NAMES_CAP}): wrap a file whole in "
        "`(() => {` ... `})();` and export only what other files call (ranked row 37a)"
    )


_TOKEN = re.compile(r"[\w$]+")


def _named_in(code: dict[str, str]) -> dict[str, set[str]]:
    """Token -> the files that name it as a global would be named: a whole identifier that is not a member access
    (`x.name`), except `window.name`. One pass over the 14 MB of script, where a regex search per export per file
    took a minute (CI time 1109); the answer is the old per-export regex's: a name not after a dot, or after `window.`, and not inside a longer one."""
    named: dict[str, set[str]] = defaultdict(set)
    for file, text in code.items():
        for m in _TOKEN.finditer(text):
            start = m.start()
            if start and text[start - 1] == "." and text[max(0, start - 7) : start] != "window.":
                continue
            named[m.group()].add(file)
    return named


def test_a_wrapped_file_exports_only_what_it_defines_and_others_call():
    """An export the file does not define is a stand-in that resolves to
    nothing; one nothing else names is a private name back in the shared scope."""
    sources = _sources()
    named = _named_in(_code())
    wrong = []
    for name, source in sources.items():
        for export in sorted(_js_scope.listed(source)):
            if not re.search(rf"^  (?:async\s+)?(?:function\s+|const\s+|class\s+){re.escape(export)}\b", source, re.M):
                wrong.append(f"{name} exports {export} but does not define it at its top")
            elif not (named.get(export, set()) - {name}):
                wrong.append(f"{name} exports {export}, which no other file names")
    assert not wrong, "; ".join(wrong)


#: Browser globals reached as `self.x?.()` where a browser may lack them.
_BROWSER_OPTIONAL = {"getComputedStyle", "getSelection", "matchMedia", "requestIdleCallback", "cancelIdleCallback",
                     "queueMicrotask", "structuredClone", "showOpenFilePicker", "showSaveFilePicker", "scheduler"}
_OPTIONAL_GLOBAL_CALL = re.compile(r"\b(?:self|window|globalThis)\.([A-Za-z_$][\w$]*)\?\.\(")


def test_an_optional_global_call_names_a_real_global():
    """`self.nameMarkBuddyShaken?.(...)` found nothing once companion-throw.js was wrapped in a closure, and
    the optional call hid it: a carried panel silently stopped shaking the companion off (PR 216). A name
    reached this way must be a top-level name of an unwrapped file or one a wrapped file exports."""
    sources = {path.name: strip_js_comments(path.read_text(encoding="utf-8")) for path in sorted(JS.glob("*.js"))}
    top = re.compile(r"(?m)^(?:async\s+)?(?:function\*?\s+|const\s+|let\s+|var\s+|class\s+)([A-Za-z_$][\w$]*)")
    exported = re.compile(r"Object\.assign\(\s*(?:window|self|globalThis)\s*,\s*\{([^}]*)\}")
    assigned = re.compile(r"\b(?:window|self|globalThis)\.([A-Za-z_$][\w$]*)\s*=[^=]")
    reachable = set(_BROWSER_OPTIONAL)
    for text in sources.values():
        reachable.update(top.findall(text))
        reachable.update(assigned.findall(text))
        for block in exported.findall(text):
            reachable.update(re.findall(r"[A-Za-z_$][\w$]*", block))
    lost = sorted(f"{name}: {called}" for name, text in sources.items() for called in _OPTIONAL_GLOBAL_CALL.findall(text)
                  if called not in reachable)
    assert not lost, "optional calls to names no file makes global:\n  " + "\n  ".join(lost)
