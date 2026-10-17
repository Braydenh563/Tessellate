"""A boot-loaded file may not quietly depend on a file that loads later.

`index.html` loads six scripts: app.js, editor.js, dashboard.js, timeline.js,
settings.js and tour.js. Everything else, graph.js and graph-canvas.js, documents.js
(with documents-code.js and documents-prose.js, split out of it), whiteboard.js
(with whiteboard-map.js) and library.js, is in a lazy bundle (`LAZY_MODULES`, app.js) and
arrives only when a tab asks for it. So a boot file that calls a function
defined only in a lazy file is calling something that is not there yet, and
what happens then depends entirely on how the call is written:

* a bare call throws `ReferenceError`, which is loud and gets fixed;
* a call through a `LAZY_ENTRY_POINTS` stand-in fetches the bundle and works;
* **a call behind `typeof x === "function"` does nothing at all, silently.**

The third is the one this file exists for, and it has already cost a feature.
`editor.js`'s `editorSurfaceFor` read

    if (typeof asSurface !== "function") return null;

with a comment saying the case "cannot happen in the browser (the script order
is fixed)". The script order stopped being fixed when documents.js joined the
Library's bundle, and nothing said so. The result, measured on the branch head
2026-09-21: typing "/" in the note capture box opened 0 menu rows, and the same
in the note edit box, the chat composer and the skill steps box. Four of the
five surfaces the "/" menu exists for did nothing, on every fresh load, until
the person happened to open Library or Documents. It is CLAUDE.md section 6's
fourth shape, a policy silently refusing the work, wearing a comment that says
it cannot.

So every such call is listed here, once, with what makes it safe. Adding a name
to a boot file that only a lazy file defines fails this test until somebody
says which of the three it is.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

#: Read off index.html rather than repeated here, so a script added to the page
#: is a script this test knows is loaded.
def _boot_scripts() -> list[str]:
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    names = []
    for src in re.findall(r'<script src="/js/([A-Za-z0-9._-]+\.js)', html):
        if (FRONTEND / "js" / src).exists():
            names.append(src)
    return names


def _lazy_files() -> dict[str, list[str]]:
    """`LAZY_MODULES` as written in app.js: bundle name to its files."""
    source = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"const LAZY_MODULES = \{(.*?)\n\};", source, re.S)
    assert block, "LAZY_MODULES not found in app.js; has the loader moved?"
    out: dict[str, list[str]] = {}
    for name, files in re.findall(r"^\s*(\w+):\s*\[(.*?)\],", block.group(1), re.M | re.S):
        out[name] = re.findall(r'"/js/([A-Za-z0-9._-]+\.js)"', files)
    return out


def _entry_points() -> dict[str, set[str]]:
    source = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"const LAZY_ENTRY_POINTS = \{(.*?)\n\};", source, re.S)
    assert block, "LAZY_ENTRY_POINTS not found in app.js"
    out: dict[str, set[str]] = {}
    #: `\],?` rather than `\],\n`: the last bundle in the object has no
    #: newline after its closing bracket inside the captured block, and the
    #: first draft of this parser silently returned an empty set for it,
    #: which made the whole test fire on names that were listed all along.
    for name, names in re.findall(r"^\s*(\w+):\s*\[(.*?)\]", block.group(1), re.M | re.S):
        out[name] = set(re.findall(r'"(\w+)"', names))
    return out


def _top_level_functions(path: Path) -> set[str]:
    """Only functions declared at column zero: a nested helper is not a global."""
    source = path.read_text(encoding="utf-8")
    return set(re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)", source, re.M))


def _declared_anywhere(path: Path) -> set[str]:
    """Every function declaration in the file, nested ones included.

    A boot file's own nested helper shadows a lazy file's global of the same
    name inside the scope that declares it, so a call there is not a
    cross-bundle call at all. `app.js` has a `bookmarkRow` inside the
    Connections builder and `library.js` has a different one at top level;
    reading only column zero made the first look like a call to the second.
    """
    source = path.read_text(encoding="utf-8")
    return set(re.findall(r"(?:^|\s)(?:async )?function ([A-Za-z_$][\w$]*)\s*\(", source))


#: Names whose call sites are reached only after the bundle they belong to has
#: been loaded, with the reason each one is safe. A name here is a promise that
#: somebody checked the path, not a way to quiet the test.
REACHED_AFTER_LOAD = {
    #: Settings, About, Maintenance: settings.js's showSettingsSection calls it
    #: in the .then of ensureModule('settingsControls').
    "renderMaintenance": "settingsControls, called in the .then of ensureModule('settingsControls') in showSettingsSection",
    #: B56: the Auto labels. The bundle labels itself on load (its last lines),
    #: so a render that ran before it arrived loses nothing; the guarded calls
    #: only keep the labels current after that.
    "renderAutoChoices": "settingsControls, paints itself at the end of the file; later renders re-label",
    #: B14: the pane's Expand all. openSettingsModal awaits settingsControls
    #: before the window is shown, so showSettingsSection never runs ahead of it.
    "ensureSettingsFoldAll": "settingsControls, the Settings window awaits it before any pane is shown",
    "renderSmallModelAuto":"settingsControls, paints itself at the end of the file; later renders re-label",
    #: The history row's Logs button: it sits in Settings, whose window loads settingsControls first.
    "openTaskLog": "settingsControls, the Settings window awaits it before any row in it can be pressed",
    #: Background jobs, Report: the click awaits ensureModule('appImport') first.
    "openImportReport": "appImport, called after `await ensureModule('appImport')` in the Report button's click",
    #: Connections, opened in the .then of lazyScript('/js/connections.js') at its three callers.
    "openConnections": "connections, called in the .then of lazyScript('/js/connections.js')",
    #: The palette's Translate this row, in the .then of ensureModule('translate').
    "translateCaught": "translate, called in the .then of ensureModule('translate') on its palette row",
    #: Brief 88: a source opens its note at the quoted line, in the .then of
    #: ensureModule('reveal') in capture-ask.js's openNoteAtPassage.
    "markNotePassage": "reveal, called in the .then of ensureModule('reveal') in openNoteAtPassage",
    #: Decision 70: the digest answer's one offer, in the .then of
    #: ensureModule('askCompose') in renderAnswerGrounding.
    "digestOffer": "askCompose, called in the .then of ensureModule('askCompose') in renderAnswerGrounding",
    "digestShape": "askCompose, called in the .then of ensureModule('askCompose') in renderAnswerGrounding",
    "digestMore": "askCompose, called in the .then of ensureModule('askCompose') in renderAnswerGrounding",
    #: The answer's foot (B12, B30, B31, decision 73, follow-ups), moved out of
    #: capture-ask.js to keep the boot scripts under their ratchet.
    "citationVerdictRow": "askCompose, called in the .then of ensureModule('askCompose') in openCitationPeek",
    "askAnswerMenu": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "renderAskInsights": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "renderAskWhy": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "renderAskFollowups": "askCompose, passed to the .then of ensureModule('askCompose') in askQuestion",
    #: B12: an answer's mind map is tidied after `await openWhiteboardBoard`,
    #: which loads the library bundle first (askKeepAsMap, capture-ask.js).
    "wbMapTidyFresh": "library, called after await openWhiteboardBoard in askKeepAsMap's Open",
    #: Brief bootdiet: the catalogue is in the palette's bundle, and every other
    #: reader (Tools and features, Quick access, startApp's recovered recordings)
    #: awaits `lazyScript` / `ensureModule` before it reads or calls.
    "featureCatalog": "appPalette, the palette's bundle names it; openFeatures and renderQuickLinks await lazyScript('/js/app-features.js') first",
    "noteRecoveredRecordings": "meetings, called in the .then of ensureModule('meetings') in dashboard.js's startApp hook",
    #: INBOX 784: the Notes column's rows are drawn by connections.js;
    #: renderNotesRail awaits lazyScript('/js/connections.js') before any of them.
    "withBacklinks": "connections, renderNotesRail awaits lazyScript('/js/connections.js') before drawing",
    "buildConnectionGroups": "connections, renderNotesRail awaits lazyScript('/js/connections.js') before drawing",
    "connectionRowEl": "connections, notesRailNearGroup runs inside renderNotesRail after it awaited the bundle",
    #: Brief 89: the palette's small tools, each called in the .then of
    #: ensureModule('utilities') on its own palette row (settings-panes.js).
    "startUtilityTimer": "utilities, called in the .then of ensureModule('utilities') on the palette's timer rows",
    "startStopwatch": "utilities, called in the .then of ensureModule('utilities') on the palette's stopwatch row",
    "countSelection": "utilities, called in the .then of ensureModule('utilities') on the palette's Count words row",
    #: Brief 47: the findAnything shortcut closes the box only while
    #: #finder-overlay is shown, and only openFinder (the same bundle) shows it.
    "closeFinder": "search, the findAnything shortcut, only while the box openFinder drew is open",
    #: chat.js moved these out for the boot gzip ratchet (2026-10-10); each
    #: is called in the `.then` of its own `ensureModule` on the same line.
    "renderChatContextPop": "usageLedger, called in the .then of ensureModule('usageLedger') in renderChatContextMeter",
    "showWebReader": "webClip, called in the .then of ensureModule('webClip') in openWebReader",
    "askAgainMenu": "askHistory, called in the .then of ensureModule('askHistory') in loadRecentQuestions",
    "answerSuggestedTags": "tagSuggest, called in the .then of ensureModule('tagSuggest') by answerTags",
    "openNoteTagPopover": "tagSuggest, called in the .then of ensureModule('tagSuggest') by the \"+ Tag\" chip (note-cards.js)",
    "settingsPrefsSeen": "settingsData, called in the .then of ensureModule('settingsData') by the apiJson wrapper (status.js)",
    "clearRecentSearches": "searchSuggest, called in the .then of ensureModule('searchSuggest') by the web panel's Clear (chat.js)",
    "renderSettingsHistory": "settingsData, called in the .then of ensureModule('settingsData') when Data opens (settings.js)",
    "renderSettingsClear": "settingsData, called in the .then of ensureModule('settingsData') when Data opens (settings.js)",
    "renderStorageBreakdown": "settingsData, called in the .then of ensureModule('settingsData') when About's health block draws (settings.js)",
    "openSearchSuggest": "searchSuggest, called in the .then of ensureModule('searchSuggest') by the focus listener (capture-ask.js)",
    "questionsForNote": "questionsView, called in the .then of ensureModule('questionsView') by a card's question count",
    "webFollowUp": "webClip, called in sendChatMessage after `await ensureModule('webClip')` in the same condition",
    "readerBookmark": "webClip, the reader's bookmark button, whose listener awaits ensureModule('webClip') first",
    #: Brief 84: a Chat answer's bar of counts, drawn in the .then of its ensureModule.
    "drawAskChart": "askHistory, called in the .then of ensureModule('askHistory') in the chat's onChart",
    "saveWebPageAsNote": "webClip, the reader's Save button, on screen only after showWebReader (same bundle) drew a page",
    "dateFieldWire": "dateField, called in enhanceDateField's first press after `await ensureModule('dateField')` in the same condition",
    #: WORLD_CLASS_PLAN section 17 row 4: called inside
    #: `ensureModule("askHistory").then(...)` in `askQuestion`, so the bundle
    #: has loaded by the time the call runs.
    #: nav-history.js (INBOX 654): `openNavHistoryMenu` awaits
    #: `ensureModule("navHistory")` and returns when it failed, so the render
    #: runs only once the bundle is in.
    "renderNavHistoryMenu": "navHistory, called by openNavHistoryMenu after awaiting ensureModule('navHistory')",
    #: INBOX 644: saveMeetingNote (media.js) awaits ensureModule("meetings")
    #: and calls only when it loaded, as openNavHistoryMenu does.
    "meetingSaveTranscript": "meetings, called by saveMeetingNote after awaiting ensureModule('meetings')",
    #: Brief 101a: the recorder's Escape (settings-wiring.js) runs only while
    #: `#meeting-overlay` is showing, and meetings.js is what shows it.
    "closeMeetingRecorder": "meetings, the Escape handler in settings-wiring.js runs it only while #meeting-overlay is open, which only meetings.js opens",
    "renderAskChart": "askHistory, called from ensureModule('askHistory').then in askQuestion",
    #: The 2026-10-10 triage: a composed answer's cited names are linked
    #: once ask-compose.js is in (`addInlineCitations`, capture-ask.js).
    "linkCitedTitles": "askCompose, called from ensureModule('askCompose').then in addInlineCitations",
    "markSaidSentences": "askCompose, called beside linkCitedTitles in the same ensureModule('askCompose').then",
    "renderActCard": "askCompose, called from ensureModule('askCompose').then in renderToolConfirm (chat-agent.js)",
    "renderWebSources": "askCompose, called from ensureModule('askCompose').then in chat-attach's onWebSources",
    #: The Escape handler (settings-wiring.js) closes the welcome card only
    #: when `#onboarding-overlay` is showing, and the only thing that shows it
    #: is `openOnboarding`, whose stand-in loads the bundle first.
    #: The same for the palette: `closePalette` is called (Escape, the chord's
    #: toggle, a chord that closes overlays) only while `#palette-overlay` is
    #: showing, and only `openPalette`, whose stand-in loads the bundle, shows it.
    "closePalette": "appPalette, called only while the palette overlay is showing, and only openPalette shows it",
    #: `openNoteEditor` drops the copy of an edit kept on this device
    #: (note-edit-panels.js). Only that bundle writes one, so before it loads
    #: there is nothing this session kept to drop; a copy from an earlier
    #: session is still unsaved work, offered back when the bundle arrives.
    "forgetNoteEditLocally": "notePanels, only its own edit form keeps a copy, and an older copy is meant to survive",
    "closeOnboarding": "onboarding, called on Escape only while the overlay is open, and only openOnboarding opens it",
    #: Capture's staged-files list asks the clear button to re-sync when it
    #: redraws (audit 2026-10-05, FE-18). Before the fieldClear bundle is in,
    #: there is no button wiring to sync, and the bundle syncs every button
    #: itself the moment it loads, so a no-op here loses nothing.
    "fieldClearSyncAll": "fieldClear, which syncs every button itself when it loads",
    #: dash-boards.js (INBOX 553(d)): `renderBoardsWidget` awaits
    #: `ensureModule("dashBoards")` on the line and calls only when it loaded.
    "dashRenderBoards": "dashBoards, awaited by renderBoardsWidget on the same line",
    #: atlas-life.js: `atlasFigure` calls these in the `.then` of
    #: `ensureModule("atlasLife")`, and only when it loaded; `atlasTailWake`
    #: (atlas.js) reaches `atlasTailFrame` only through a tail that
    #: `atlasTailAttach` made, which is in the same bundle.
    "atlasTailAttach": "atlasLife, called in the .then of ensureModule('atlasLife') when it loaded",
    "atlasRingLoops": "atlasLife, called in the .then of ensureModule('atlasLife') when it loaded",
    "atlasPropLoops": "atlasLife, called in the .then of ensureModule('atlasLife') when it loaded",
    "atlasRigLowerAttach": "atlasLife, called in the .then of ensureModule('atlasLife') when it loaded",
    "atlasRigLower": "atlasLife, called by the rig only once rig.lower exists, which atlasRigLowerAttach (same bundle) makes",
    "atlasTailFrame": "atlasLife, reached only through a tail atlasTailAttach (same bundle) made",
    #: The settingsUi bundle (settings-find.js) is awaited by `openSettingsModal`
    #: before it shows any section, and every call below runs from a section
    #: that is on screen or a search field inside the open dialog. With the
    #: bundle absent (a failed fetch) Settings keeps its nav, the section filter
    #: and the arrow keys, and these index and result extras are simply not
    #: drawn, which is the intended degradation.
    "settingsIndexWatchSection": "settingsUi, awaited by openSettingsModal before a section is shown",
    "renderHelpTopics": "settingsUi, awaited by openSettingsModal on the line before the call",
    "renderCredits": "settingsUi, awaited by openSettingsModal two lines before the call",
    "renderSettingResults": "settingsUi, called from the search field inside the open dialog",
    "settingQueryAlts": "settingsUi, called from filterSettings, the search field inside the open dialog (an empty query returns before it)",
    "meaningHolds": "settingsUi (meaning.js), called from filterSettings beside settingQueryAlts; without the bundle the plain substring rule runs",
    "settingResultsKey": "settingsUi, called from the search field inside the open dialog",
    "renderSuggested": "settingsUi, called from the status poll only while Settings is open (renderSettings), and Settings awaits the bundle first",
    #: The installed models moved beside it (op4-1005): the same poll branch,
    #: the same reason; the box is hidden until a call draws it.
    "renderInstalledModels": "settingsUi, beside renderSuggested in the same status-poll branch, and Settings awaits the bundle first",
    #: editConflictPrompt's Compare awaits `ensureModule("library")` on the
    #: line before, so the diff builder is in the page when it is called.
    "docRenderDiff": "library, called by editConflictPrompt only after it awaits ensureModule('library')",
    "docDiffLines": "library, called by editConflictPrompt only after it awaits ensureModule('library')",
    "docFileType": "library, read by the selection bar only when the surface is `doc-content`, which exists only once the documents bundle has drawn it",
    #: The tab dispatch itself: `switchTab` awaits `ensureModule(TAB_MODULES[tab])`
    #: before it runs any of these, so by the time they are called the bundle is
    #: in the page. They are the bundle's own render entry points.
    "renderLibrary": "library, called from the Library tab's own dispatch",
    "renderLibraryFilters": "library, called from the Library tab's own dispatch",
    "loadLibrary": "library, called from the Library tab's own dispatch",
    #: switchTab stops the media poll on leaving the Library (INBOX 424). The
    #: poll can only have been started by library.js, so while the bundle is
    #: not loaded there is nothing to stop and the guarded no-op is correct.
    "stopLibraryImagesPoll": "library, a poll only library.js can have started",
    "startLibraryImagesPoll": "library, restarted only when its sub-tab (drawn by library.js) is showing",
    "graphLayout": "graph, called from the Graph tab's own dispatch",
    "fitGraphToView": "graph, called from the Graph tab's own dispatch",
    "setGraphPhysicsEnabled": "graph, called from the Graph tab's own dispatch",
    "applyGraphHighlight": "graph, called from the Graph tab's own controls",
    "graphShowNote": "graph, called by showNoteInGraph after `await switchTab(\"graph\")`",
    "showTopicInGraph": "graph, called by a note card's topic chip after `await switchTab(\"graph\")`",
    "toggleGraphFullscreen": "graph, called only while #graph-card is already full screen, which only graph.js can have made it",
    "wbOwnsChord": "library, asked by the global shortcut handler; with the bundle absent no board is open, so no chord can be the board's and the guard's false is the right answer",
    "openLibraryItem": "library, called from a row the Library itself drew",
    "renderDocPreview": "library, called from the document editor's own update path",
    "mountNoteSurface": "library, called once the note engine setting has loaded it",
    #: focusCaptureBox (capture-ask.js): with the bundle absent no editor view
    #: is mounted over the capture box, so focusing the textarea itself, the
    #: guarded fallback, is the right thing rather than a silent no-op.
    #: setNoteSource (wiring.js): only a mounted box can be switched, and a box
    #: mounts only with the bundle in; one mounted later reads the choice.
    "setNoteSurfaceSource": "library, a mounted editor view exists only once the bundle is in; a later mount reads the remembered choice",
    "noteSurfaceFor": "library, a mounted editor view exists only once the bundle is in; without it the textarea fallback runs",
    "docSurfaceById": "library, called from the document editor's own handlers",
    "docPaletteCommands": "library, the palette asks only once documents.js is in",
    "docEventFromCm": "library, only ever true when CodeMirror is mounted",
    "gcRequestDraw": "graph, the canvas renderer's own frame loop",
    "gcStop": "graph, the canvas renderer's own teardown",
    "renderDocShortcutSheet": "library, the document editor's own sheet",
    "wbPaletteCommands": "library, the palette's board group: with the bundle absent no board is open, so no board command applies and the guard's empty list is the right answer",
    "renderWbShortcutSheet": "library, the board's section of the sheet, which says to open a board once while the bundle is absent",
    "wbCommandsLive": "library, asks whether a board is on screen; with the bundle absent none is, so the guard's false is the right answer",
    "wbOpenHelpSheet": "library, called by '?' only when wbCommandsLive() says a board is on screen, which needs the bundle in; otherwise the app's sheet opens",
    "wireMdFormatShortcuts": "library, wired when the document editor mounts",
    "hideDocComplete": "library, the document editor's word list; with the bundle absent there is no list on screen to hide, so the guard's no-op is the right answer",
    "docMathRender": "library; `mdMathElement` (app.js) shows the formula's source when it is absent and calls `ensureModule(\"library\")` to redraw the block once the bundle lands, so the guard is a first frame, not a silent no-op",
    #: The catalogue reveals (app.js, REVEAL_TARGETS): each is called only
    #: after `revealBoard` or the target itself has awaited the bundle.
    "wbIsMap": "library, asked by revealBoard after `await ensureModule(\"library\")`",
    "wbExportBoard": "library, called by the board-export reveal once revealBoard has opened a board",
    "openGraphPopup": "graph, called by the graph-edit reveal after `await ensureModule(\"graph\")`",
    "setDocView": "library, called by the doc-find reveal once revealDocument has opened a document",
    "docToolbarCollapsed": "library, asked by revealStrip after `await ensureModule(\"library\")`",
    "setDocToolbarCollapsed": "library, called by revealStrip after `await ensureModule(\"library\")`",
    #: Generic names that a lazy file happens to declare too. The call in the
    #: boot file is to its own local of the same name, not across the bundle.
    "build": "a local name in more than one file, not a cross-bundle call",
    "place": "a local name in more than one file, not a cross-bundle call",
    "sync": "a local name in more than one file, not a cross-bundle call",
    #: Fetched on focus and replayed, rather than stood in for: a stand-in is
    #: async and this has to answer synchronously. See `editorEnsureSurfaceModule`
    #: in editor.js, which is the fix for the fault this whole file records.
    "asSurface": "editor.js warms the bundle on focus and replays the keystroke",
}

GUARD = re.compile(r'typeof\s+(\w+)\s*===?\s*["\']function["\']')


def test_no_boot_file_silently_depends_on_a_lazy_bundle():
    lazy = _lazy_files()
    entries = _entry_points()
    boot = _boot_scripts()
    assert "app.js" in boot and "editor.js" in boot, f"boot scripts look wrong: {boot}"

    boot_defined: set[str] = set()
    for name in boot:
        boot_defined |= _declared_anywhere(FRONTEND / "js" / name)

    lazy_defined: dict[str, str] = {}
    for bundle, files in lazy.items():
        for file_name in files:
            for symbol in _top_level_functions(FRONTEND / "js" / file_name):
                lazy_defined.setdefault(symbol, bundle)

    candidates = {s: b for s, b in lazy_defined.items() if s not in boot_defined}
    assert candidates, "no cross-bundle names at all; has the scan broken?"
    call = re.compile(r"(?<![\w$.])(" + "|".join(sorted(map(re.escape, candidates))) + r")\s*\(")

    unaccounted: list[str] = []
    for name in boot:
        lines = (FRONTEND / "js" / name).read_text(encoding="utf-8").split("\n")
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            for match in call.finditer(line):
                symbol = match.group(1)
                bundle = candidates[symbol]
                if symbol in entries.get(bundle, set()):
                    continue
                if symbol in REACHED_AFTER_LOAD:
                    continue
                #: A `typeof` guard in the four lines above is exactly the shape
                #: that fails silently, so it does NOT make a call safe here. It
                #: only tells us the author knew, which is why the message says
                #: so rather than passing.
                context = "\n".join(lines[max(0, number - 5):number])
                guarded = symbol in GUARD.findall(context)
                unaccounted.append(
                    f"{name}:{number}: {symbol}() is defined only in the '{bundle}' bundle"
                    + (
                        "; it is behind a typeof guard, which means the call does"
                        " nothing when the bundle has not loaded, silently"
                        if guarded
                        else "; a bare call throws before the bundle loads"
                    )
                    + ". Add it to LAZY_ENTRY_POINTS (app.js) so the call loads the"
                    " bundle, or to REACHED_AFTER_LOAD here with the reason its"
                    " call site cannot run first."
                )

    assert not unaccounted, "\n".join(unaccounted)


#: The lazy tabs whose pages are drawn from index.html at boot, and so are on
#: screen before their bundle is in (`switchTab` reveals first and fetches
#: second, WORLD_CLASS_PLAN A1).
LAZY_TAB_PAGES = ("tab-graph", "tab-library", "tab-documents")

LISTENER = re.compile(
    r'^(?:\$\("([\w-]+)"\)|document\.getElementById\("([\w-]+)"\))\??\.addEventListener\('
)


def _ids_on_lazy_pages() -> set[str]:
    """Every id inside one of the lazy tabs' pages in index.html."""
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    starts = [m.start() for m in re.finditer(r'<div class="tab-page[^"]*" id="tab-', html)]
    ids: set[str] = set()
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        chunk = html[start:end]
        page = re.search(r'id="(tab-[\w-]+)"', chunk).group(1)
        if page in LAZY_TAB_PAGES:
            ids |= set(re.findall(r'\bid="([\w-]+)"', chunk))
    return ids


def test_a_boot_listener_cannot_reach_a_lazy_function_before_its_bundle():
    """**The cold-load window, per call site** (reported 2026-09-26: changing
    the graph's layout threw "setGraphPhysicsEnabled is not defined").

    The name-level list above allows `setGraphPhysicsEnabled` because the Graph
    tab's dispatch awaits the bundle before calling it; the call that threw was
    a different one, a `change` listener wired at boot in navigation.js on the
    layout picker, which is drawn from index.html and was live for as long as
    the bundle took to arrive (`scratchpad/ui-sweeps/graphcoldlayout.js`). So a
    listener wired at a boot file's top level that calls a function only a lazy
    bundle defines (and that is not a stand-in) must do one of two things:

    * `await ensureModule(...)` (or `await switchTab(...)`, which awaits it)
      before the call, in the listener itself; or
    * be on an element inside a lazy tab's page, which `switchTab` keeps
      `inert` until that tab's bundle has arrived, so no press reaches it.

    The second is the general fix and this test holds it in place too.
    """
    nav = (FRONTEND / "js" / "navigation.js").read_text(encoding="utf-8")
    assert "lazyPage.inert = true" in nav and "lazyPage.inert = false" in nav, (
        "switchTab no longer keeps a lazy tab's page inert while its bundle loads; "
        "every control drawn on that page is then live before its code exists"
    )

    lazy = _lazy_files()
    entries = _entry_points()
    boot = _boot_scripts()
    boot_defined: set[str] = set()
    for name in boot:
        boot_defined |= _declared_anywhere(FRONTEND / "js" / name)
    lazy_only: dict[str, str] = {}
    for bundle, files in lazy.items():
        for file_name in files:
            for symbol in _top_level_functions(FRONTEND / "js" / file_name):
                if symbol not in boot_defined and symbol not in entries.get(bundle, set()):
                    lazy_only.setdefault(symbol, bundle)
    call = re.compile(r"(?<![\w$.])(" + "|".join(sorted(map(re.escape, lazy_only))) + r")\s*\(")
    on_lazy_page = _ids_on_lazy_pages()
    assert "graph-layout" in on_lazy_page, "the page scan found nothing; has index.html's tab markup changed?"

    offenders: list[str] = []
    checked = 0
    for name in boot:
        lines = (FRONTEND / "js" / name).read_text(encoding="utf-8").split("\n")
        i = 0
        while i < len(lines):
            match = LISTENER.match(lines[i])
            if not match:
                i += 1
                continue
            element = match.group(1) or match.group(2)
            j = i
            # The statement runs to its own closing line at column 0.
            if not lines[i].rstrip().endswith(");"):
                j = i + 1
                while j < len(lines) and not lines[j].startswith("}"):
                    j += 1
            body = "\n".join(lines[i : j + 1])
            checked += 1
            for hit in call.finditer(body):
                if element in on_lazy_page:
                    continue
                before = body[: hit.start()]
                #: `await switchTab(...)` awaits the tab's bundle itself, and a
                #: `typeof` guard on the same name is the name-level test's
                #: business (above), which lists what each one does instead.
                if "ensureModule(" in before or "await switchTab(" in before:
                    continue
                if re.search(r"typeof\s+" + hit.group(1) + r"\s*===?\s*[\"']function", before):
                    continue
                offenders.append(
                    f"{name}:{i + 1}: the listener on #{element} calls {hit.group(1)}(), "
                    f"which only the '{lazy_only[hit.group(1)]}' bundle defines, with no "
                    "`await ensureModule(...)` before it and from outside a lazy tab's page"
                )
            i = j + 1
    assert checked > 50, f"only {checked} boot listeners found; has the scan broken?"
    assert not offenders, "\n".join(offenders)


def test_the_graph_canvas_is_not_desynchronized():
    """INBOX 430: a desynchronized 2D context is handed to the screen as an
    opaque overlay on a GPU, so the map's transparent background drew black
    until a menu over it forced ordinary compositing."""
    from pathlib import Path

    source = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "graph-canvas.js").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("//"))
    assert "desynchronized" not in code
