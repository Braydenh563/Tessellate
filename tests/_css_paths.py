"""Where the CSS lives, now that it isn't one file.

`frontend/style.css` was split into multiple linked files (ROADMAP.md
Priority 0 item 2: "CSS splitting into multiple linked `<link>` files is
mechanically low-risk"). Every test that used to hardcode
`frontend/style.css` needs the same list, in the same order index.html
loads them in: that order is load-bearing (the split was cut only at
section-comment boundaries, so concatenating these files in this order
reproduces the old single file byte-for-byte, which is what guarantees no
selector's cascade/specificity position moved). One shared list here means
a ninth file, or a reorder, is a one-line change instead of an N-line hunt
through every test that used to open `style.css` directly.

Not named `test_*.py` on purpose: pytest would otherwise try to collect it
and find no tests in it.
"""

from __future__ import annotations

from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
CSS_DIR = FRONTEND_DIR / "css"

#: Matches index.html's <link rel="stylesheet"> order exactly.
CSS_FILES = [
    CSS_DIR / "00-tokens-shell.css",
    CSS_DIR / "01-forms-settings.css",
    CSS_DIR / "02-chat-graph.css",
    #: Linked right after 02 with media="not all"; on only while a motion switch is.
    CSS_DIR / "motion-still.css",
    CSS_DIR / "03-dashboard-widgets.css",
    CSS_DIR / "04-chat-dock-appearance.css",
    CSS_DIR / "05-sidebars-themes.css",
    CSS_DIR / "06-timeline-dialogs.css",
    CSS_DIR / "07-whiteboard-misc.css",
    CSS_DIR / "08-consistency.css",
    #: The documents editor's own layout (DOCUMENTS_PLAN Phase 2). Appended
    #: rather than inserted: it is linked last in index.html, and this list is
    #: load order, which is what makes the concatenation above meaningful.
    CSS_DIR / "09-editor.css",
    CSS_DIR / "10-responsive.css",
    #: Not linked by index.html: loaded with the Library bundle (app.js
    #: `LAZY_MODULES.library`), and so after every file above.
    CSS_DIR / "library-lazy.css",
    #: Loaded with the back/forward list's rows (`LAZY_MODULES.navHistory`).
    CSS_DIR / "nav-history-lazy.css",
    #: Not linked by index.html either: loaded with the icon picker (app.js
    #: `LAZY_MODULES.iconPicker`, MINDMAP_PLAN decision 43), on first open.
    CSS_DIR / "icon-picker.css",
    #: Loaded with "Forgot your password?" and the recovery key
    #: (`LAZY_MODULES.accountRecovery`, INBOX 663).
    CSS_DIR / "recovery-lazy.css",
    #: Tidy's sheet (`LAZY_MODULES.tidy`, INBOX 691).
    CSS_DIR / "tidy-lazy.css",
    #: The Graph tab's late styles (`LAZY_MODULES.graph`, 2026-10-10).
    CSS_DIR / "graph-lazy.css",
    #: The web reader's typography (`LAZY_MODULES` web reader, composer-1025).
    CSS_DIR / "web-lazy.css",
    #: An answer composed from the notes (loaded by ask-compose.js, CHAT_PLAN
    #: decision 33): the quote style of a sentence said from a note.
    CSS_DIR / "ask-compose-lazy.css",
    #: The chat context pill's popover (usage-ledger.js loads it).
    CSS_DIR / "usage-lazy.css",
    #: The Guide's streamed bubble (help-chat.js loads it).
    CSS_DIR / "help-chat-lazy.css",
    #: The chips under a quick-add field (quickadd.js, CHAT_PLAN decision 50).
    CSS_DIR / "quickadd-lazy.css",
    #: The search box's kind chip, Show more and saved-search rows (search.js).
    CSS_DIR / "search-lazy.css",
    #: Atlas's faces at 28 and 20px (atlas.js `atlasSheet`, Brief 34 continues).
    CSS_DIR / "atlas-lazy.css",
    #: The Statistics page and This week (statistics.js, Brief 89).
    CSS_DIR / "utilities-lazy.css",
    #: What the app draws into a reply beside its words (reply-kit.js, INBOX 1300 C06).
    CSS_DIR / "reply-kit-lazy.css",
    #: The live captions dock (captions.js, Brief 82).
    CSS_DIR / "captions-lazy.css",
    #: The Notes tab's Questions view (questions-view.js loads it).
    CSS_DIR / "questions-lazy.css",
    #: The voice-note recorder and Library, Recordings (meetings.js, Brief 80).
    CSS_DIR / "meetings-lazy.css",
    #: The quoted span a source opens at (`LAZY_MODULES.reveal`, Brief 88).
    CSS_DIR / "reveal-lazy.css",
    #: The manual (manual.js loads it, WORLD_CLASS_PLAN 25c).
    CSS_DIR / "manual-lazy.css",
    #: The dashboard's first steps (first-run.js loads it, WORLD_CLASS_PLAN 25c).
    CSS_DIR / "first-run-lazy.css",
    #: The Timeline's calendar (timeline-calendar.js loads it, TIMELINE_PLAN 9).
    CSS_DIR / "timeline-calendar-lazy.css",
    #: Where another device opens the notebook (settings-controls.js, INBOX 867).
    CSS_DIR / "lan-lazy.css",
    CSS_DIR / "objmove-lazy.css",
    #: The storage bar in Settings, About (settings-data.js, data-1011).
    CSS_DIR / "settings-data-lazy.css",
    #: Moved out of the boot sheets for the gzip budget (2026-10-12), each
    #: loaded with its bundle in lazy-entries.js or app.js's LAZY_MODULES.
    CSS_DIR / "improve-lazy.css",
    CSS_DIR / "dash-orphans-lazy.css",
    CSS_DIR / "dash-night-lazy.css",
    CSS_DIR / "inbox-lazy.css",
    CSS_DIR / "lightbox-lazy.css",
    CSS_DIR / "quick-access-lazy.css",
    #: Files dragged in from outside the window (settings-wiring.js's dragenter stub).
    CSS_DIR / "file-drop-lazy.css",
    #: The no-model notice's split button (offline-split.js loads it, INBOX 904 B05).
    CSS_DIR / "offline-split-lazy.css",
    #: The Settings listeners' additions: the theme cards' eye (settings-controls.js).
    CSS_DIR / "settings-controls-lazy.css",
    #: The density strip's year and month labels (timeline-ticks.js loads it).
    CSS_DIR / "timeline-ticks-lazy.css",
    #: Quick sketch, the self-contained pad (media.js `openSketch` loads it).
    CSS_DIR / "sketch-pad.css",
    #: The Notes sidebar's folds (C43).
    CSS_DIR / "sidebar-folds-lazy.css",
    #: The thrown companion's fates (companion-throw.js loads it, D6).
    CSS_DIR / "companion-throw-lazy.css",
    #: The companion's far moves and small acts (companion-travel.js loads it, INBOX 1429).
    CSS_DIR / "companion-travel-lazy.css",
    #: Movable and resizable panels (panel-movable.js loads it, INBOX 1427).
    CSS_DIR / "panel-movable-lazy.css",
    #: The guided equation editor (lazy-entries.js `mathEditor`, DOCUMENTS_PLAN 16).
    CSS_DIR / "math-editor-lazy.css",
    #: Mermaid diagrams: the figure, its placeholder and the hidden frame (mermaid-draw.js).
    CSS_DIR / "mermaid-lazy.css",
    #: Settings, Appearance, Glass controls: icon buttons in glass (lazy-entries.js `glassControls`, INBOX 1409).
    CSS_DIR / "glass-controls-lazy.css",
    #: The Appearance quick panel (lazy-entries.js `appearancePanel`, INBOX 1435): the Settings
    #: rules copied under #appearance-panel (scripts/appearance_panel_css.py), then its own.
    CSS_DIR / "appearance-panel-lazy.css",
    CSS_DIR / "appearance-panel-own-lazy.css",
    #: The update bar (INBOX 1440), loaded by update-dialogs.js when a version is found.
    CSS_DIR / "update-bar-lazy.css",
    #: Windows high contrast only (status.js loads it under forced-colors, audit 1028 S38).
    CSS_DIR / "forced-colors-lazy.css",
    #: The meaning-search notice (app.js `LAZY_MODULES.semanticNotice`).
    CSS_DIR / "semantic-notice-lazy.css",
]


def css_text() -> str:
    """All of CSS_FILES, concatenated in load order.

    Byte-for-byte what `frontend/style.css` used to return from
    `.read_text()`, see the split's own diff, or diff this against a
    `cat`'d concatenation of CSS_FILES, to confirm.
    """
    return "".join(p.read_text(encoding="utf-8") for p in CSS_FILES)
