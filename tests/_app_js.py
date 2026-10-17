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
LAZY_PIECES = ("lightbox-view.js", "edit-conflict.js", "categories-panel.js", "tag-manager.js", "chip-menus.js", "note-history.js", "ask-history.js", "settings-data.js", "meaning.js", "settings-find.js", "settings-models.js", "tag-suggest.js", "search-suggest.js", "sketch-pad.js", "writing-desk.js", "attachment-actions.js", "ocr-engine.js", "quick-note.js", "quick-access.js", "field-clear.js", "date-field.js", "assistant-avatar.js", "suggestions-inbox.js", "entity-page.js", "link-types.js", "note-properties.js", "reveal-targets.js", "onboarding.js", "update-dialogs.js", "app-palette.js", "note-panels.js", "settings-controls.js", "note-edit-panels.js", "attach-to.js", "notes-rail-spy.js", "dash-boards.js", "model-bench.js", "web-clip.js", "app-import.js", "usage-ledger.js", "chord-guide.js", "note-templates.js", "atlas-motion.js", "help-chat.js", "settings-packages.js", "batch-space.js", "atlas-life.js", "companion-menu.js", "drag-edge.js", "pick-row.js", "vault-unlock.js", "nav-history.js", "icon-picker.js", "note-pick-preview.js", "tour.js", "questions-view.js", "ask-compose.js", "meetings.js", "chat-edit.js", "quickadd.js", "search.js", "statistics.js", "utility-tools.js", "captions.js", "translate.js", "app-features.js", "chat-undo.js", "chat-time.js", "notifications.js", "shared-intake.js", "undo-kit.js", "connections.js", "timeline-calendar.js", "timeline-cal-add.js", "timeline-detail.js", "chat-tasks.js", "improve-panel.js", "lightbox-actions.js", "settings-health.js", "dash-orphans.js", "dash-night.js", "personas-pane.js", "dash-day.js", "library-pick.js", "feature-model-sheet.js", "status-panels.js")


@lru_cache(maxsize=1)
def _joined() -> str:
    paths = [*app_js_files(), *(JS_DIR / name for name in LAZY_PIECES)]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def app_js_text() -> str:
    """The app's code: every file in `app_js_files()`, joined in load order."""
    return _joined()


#: Pieces moved out of a boot script into lazy files (2026-10-12, the gzip
#: budget): a test that reads the boot file by name also means these.
MOVED_OUT = {
    "ai-tools.js": ("chat-tasks.js", "improve-panel.js", "feature-model-sheet.js"),
    "lightbox.js": ("lightbox-actions.js",),
    "settings.js": ("settings-health.js",),
    "sheets-selects.js": ("personas-pane.js",),
    "selection.js": ("library-pick.js",),
    "status.js": ("status-panels.js",),
    "dashboard.js": ("dash-day.js", "dash-night.js", "dash-orphans.js"),
}


def with_pieces(name: str) -> str:
    """A boot script's text plus the lazy files its code moved into."""
    parts = [(JS_DIR / name).read_text(encoding="utf-8")]
    parts += [(JS_DIR / piece).read_text(encoding="utf-8") for piece in MOVED_OUT.get(name, ())]
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
    return path.read_text(encoding="utf-8")


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
    """Every `LAZY_MODULES` row: app.js's table, then lazy-entries.js's."""
    app = APP_JS.read_text(encoding="utf-8")
    extra = LAZY_ENTRIES.read_text(encoding="utf-8")
    return _block(app, "const LAZY_MODULES = {", "\n};\n") + "\n" + _block(extra, "Object.assign(LAZY_MODULES, {", "\n});\n")


def stand_ins_source() -> str:
    """Every stand-in row: app.js's `LAZY_ENTRY_POINTS`, then lazy-entries.js's."""
    app = APP_JS.read_text(encoding="utf-8")
    extra = LAZY_ENTRIES.read_text(encoding="utf-8")
    return _block(app, "const LAZY_ENTRY_POINTS = {", "\n};\n") + "\n" + _block(extra, "installStandIns({", "\n});\n")
