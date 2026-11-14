"""Where the app's own code lives, now that app.js is being split.

`frontend/js/app.js` was one file of 50,000 lines. The split (INBOX 426 cc,
`docs/roadmap/archive/agent-remaining/appjs-split.md`) cuts it into classic scripts
loaded in its own order, each a contiguous range of the old file, so
concatenating them in index.html's order reproduces the old app.js (less
the two blocks the plan moves on purpose). A test that read app.js to find a
function or a table means "the app's code", and reads `app_js_text()` now;
a test that means the file app.js itself (the lazy loader's tables, which
stay there) keeps reading `APP_JS`.

The list is read from index.html, not written here: every local script from
`/js/app.js` through `/js/agent-activity.js` (the first piece split out, in
5b1f809) in the order the page loads them. A new file added to the page in
that stretch is in the list without an edit here, which is the point.

Not named `test_*.py` on purpose, as `_css_paths.py`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from tests._js_scope import unwrapped

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
#: The scripts live in `frontend/js/` (2026-10-03); `sw.js` alone stays at the
#: frontend root, because a service worker only controls pages under its own path.
JS_DIR = FRONTEND_DIR / "js"
APP_JS = JS_DIR / "app.js"
INDEX_HTML = FRONTEND_DIR / "index.html"

FIRST = "app.js"
LAST = "agent-activity.js"


def app_js_files() -> list[Path]:
    """The app's scripts in load order, from app.js to agent-activity.js."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    names = re.findall(r'<script src="/js/([A-Za-z0-9_.-]+\.js)', html)
    start = names.index(FIRST)
    end = names.index(LAST)
    return [JS_DIR / name for name in names[start : end + 1]]


#: Pieces of the app's code moved out of the boot scripts to load on first use
#: (app.js, `LAZY_MODULES`). Still the app's code for every test that reads
#: it, so `app_js_text` includes them; not in `app_js_files`, which is what
#: loads at boot and what the gzip budget counts.
LAZY_PIECES = ("panel-movable.js", "notes-lazy.js", "lightbox-view.js", "edit-conflict.js", "categories-panel.js", "tag-manager.js", "chip-menus.js", "note-history.js", "ask-history.js", "settings-data.js", "meaning.js", "settings-find.js", "settings-models.js", "tag-suggest.js", "search-suggest.js", "chat-ghost.js", "sketch-pad.js", "writing-desk.js", "attachment-actions.js", "ocr-engine.js", "quick-note.js", "quick-access.js", "field-clear.js", "date-field.js", "assistant-avatar.js", "suggestions-inbox.js", "entity-page.js", "link-types.js", "note-properties.js", "reveal-targets.js", "onboarding.js", "update-dialogs.js", "app-palette.js", "note-panels.js", "settings-controls.js", "settings-prefs.js", "note-edit-panels.js", "attach-to.js", "notes-rail-spy.js", "dash-boards.js", "model-bench.js", "web-clip.js", "app-import.js", "usage-ledger.js", "chord-guide.js", "note-templates.js", "atlas-motion.js", "atlas-micro.js", "help-chat.js", "mermaid-draw.js", "code-colour.js","settings-packages.js", "batch-space.js", "atlas-life.js", "companion-menu.js", "companion-settings.js", "drag-edge.js", "pick-row.js", "vault-unlock.js", "nav-history.js", "icon-picker.js", "note-pick-preview.js", "tour.js", "questions-view.js", "ask-compose.js", "meetings.js", "chat-edit.js", "quickadd.js", "search.js", "statistics.js", "utility-tools.js", "captions.js", "translate.js", "app-features.js", "chat-undo.js", "web-results.js", "chat-private.js", "chat-time.js", "notifications.js", "shared-intake.js", "undo-kit.js", "connections.js", "timeline-calendar.js", "timeline-cal-add.js", "timeline-detail.js", "task-steps.js", "chat-tasks.js", "improve-panel.js", "lightbox-actions.js", "settings-health.js", "dash-orphans.js", "dash-night.js", "personas-pane.js", "dash-day.js", "library-pick.js", "feature-model-sheet.js", "status-panels.js", "phone-more.js", "gesture-kit.js", "load-failed.js", "reminder-edit.js", "image-layout.js", "obj-ref.js", "obj-order.js", "obj-drag.js", "obj-reorder.js", "obj-clip.js", "obj-carry.js", "obj-tray.js", "popup-glyph.js", "capture-card.js", "capture-card-more.js", "capture-stage.js", "attach-accept.js", "chat-docs.js", "chat-turn.js", "entry-menu.js", "answer-kit.js", "map-preview.js", "citation-peek.js", "space-swap.js", "table-block.js", "entry-card.js", "dash-art.js", "scroll-row.js", "confirmed-patterns.js", "value-field.js", "studio.js", "sync-folder.js", "ndjson-read.js")


@lru_cache(maxsize=1)
def _joined() -> str:
    paths = [*app_js_files(), *(JS_DIR / name for name in LAZY_PIECES)]
    return "\n".join(unwrapped(path.read_text(encoding="utf-8")) for path in paths)


def app_js_text() -> str:
    """The app's code: every file in `app_js_files()`, joined in load order."""
    return _joined()


#: Pieces moved out of a boot script into lazy files (2026-10-12, the gzip
#: budget): a test that reads the boot file by name also means these.
MOVED_OUT = {
    "ai-tools.js": ("task-steps.js", "chat-tasks.js", "improve-panel.js", "feature-model-sheet.js", "gesture-kit.js", "answer-kit.js"),
    "menus.js": ("gesture-kit.js", "entry-menu.js"),
    "notes-list.js": ("notes-lazy.js",),
    "note-cards.js": ("map-preview.js", "entry-card.js"),
    "markdown.js": ("table-block.js",),
    "sheets-selects.js": ("personas-pane.js", "gesture-kit.js"),
    "lightbox.js": ("lightbox-actions.js",),
    "settings.js": ("settings-health.js", "settings-controls.js"),
    "selection.js": ("library-pick.js",),
    "dashboard.js": ("dash-day.js", "dash-night.js", "dash-orphans.js", "app-features.js", "dash-art.js"),
    "navigation.js": ("load-failed.js",),
    "settings-panes.js": ("app-features.js",),
    "chat-attach.js": ("chat-turn.js", "answer-kit.js", "chat-docs.js"),
    "chat-agent.js": ("chat-turn.js", "answer-kit.js"),
    "chat.js": ("chat-turn.js", "answer-kit.js"),
    "capture-ask.js": ("ask-compose.js", "answer-kit.js", "citation-peek.js"),
    "agent-activity.js": ("answer-kit.js",),
    "status.js": ("status-panels.js", "answer-kit.js"),
    "wiring.js": ("answer-kit.js",),
    "skills.js": ("answer-kit.js", "settings-controls.js"),
    "shell-reminders.js": ("scroll-row.js",),
}


def with_pieces(name: str) -> str:
    """A boot script's text plus the lazy files its code moved into."""
    parts = [unwrapped((JS_DIR / name).read_text(encoding="utf-8"))]
    parts += [unwrapped((JS_DIR / piece).read_text(encoding="utf-8")) for piece in MOVED_OUT.get(name, ())]
    return "\n".join(parts)


def frontend_text(name: str) -> str:
    """A frontend script's text by name, where "app.js" means the app's code
    (every piece of it), for the tests that read files by name in a loop."""
    if name == FIRST:
        return app_js_text()
    if name in MOVED_OUT:
        return with_pieces(name)
    path = JS_DIR / name
    if not path.exists():  # sw.js, the one script that stays at the root
        path = FRONTEND_DIR / name
    return unwrapped(path.read_text(encoding="utf-8"))


def script_file_text(name: str) -> str:
    """A script as written, wrapper and all: the scope tests ask whether the file is one closure,
    which `frontend_text` hides by unwrapping."""
    return (JS_DIR / name).read_text(encoding="utf-8")


def app_js_family(path: Path) -> bool:
    """Whether a frontend file is one of the pieces of the old app.js, for
    the lints that count or allow things per file."""
    pieces = [*app_js_files(), *(JS_DIR / name for name in LAZY_PIECES)]
    return path.resolve() in {p.resolve() for p in pieces}


#: lazy-entries.js (2026-10-12) extends app.js's two loader tables, because
#: app.js is at its boot cap: `Object.assign(LAZY_MODULES, {...})` and
#: `installStandIns({...})`. A test that reads the bundles or the stand-ins
#: means both files.
LAZY_ENTRIES = JS_DIR / "lazy-entries.js"


def _block(text: str, opener: str, closer: str) -> str:
    start = text.index(opener)
    return text[start : text.index(closer, start)]


def lazy_modules_source() -> str:
    """Every `LAZY_MODULES` row: app.js's table, lazy-entries.js's, then the one documents-mermaid.js adds."""
    app = APP_JS.read_text(encoding="utf-8")
    extra = LAZY_ENTRIES.read_text(encoding="utf-8")
    builder = (JS_DIR / "documents-mermaid.js").read_text(encoding="utf-8")
    return (
        _block(app, "const LAZY_MODULES = {", "\n};\n")
        + "\n"
        + _block(extra, "Object.assign(LAZY_MODULES, {", "\n});\n")
        + "\n"
        + _block(builder, "Object.assign(LAZY_MODULES, {", "});\n")
    )


def stand_ins_source() -> str:
    """Every stand-in row: app.js's `LAZY_ENTRY_POINTS`, then lazy-entries.js's."""
    app = APP_JS.read_text(encoding="utf-8")
    extra = LAZY_ENTRIES.read_text(encoding="utf-8")
    return _block(app, "const LAZY_ENTRY_POINTS = {", "\n};\n") + "\n" + _block(extra, "installStandIns({", "\n});\n")


#: documents.js and the pieces split out of it that hold part of the editor's
#: own text (`docLivePlugin`, `docCmTheme`; audit 1031 DC13): a test that means
#: "the documents editor's code" reads them joined, so a piece moving between
#: these files does not move its tests.
DOCUMENTS_PIECES = ("documents.js", "documents-cm.js", "documents-cm-theme.js", "documents-replace.js", "documents-export.js", "documents-ai.js", "documents-history.js", "documents-props.js", "documents-mermaid.js", "documents-math.js", "documents-comments.js", "documents-embeds.js", "documents-tables.js", "documents-columns.js", "documents-print.js", "documents-spell.js", "documents-languagetool.js", "documents-outline.js", "documents-callouts.js", "documents-view.js")


def documents_text() -> str:
    return "\n".join((JS_DIR / name).read_text(encoding="utf-8") for name in DOCUMENTS_PIECES)
