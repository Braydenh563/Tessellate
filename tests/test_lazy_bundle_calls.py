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
import sys
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
    """`LAZY_MODULES` as written in app.js, plus the bundles lazy-entries.js
    adds with `Object.assign(LAZY_MODULES, {...})`: bundle name to its files.
    lazy-entries.js went unread until 2026-11-01, when a bundle there lost a
    file and Ask threw `progressLine is not defined` on every question."""
    source = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"const LAZY_MODULES = \{(.*?)\n\};", source, re.S)
    assert block, "LAZY_MODULES not found in app.js; has the loader moved?"
    blocks = [block.group(1)]
    extra = (FRONTEND / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    blocks += re.findall(r"Object\.assign\(LAZY_MODULES, \{(.*?)\n\}\);", extra, re.S)
    out: dict[str, list[str]] = {}
    for text in blocks:
        for name, files in re.findall(r"^\s*(\w+):\s*\[(.*?)\],", text, re.M | re.S):
            out[name] = re.findall(r'"/js/([A-Za-z0-9._-]+\.js)"', files)
    #: A bundle that lists the characters first (lazy-entries.js's
    #: `CHARACTER_DEPENDENTS`) carries their files too, at run time.
    deps = re.search(r"const CHARACTER_DEPENDENTS = \[(.*?)\];", extra, re.S)
    assert deps, "CHARACTER_DEPENDENTS not found in lazy-entries.js; has it moved?"
    for name in re.findall(r'"(\w+)"', deps.group(1)):
        out[name] = out["characters"] + [f for f in out[name] if f not in out["characters"]]
    return out


def test_no_bundle_list_is_changed_at_run_time():
    """A bundle's files are what its definition says. A list grown at run time
    (`LAZY_MODULES.x.unshift(...)`) is invisible to every test here, and its
    loss is invisible too: the line that put answer-kit.js in front of the
    Ask, Ask history and Guide bundles went in a byte trim, and only the
    browser noticed (2026-11-01)."""
    found = []
    for path in sorted((FRONTEND / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        found += [f"{path.name}: {m}" for m in re.findall(r"LAZY_MODULES(?:\.\w+|\[[^\]]+\])\.(?:unshift|push|splice)\(", text)]
    assert not found, found


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
    #: lazy-entries.js's own stand-ins: `installStandIns({...})` blocks, and
    #: `installCharacterStandIns([...])` for the characters bundle.
    extra = (FRONTEND / "js" / "lazy-entries.js").read_text(encoding="utf-8")
    for text in re.findall(r"installStandIns\(\{(.*?)\n\}\);", extra, re.S):
        for name, names in re.findall(r"^\s*(\w+):\s*\[(.*?)\]", text, re.M | re.S):
            out.setdefault(name, set()).update(re.findall(r'"(\w+)"', names))
    for names in re.findall(r"installCharacterStandIns\(\[(.*?)\]", extra, re.S):
        out.setdefault("characters", set()).update(re.findall(r'"(\w+)"', names))
    return out


WINDOW_EXPORTS = re.compile(r"Object\.assign\(\s*(?:window|globalThis)\s*,\s*\{([^}]*)\}")


def _window_exports(source: str) -> set[str]:
    """Globals a wrapped file hands out: `Object.assign(window, { a, b: c })` binds `a` and `b`.

    A file wrapped in one closure (documents-props.js, documents-math.js, ...) declares
    nothing at column zero, so without this its globals were invisible to every lint here
    (doc23-1102: `math-editor.js:docMathRender` read as stale and was dropped).
    """
    names: set[str] = set()
    for body in WINDOW_EXPORTS.findall(source):
        for part in body.split(","):
            key = part.split(":", 1)[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", key):
                names.add(key)
    return names


def _top_level_functions(path: Path) -> set[str]:
    """Only functions declared at column zero, and a wrapped file's window exports: a nested helper is not a global."""
    source = path.read_text(encoding="utf-8")
    return set(re.findall(r"^(?:async )?function ([A-Za-z_$][\w$]*)", source, re.M)) | _window_exports(source)


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
    #: `file:name` keys (INBOX 1521): the same name is safe in one boot file and
    #: not in another, so these are per file. Every one is a call that only runs
    #: once the bundle is in, with the line that proves it.
    "editor.js:docTemplateFill": "inside `typeof DOC_TEMPLATES !== \"undefined\"` in editorCommands; DOC_TEMPLATES is defined in documents.js, the same library bundle, so the call runs only once it is in (audit 1102 DX30)",
    "settings-wiring.js:docFileDropBox": "inside `el?.closest?.(\"#doc-editor\")` in fileDropBox: the element exists only while the Documents page, and so the library bundle, is mounted (audit 161 D24)",
    "chat-agent.js:atlasAvatar": "assistantAvatar runs only from paintAssistantAvatar's afterCharacters (chat-agent.js)",
    "chat-agent.js:atlasDraw": "assistantAvatar runs only from paintAssistantAvatar's afterCharacters (chat-agent.js)",
    "chat-agent.js:atlasLook": "chatHeadKey is a cache key; its typeof guard only trims the key, and it is asked for a face only after afterCharacters",
    "chat-agent.js:atlasStyle": "chatHeadKey is a cache key; its typeof guard only trims the key, and it is asked for a face only after afterCharacters",
    "chat-agent.js:nameMark": "inside paintUserMarks's afterCharacters (chat-agent.js)",
    "chat.js:nameMark": "the same line is the afterCharacters callback (chat.js)",
    "chat.js:webEngineWords": "setWebEngineDot is called only from refreshWebSearxngStrip, which awaits ensureModule(\"webClip\") first (chat.js)",
    "chat.js:chatPrivateEmpty": "chatConv.private is set only by chat-private.js (chatPrivateStart, line 42), which the stand-in loads",
    "dashboard.js:nameMarkLive": "paintDashFace is called only from paintDashEmblem's afterCharacters (dashboard.js)",
    "palette.js:chatSourcesFrom": "called only inside cmdPaletteAsk, which awaits ensureModule('chatTurn') first (answer-kit.js rides in it)",
    "palette.js:chatSourcesPanel": "called only inside cmdPaletteAsk, which awaits ensureModule('chatTurn') first (answer-kit.js rides in it)",
    "palette.js:messageMetaLine": "called only inside cmdPaletteAsk, which awaits ensureModule('chatTurn') first (answer-kit.js rides in it)",
    "settings-panes.js:atlasAvatar": "a palette row's optional face: typeof-guarded, and the row's icon is the designed fallback (face null)",
    "settings-panes.js:mountProfileLook": "inside the afterCharacters callback that also calls setOwnNameMarkStyle",
    "settings-panes.js:nameMark": "the same line is the afterCharacters callback (settings-panes.js, profile avatar)",
    "settings-panes.js:setOwnNameMarkStyle": "inside the afterCharacters callback (settings-panes.js, renderProfile)",
    "settings-panes.js:ownNameMarkStyle": "the save payload: without the bundle the look controls were never mounted, so there is no change to send and undefined omits the field",
    "settings-wiring.js:improveReady": "a click on .improve-mode, which is inside #improve-overlay; that is hidden until openImprove (improve-panel.js:18) shows it",
    "settings.js:nameMarkBuddyMotion": "inside the afterCharacters callback (settings.js, the About motion line)",
    "settings.js:bgArtSeedText": "bgArtRefreshSeed returns early unless bgArtSeedUsed is defined, and that is declared in bg-art.js",
    "settings.js:bgArtHalt": "halts what bgArtRun mounted, and bgArtRun runs only once bg-art.js is in (startBgArt's typeof gate)",
    "copyWebLink": "the web reader's Copy link listener (wiring.js), which awaits ensureModule('webClip') first",
    "openWebPageExternally": "the web reader's Open listener (wiring.js), which awaits ensureModule('webClip') first",
    #: INBOX 1301 D6: the release calls it only when `typeof nameMarkBuddyThrow
    #: === "function"`; the carry's first move fetched the bundle, and a let-go
    #: before it arrives is a drop.
    #: INBOX 1305: a far move asks for its path when `typeof companionPathPlan
    #: === "function"`; the mind's first tick fetches the bundle, and until
    #: it is here a far move walks.
    "popupToolMaths": "POPUP_TOOLS' open, which waits on ensureModule('appPalette') before the call",
    "renderShortcutList": "settings.js asks for it in the .then of ensureModule('reveal'); settings-wiring's resetShortcuts and captureShortcutKey run only once a list built by this bundle is on screen",
    "renderToolShortcutList": "openShortcuts, which waits on ensureModule('appPalette') before the call",
    "docDropIfUntouched": "confirmLeavingUnsavedWork, past its `typeof docDirty` return: docDirty is declared by the same library bundle, so the call is reached only once it has loaded",
    "docTurnIntoMenu": "the selection bar's Turn into button, which selectionBarShow hides until the library bundle defines it",
    "imageLayout": "appendInlineRun (notes-list.js), called as window.imageLayout?.(): a picture drawn before the library bundle arrives is plain, and image-layout.js lays out what is already on the page when it loads (its sweep), so nothing is lost",
    "mdRunNode": "appendInlineRun, behind a typeof check: a run (INBOX 1403) is written only in a board text box, which is the library bundle; read in a note before that bundle arrives, its words draw plain and are not lost (the grammar and the preview are at boot)",
    "wbSelectionBarFit": "selectionBarShow on a board box, which exists only once whiteboard.js (library bundle) has drawn the board; elsewhere there is nothing to fit",
    "mermaidDrawBlock": "mermaidSoon (navigation.js), inside the then of ensureModule('mermaid'): it runs only once the bundle has loaded",
    "findSettings":"settingsUi, called by filterSettings only when renderSettingResults (same bundle) returned a count",
    "linkCancel": "settings-wiring's Escape handler, only while `linkSource !== null`, which beginOrCompleteLink (the same notePanels bundle) alone sets",
    "companionPathPlan": "companionMenu, fetched with the mind at the first tick; a far move walks until then (typeof check)",
    "nameMarkBuddyThrow": "companionThrow, fetched on the carry's first move; the release checks typeof and drops otherwise",
    "companionThrowPlan": "companionThrow, called by the release only when `thrown`, which is false unless typeof nameMarkBuddyThrow (same bundle) is a function",
    #: Back closing an open overlay (router-overlays.js): preloaded three seconds
    #: after boot; before that Back steps the tab history as it always did. A
    #: stand-in would return a promise, which is truthy, and swallow every Back.
    "routerSettle": "quickNote (carries router-overlays.js), called in the .then of ensureModule('quickNote') in closeSettingsModal",
    "routerBackHook": "quickNote (carries router-overlays.js), preloaded 3 s after boot; until then Back is the tab history's, as before",
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
    #: The per-feature model rows: `renderSettings` (status.js) runs only while
    #: the Settings window is open, and openSettingsModal awaits settingsControls
    #: before it shows.
    "renderFeatureModelRows": "settingsControls, drawn only by renderSettings, which runs while the window that awaited it is open",
    "openTaskLog":"settingsControls, the Settings window awaits it before any row in it can be pressed",
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
    "renderRelatedElsewhere": "replyKit, called in the .then of ensureModule('replyKit') by the Ask foot and Chat's onRelated",
    "replyFinish": "replyKit, called in the .then of ensureModule('replyKit') by finishReply, every answer surface's last step (INBOX 1300 C07)",
    "replyDrawAll": "replyKit, called in the .then of ensureModule('replyKit') by drawAnswerPanels, every answer surface's panel drawer (INBOX 1300 C06)",
    "digestOffer": "askCompose, called in the .then of ensureModule('askCompose') in renderAnswerGrounding",
    "digestShape": "askCompose, called in the .then of ensureModule('askCompose') in renderAnswerGrounding",
    "digestMore": "askCompose, called in the .then of ensureModule('askCompose') in renderAnswerGrounding",
    #: The answer's foot (B12, B30, B31, decision 73, follow-ups), moved out of
    #: capture-ask.js to keep the boot scripts under their ratchet.
    "citationVerdictRow": "askCompose, called in the .then of ensureModule('askCompose') in openCitationPeek",
    "askAnswerMenu": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "renderAskInsights": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "renderAskWhy": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "drawWhyTrail": "askCompose, called in the .then of ensureModule('askCompose') by Chat's send and the popup agent (B30)",
    "renderAskBoth": "askCompose, called in the .then of ensureModule('askCompose') in askQuestion",
    "renderAskFollowups": "askCompose, passed to the .then of ensureModule('askCompose') in askQuestion",
    #: B12: an answer's mind map is tidied after `await openWhiteboardBoard`,
    #: which loads the library bundle first (askKeepAsMap, capture-ask.js).
    "wbMapTidyFresh": "library, called after await openWhiteboardBoard in askKeepAsMap's Open",
    #: Brief bootdiet: the catalogue is in the palette's bundle, and every other
    #: reader (Tools and features, Quick access, startApp's recovered recordings)
    #: awaits `lazyScript` / `ensureModule` before it reads or calls.
    "featureCatalog": "appPalette, the palette's bundle names it; openFeatures and renderQuickLinks await lazyScript('/js/app-features.js') first",
    "featureCommandRows": "renderFeatures, which runs after openFeatures awaits lazyScript('/js/app-features.js'); the search box only types once the dialog is open",
    "noteRecoveredRecordings": "meetings, called in the .then of ensureModule('meetings') in dashboard.js's startApp hook",
    #: INBOX 784: the Notes column's rows are drawn by connections.js;
    #: renderNotesRail awaits lazyScript('/js/connections.js') before any of them.
    "withBacklinks": "connections, renderNotesRail awaits lazyScript('/js/connections.js') before drawing",
    "buildConnectionGroups": "connections, renderNotesRail awaits lazyScript('/js/connections.js') before drawing",
    "connectionRowEl": "connections, the forgotten group is drawn inside drawNotesRail, which renderNotesRail calls after it awaited the bundle",
    "drawNotesRail": "connections, renderNotesRail awaits lazyScript('/js/connections.js') and then returns it (INBOX 1525: moved for the boot gzip cap)",
    #: Brief 89: the palette's small tools, each called in the .then of
    #: ensureModule('utilities') on its own palette row (settings-panes.js).
    "startUtilityTimer": "utilities, called in the .then of ensureModule('utilities') on the palette's timer rows",
    "openCalculator": "replyKit, called in the .then of ensureModule('replyKit') on the palette's Calculator row",
    "startStopwatch": "utilities, called in the .then of ensureModule('utilities') on the palette's stopwatch row",
    "openClockPanel": "utilities, called in the .then of ensureModule('utilities') on the timer, stopwatch and alarm rows and the palette's typed timer",
    "utilityOps": "utilities, used in the .then of ensureModule('utilities') by the dashboard's Focus widget (focusRow)",
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
    #: A composed answer's quoted sentences take the quote style once ask-compose.js is in (`addInlineCitations`, capture-ask.js).
    "markSaidSentences": "askCompose, called from ensureModule('askCompose').then in addInlineCitations",
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
    "renderHelpTopics": "settingsUi, called when Help is shown or Settings is first searched, both inside the open dialog that awaited the bundle",
    "renderCredits": "settingsUi, awaited by openSettingsModal two lines before the call",
    "renderSettingResults": "settingsUi, called from the search field inside the open dialog",
    "settingQueryAlts": "settingsUi, called from filterSettings, the search field inside the open dialog (an empty query returns before it)",
    "meaningHolds": "settingsUi (meaning.js), called from filterSettings beside settingQueryAlts; without the bundle the plain substring rule runs",
    "settingResultsKey": "settingsUi, called from the search field inside the open dialog",
    "renderSuggested": "settingsUi, called from the status poll only while Settings is open (renderSettings), and Settings awaits the bundle first",
    #: The installed models moved beside it (op4-1005): the same poll branch,
    #: the same reason; the box is hidden until a call draws it.
    "renderInstalledModels": "settingsUi, beside renderSuggested in the same status-poll branch, and Settings awaits the bundle first",
    "renderEmbeddingPicker": "settingsUi, called from renderSettings beside renderSuggested, only while Settings is open, and Settings awaits the bundle first",
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

#: Lazy-to-lazy (INBOX 1521): a call in a lazy file to a name that only another
#: bundle defines. `file:name` keys, each with the line that proves the call is
#: reached only after the file that defines the name is in.
LAZY_REACHED_AFTER_LOAD: dict[str, str] = {
    "whiteboard-format.js:swatchPicker": "wbColourPalettes fills its rows in the .then of ensureModule('categories'), which carries categories-panel.js",
    "answer-kit.js:agentTimeline": "addAssistantBubble has two callers: chat-turn.js (its own file) and sheets-selects.js's replay, after `await ensureModule(\"chatTurn\")` (line 1991)",
    "answer-kit.js:nameMark": "inside the afterCharacters callback (avatarHead and chatHead paths) or reached from it",
    "app-palette.js:quickAddPaletteRow": "typeof-guarded optional first row; null is the designed answer without it (the act row only exists once quickadd.js or the board is loaded)",
    "app-palette.js:wbPaletteActRow": "typeof-guarded optional first row; null is the designed answer without it (the act row only exists once quickadd.js or the board is loaded)",
    "appearance-panel.js:paintSettingRow": "the panel is opened only by openAppearancePanel, which awaits settingsControls and settings-rows.js (line 265) before it sets APPEARANCE_PANEL.open, and this returns while it is not open",
    "appearance-panel.js:releaseThemeHold": "closeAppearancePanel returns unless APPEARANCE_PANEL.open, and openAppearancePanel awaits settingsControls before it sets it (line 265)",
    "appearance-panel.js:settingDefaults": "the panel is opened only by openAppearancePanel, which awaits settingsControls and settings-rows.js (line 265) before it sets APPEARANCE_PANEL.open, and this returns while it is not open",
    "appearance-panel.js:settingRowsIn": "the panel is opened only by openAppearancePanel, which awaits settingsControls and settings-rows.js (line 265) before it sets APPEARANCE_PANEL.open, and this returns while it is not open",
    "appearance-panel.js:settingsControlState": "the panel is opened only by openAppearancePanel, which awaits settingsControls and settings-rows.js (line 265) before it sets APPEARANCE_PANEL.open, and closeAppearancePanel returns while it is not open",
    "ask-compose.js:wbMapTidyFresh": "after `await openWhiteboardBoard(...)`, a stand-in that loads the library bundle (whiteboard-map.js) first",
    "atlas-motion.js:atlasRigLower": "`if (rig.lower)`: only atlasRigLowerAttach (atlas-life.js) sets it, and the atlasLife bundle carries atlas-motion.js",
    "atlas.js:atlasTailFrame": "reached only through a tail atlasTailAttach (atlas-life.js) made, as the line above says",
    "avatars.js:companionPathPlan": "typeof-guarded (INBOX 1305): a far move walks until the companion's mind has fetched companion-menu.js",
    "captions.js:translateAsk": "captionTranslate.on is set only after `await ensureModule(\"translate\")` in captionToggleTranslate",
    "capture-card.js:renderCaptureThumbs": "behind `captureCard.root.dataset.extras`, which only mountCaptureExtras (capture-card-more.js) sets",
    "capture-card.js:syncCaptureExtras": "behind `captureCard.root.dataset.extras`, which only mountCaptureExtras (capture-card-more.js) sets",
    "capture-card.js:uploadCapturePictures": "behind `captureCard.pictures.length`: a picture is added only by capture-card-more.js",
    "categories-panel.js:manageCountButton": "the panel's opener awaits ensureModule(\"tagManager\") (line 29) before it renders a row",
    "categories-panel.js:manageRecent": "the panel's opener awaits ensureModule(\"tagManager\") (line 29) before it renders a row",
    "categories-panel.js:manageSorted": "the panel's opener awaits ensureModule(\"tagManager\") (line 29) before it renders a row",
    "chat-turn.js:docSurfaceById": "typeof-guarded with a designed fallback (the textarea's own text) when documents.js has never loaded",
    "chat-turn.js:setAtlasMood": "typeof-guarded cue: a mood is stale a moment later, and there is no face to move before the characters arrive",
    "documents-codekit.js:docDiffLines": "in docAssistPropose, reached only from docAssistShow after `await lazyScript(\"/js/documents-history.js\")` (docAssistAsk)",
    "documents-codekit.js:docRenderDiff": "in docAssistPropose, reached only from docAssistShow after `await lazyScript(\"/js/documents-history.js\")` (docAssistAsk)",
    "documents-export.js:mermaidInlineForExport": "after `await lazyModuleLoads.get(\"mermaid\")`: undefined (never asked for) skips it, a pending load is awaited",
    "documents-mermaid.js:mermaidSettled": "after `await lazyModuleLoads.get(\"mermaid\")`: undefined (never asked for) skips it, a pending load is awaited",
    "documents-mermaid.js:currentDoc": "the Live figure and the fence renderer run inside the document editor (docRenderMermaidIn, docMermaidField's widgets), which exists only once documents.js is in; the diagramDoor module (INBOX 1722) loads this file without the editor and never calls them",
    "documents-mermaid.js:docPhase2State": "the Live figure and the fence renderer run inside the document editor (docRenderMermaidIn, docMermaidField's widgets), which exists only once documents.js is in; the diagramDoor module (INBOX 1722) loads this file without the editor and never calls them",
    "documents-mermaid.js:docStr": "the Live figure and the fence renderer run inside the document editor (docRenderMermaidIn, docMermaidField's widgets), which exists only once documents.js is in; the diagramDoor module (INBOX 1722) loads this file without the editor and never calls them",
    "documents-mermaid.js:wbEditDiagram": "behind `window.wbCommandsLive?.()` in diagramDoor (true only once the board's files are in); the Diagram builder door (INBOX 1722) loads this file alone, with no board",
    "graph-canvas.js:refreshBoardList": "typeof-guarded refresh of a list that exists only once the library bundle is on screen (lazy-entries.js rule 2)",
    "graph-canvas.js:wbMapTidyFresh": "after `await openWhiteboardBoard(...)`, a stand-in that loads the library bundle (whiteboard-map.js) first",
    "graph.js:fillSearchSuggest": "inside `typeof searchSuggestHold === \"function\" && searchSuggestHold(box)`: the list is open only when search-suggest.js is in",
    "lan-watch.js:popoverHead": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"statusPanels\") with settingsControls before it draws",
    "obj-tray.js:popoverHead": "the tray's wiring awaits ensureModule(\"statusPanels\") before its first paint; a change before that draws nothing until it, by design (INBOX 1603)",
    "lan-watch.js:lanAllowHere": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"settingsControls\") (line 289) before it draws",
    "lan-watch.js:lanEmptyRow": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"settingsControls\") (line 289) before it draws",
    "lan-watch.js:lanNetworkRows": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"settingsControls\") (line 289) before it draws",
    "lan-watch.js:lanSwitch": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"settingsControls\") (line 289) before it draws",
    "lan-watch.js:lanTrustNetwork": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"settingsControls\") (line 289) before it draws",
    "lan-watch.js:renderLanAddresses": "lanDrawPanel's only caller is the panel's opener, which awaits ensureModule(\"settingsControls\") (line 289) before it draws",
    "library.js:showTopicInGraph": "after `await switchTab(\"graph\")`, which fetches the graph bundle first",
    "lightbox-view.js:loadLibrary": "typeof-guarded refresh of the Library's list: skipping is right when it was never opened, and opening it loads and renders it (lazy-entries.js rule 2)",
    "lightbox-view.js:renderLibrary": "typeof-guarded refresh of the Library's list: skipping is right when it was never opened, and opening it loads and renders it (lazy-entries.js rule 2)",
    "lightbox-view.js:renderLibraryImagesGallery": "typeof-guarded refresh of the Library's list: skipping is right when it was never opened, and opening it loads and renders it (lazy-entries.js rule 2)",
    "manual.js:meaningAlts": "meaning.js is fetched by openManual (`await lazyScript(\"/js/meaning.js\")`, line 149) before the search box can be typed in",
    "manual.js:meaningHolds": "meaning.js is fetched by openManual (`await lazyScript(\"/js/meaning.js\")`, line 149) before the search box can be typed in",
    "manual.js:meaningNamed": "meaning.js is fetched by openManual (`await lazyScript(\"/js/meaning.js\")`, line 149) before the search box can be typed in",
    "meetings.js:holdLiveCaptions": "behind `meetingLive.on`, which meetingLiveWordsStart sets only after `await ensureModule(\"captions\")`",
    "meetings.js:loadLibrary": "typeof-guarded refresh of the Library's list: skipping is right when it was never opened, and opening it loads and renders it (lazy-entries.js rule 2)",
    "meetings.js:stopRecorderWords": "behind `meetingLive.on`, which meetingLiveWordsStart sets only after `await ensureModule(\"captions\")`",
    "note-edit-panels.js:noteOffersAttach": "typeof-guarded: a form opened before quickadd.js (preloaded three seconds after boot) has no offers, by design",
    "note-properties.js:applyGraphHighlight": "behind `typeof renderGraph`/`typeof applyGraphHighlight` guards, both graph.js's: with the graph never loaded there is no map to colour",
    "note-properties.js:graphColourMode": "behind `typeof renderGraph`/`typeof applyGraphHighlight` guards, both graph.js's: with the graph never loaded there is no map to colour",
    "obj-carry.js:wbIsMap": "behind `window.wbCommandsLive?.()`, true only once the board's files (whiteboard-commands.js, whiteboard-map.js, whiteboard.js, one bundle) are in",
    "obj-clip.js:wbAnnounce": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbClientToBoard": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbCreateCopies": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbIsMap": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbPasteTextBoxItem": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbPlaceNote": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbRecordGesture": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbSelectMade": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-clip.js:wbViewCentre": "behind `window.wbCommandsLive?.()` in the board renderer, true only once the board's files (one bundle) are in",
    "obj-reorder.js:LIBRARY_DOC_SORTS": "a surface's `all()` runs for a reorder inside a list the Library drew (#library-docs-list holds items only after library.js ran)",
    "obj-reorder.js:LIBRARY_MEDIA_SORTS": "a surface's `all()` runs for a reorder inside a list the Library drew (#library-images-grid holds tiles only after library.js ran)",
    "obj-reorder.js:libraryDocSort": "a surface's `all()` runs for a reorder inside a list the Library drew (#library-docs-list holds items only after library.js ran)",
    "obj-reorder.js:libraryMediaSort": "a surface's `all()` runs for a reorder inside a list the Library drew (#library-images-grid holds tiles only after library.js ran)",
    "quickadd.js:renderPalette": "behind `!$(\"palette-overlay\").classList.contains(\"hidden\")`: only openPalette shows it, and its stand-in loads app-palette.js",
    "reveal-targets.js:libraryKind": "a reveal target's `open` runs after `module: \"library\"` has loaded the library bundle (the target table's own rule)",
    "reveal-targets.js:renderDocShortcutSheet": "typeof-guarded; the section says where its rows come from when the library bundle is not in (the note beside it)",
    "reveal-targets.js:renderLibrary": "a reveal target: `await switchTab(target.tab)` (line 563), revealDocument, revealBoard or revealBoardsGallery has loaded the library bundle first",
    "reveal-targets.js:renderLibraryFilters": "a reveal target: `await switchTab(target.tab)` (line 563), revealDocument, revealBoard or revealBoardsGallery has loaded the library bundle first",
    "reveal-targets.js:renderWbShortcutSheet": "typeof-guarded; the section says where its rows come from when the library bundle is not in (the note beside it)",
    "reveal-targets.js:setDocView": "a reveal target: `await switchTab(target.tab)` (line 563), revealDocument, revealBoard or revealBoardsGallery has loaded the library bundle first",
    "reveal-targets.js:wbCommandsLive": "typeof-guarded; the section says where its rows come from when the library bundle is not in (the note beside it)",
    "reveal-targets.js:wbExportBoard": "a reveal target: `await switchTab(target.tab)` (line 563), revealDocument, revealBoard or revealBoardsGallery has loaded the library bundle first",
    "reveal-targets.js:wbNewUntitledBoard": "a reveal target: `await switchTab(target.tab)` (line 563), revealDocument, revealBoard or revealBoardsGallery has loaded the library bundle first",
    "run-core.js:docCsvTableHtml": "the run bundle is fetched only by documents-code.js (`ensureModule(\"run\")`, runDocument), which defines it",
    "search.js:paletteFind": "finderActions is called after `await ensureModule(\"appPalette\")` (search.js lines 187 and 357)",
    "settings-controls.js:atlasLookReason": "inside the afterCharacters callback",
    "settings-data.js:helpChatHistory": "restoreGuideTurns' one caller awaits ensureModule(\"helpChat\") first (the undo handler, `kept.kind === \"guide\"`)",
    "settings-data.js:helpChatNewChat": "restoreGuideTurns' one caller awaits ensureModule(\"helpChat\") first (the undo handler, `kept.kind === \"guide\"`)",
    "settings-data.js:renderHelpChatMessage": "restoreGuideTurns' one caller awaits ensureModule(\"helpChat\") first (the undo handler, `kept.kind === \"guide\"`)",
    "settings-data.js:renderLanAddresses": "typeof-guarded, else the row is hidden; renderPrivacy runs in a Settings window that awaited settingsControls",
    "space-swap.js:gcTopicSummaries": "behind `typeof graphStructure` (graph.js): graph-canvas.js is the next file of the same graph bundle",
    "space-swap.js:showNoDocument": "behind `typeof currentDoc`/`typeof wbFlushNudge` guards: with documents.js or the board never loaded there is nothing open to put away",
    "space-swap.js:wbFlushNudge": "behind `typeof currentDoc`/`typeof wbFlushNudge` guards: with documents.js or the board never loaded there is nothing open to put away",
    "statistics.js:overlayClosed": "typeof-guarded back-stack note: router-overlays.js is in the quickNote bundle, preloaded three seconds after boot, and without it no overlay entry was pushed to pop",
    "whiteboard-commands.js:renderPalette": "behind `!$(\"palette-overlay\").classList.contains(\"hidden\")`: only openPalette shows it, and its stand-in loads app-palette.js",
    "whiteboard-interchange.js:mermaidKnown": "typeof-guarded with a designed fallback (no picture, the plain placeholder) until mermaid-draw.js is in",
    "whiteboard.js:nameMarkBuddyCanvasZoom": "typeof-guarded sync of the companion's zoom: with no companion loaded there is nothing to scale",
    "whiteboard.js:nmb": "behind `!charactersLoaded ||`, set only once the characters bundle (avatars.js) is in (lazy-entries.js)",
}

GUARD = re.compile(r'typeof\s+(\w+)\s*===?\s*["\']function["\']')


#: Gaps the scan found when it first read lazy-entries.js (2026-11-01, INBOX 1521),
#: as `file:name`. This set only shrinks: each is fixed (a stand-in, an awaited
#: ensureModule, or a REACHED_AFTER_LOAD reason) and taken out; a new gap fails.
KNOWN_GAPS_1521: set[str] = set()


FUNCTION_START = re.compile(r"^(?:async )?function [A-Za-z_$]")


def test_no_boot_file_silently_depends_on_a_lazy_bundle():
    lazy = _lazy_files()
    entries = _entry_points()
    boot = _boot_scripts()
    assert "app.js" in boot and "editor.js" in boot, f"boot scripts look wrong: {boot}"

    boot_defined: set[str] = set()
    for name in boot:
        boot_defined |= _declared_anywhere(FRONTEND / "js" / name)

    lazy_defined: dict[str, str] = {}
    #: Every bundle a name arrives with: answer-kit.js rides in four.
    arrives_with: dict[str, set[str]] = {}
    for bundle, files in lazy.items():
        for file_name in files:
            for symbol in _top_level_functions(FRONTEND / "js" / file_name):
                lazy_defined.setdefault(symbol, bundle)
                arrives_with.setdefault(symbol, set()).add(bundle)

    candidates = {s: b for s, b in lazy_defined.items() if s not in boot_defined}
    assert candidates, "no cross-bundle names at all; has the scan broken?"
    call = re.compile(r"(?<![\w$.])(" + "|".join(sorted(map(re.escape, candidates))) + r")\s*\(")

    unaccounted: list[str] = []
    still_known: set[str] = set()
    for name in boot:
        lines = (FRONTEND / "js" / name).read_text(encoding="utf-8").split("\n")
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            for match in call.finditer(line):
                symbol = match.group(1)
                bundle = candidates[symbol]
                if any(symbol in entries.get(b, set()) for b in arrives_with[symbol]):
                    continue
                if symbol in REACHED_AFTER_LOAD or f"{name}:{symbol}" in REACHED_AFTER_LOAD:
                    continue
                if f"{name}:{symbol}" in KNOWN_GAPS_1521:
                    still_known.add(f"{name}:{symbol}")
                    continue
                #: Safe by construction: the enclosing top-level function waited
                #: for a bundle that carries the name before this line
                #: (`if (!(await ensureModule("chatTurn"))) return ...`).
                start = number - 1
                while start > 0 and not FUNCTION_START.match(lines[start]):
                    start -= 1
                before = "\n".join(lines[start:number - 1]) + "\n" + line[: match.start()]
                if any(f'ensureModule("{b}")' in before for b in arrives_with[symbol]):
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
    assert still_known == KNOWN_GAPS_1521, f"fixed, take out of KNOWN_GAPS_1521: {sorted(KNOWN_GAPS_1521 - still_known)}"


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
                if symbol not in boot_defined and not any(symbol in names for names in entries.values()):
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


def _defined_any_form(path: Path) -> set[str]:
    """Every name a file binds at any depth: functions, const/let/var, classes."""
    source = path.read_text(encoding="utf-8")
    names = set(re.findall(r"(?:^|\s)(?:async )?function\*? ([A-Za-z_$][\w$]*)\s*\(", source))
    names |= set(re.findall(r"\b(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)", source))
    names |= set(re.findall(r"\bwindow\.([A-Za-z_$][\w$]*)\s*=[^=]", source))
    return names


def _top_level_bindings(path: Path) -> tuple[set[str], set[str]]:
    """Column-zero functions, and column-zero const/let/class names (`const a = 1, b`
    chains and destructuring are not read: a name a lint cannot see is one it cannot flag)."""
    source = path.read_text(encoding="utf-8")
    funcs = set(re.findall(r"^(?:async )?function\*? ([A-Za-z_$][\w$]*)", source, re.M)) | _window_exports(source)
    data = set(re.findall(r"^(?:const|let|class) ([A-Za-z_$][\w$]*)", source, re.M))
    return funcs, data


def _loader_chains() -> list[tuple[str, list[str]]]:
    """`[...js files].forEach(lazyScript)`: `(host file, files in load order)`. The
    obj-* scripts load this way (obj-ref.js, a chain of six): `lazyScript` keeps dynamic
    scripts in document order, so a later file is not there yet while an earlier one runs."""
    out = []
    for path in sorted((FRONTEND / "js").glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for body in re.findall(r"\[((?:\s*\"/(?:js|css)/[A-Za-z0-9._-]+\",?)+)\s*\]\s*\.(?:forEach|map)\(lazyScript\)", text):
            files = re.findall(r'"/js/([A-Za-z0-9._-]+\.js)"', body)
            if files:
                out.append((path.name, files))
    return out


def _direct_loads() -> dict[str, list[tuple[str, frozenset[str], frozenset[str]]]]:
    """Files loaded by a literal `lazyScript("/js/x.js")`: file to one `(asker, bundles it
    awaited first, files loaded with it)` per call site. A call site that follows
    `await ensureModule("library")` in the same function loads the file with that whole
    bundle in; one beside or after another `lazyScript` in that function (documents.js's
    `Promise.all([lazyScript(ai), lazyScript(history)])`) loads it with that file in."""
    out: dict[str, list[tuple[str, frozenset[str], frozenset[str]]]] = {}
    for path in sorted((FRONTEND / "js").glob("*.js")):
        lines = path.read_text(encoding="utf-8").split("\n")
        for number, line in enumerate(lines):
            for m in re.finditer(r'lazyScript\("/js/([A-Za-z0-9._-]+\.js)"\)', line):
                name = m.group(1)
                if name == path.name or not (FRONTEND / "js" / name).exists():
                    continue
                start = number
                while start > 0 and not FUNCTION_START.match(lines[start]):
                    start -= 1
                before = "\n".join(lines[start:number]) + "\n" + line[: m.start()]
                beside = before + line[m.end() :]
                with_it = frozenset(f for f in re.findall(r'lazyScript\("/js/([A-Za-z0-9._-]+\.js)"\)', beside)
                                    if f != name and (FRONTEND / "js" / f).exists())
                out.setdefault(name, []).append((path.name, frozenset(re.findall(r'ensureModule\("(\w+)"\)', before)), with_it))
    return out


STRING_LITERAL = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`")


def lazy_to_lazy_gaps(used: set[str] | None = None) -> list[str]:
    """One lazy file reading a name that only another lazy file defines, where the
    files that loaded it (its bundle, the files before it in its `forEach(lazyScript)`
    chain, the file that asked for it by `lazyScript("/js/x.js")`) do not carry it, no
    stand-in stands for it, and nothing before the read awaits it. A read is a call
    or, for a top-level const/let/class, the bare name. `progressLine` in Ask, the Guide
    and first-run was this: answer-kit.js left three bundles. `OBJ_EDITABLE` was the
    chain case: obj-reorder.js read a const obj-clip.js, loaded after it, defined."""
    lazy = _lazy_files()
    entries = _entry_points()
    always: set[str] = set().union(*entries.values())
    for name in _boot_scripts():
        always |= _defined_any_form(FRONTEND / "js" / name)
    chains = _loader_chains()
    direct = _direct_loads()
    boot = set(_boot_scripts())
    bundled = {f for files in lazy.values() for f in files if f.endswith(".js")}
    universe = sorted(bundled | {f for _, files in chains for f in files} | set(direct))
    universe = [f for f in universe if f not in boot and (FRONTEND / "js" / f).exists()]
    names_of = {f: _defined_any_form(FRONTEND / "js" / f) for f in universe + sorted(boot)}
    for _, files in chains:
        for f in files:
            names_of.setdefault(f, _defined_any_form(FRONTEND / "js" / f))
    funcs_in: dict[str, set[str]] = {}
    data_in: dict[str, set[str]] = {}
    for file_name in universe:
        funcs, data = _top_level_bindings(FRONTEND / "js" / file_name)
        for symbol in funcs:
            funcs_in.setdefault(symbol, set()).add(file_name)
        for symbol in data:
            data_in.setdefault(symbol, set()).add(file_name)
    defined_in = {**data_in, **{k: v | data_in.get(k, set()) for k, v in funcs_in.items()}}
    routes_memo: dict[str, list[set[str]]] = {}

    def routes(file_name: str, seen: frozenset = frozenset()) -> list[set[str]]:
        """The name sets a file can be loaded with: one per way it arrives. A file
        reached only by a route that carries a name may read it; one arriving by any
        route that does not may not."""
        if file_name in routes_memo:
            return routes_memo[file_name]
        out: list[set[str]] = []
        for bundle, files in lazy.items():
            if file_name in files:
                out.append(set().union(*(names_of.get(f) or _defined_any_form(FRONTEND / "js" / f) for f in files if f.endswith(".js") and (FRONTEND / "js" / f).exists())))
        for host, files in chains:
            if file_name in files and file_name != host:
                before = set().union(*(names_of[f] for f in files[: files.index(file_name) + 1]))
                out += [before | names_of.get(host, set()) | r for r in (host_routes(host, seen) or [set()])]
        for host, awaited, with_it in direct.get(file_name, ()):
            loaded = set().union(set(), *(set().union(*(names_of.get(f) or _defined_any_form(FRONTEND / "js" / f) for f in lazy[b] if f.endswith(".js"))) for b in awaited if b in lazy))
            loaded |= set().union(set(), *(names_of.get(f) or _defined_any_form(FRONTEND / "js" / f) for f in with_it))
            out += [names_of.get(file_name, set()) | names_of.get(host, set()) | loaded | r for r in (host_routes(host, seen) or [set()])]
        routes_memo[file_name] = out
        return out

    def host_routes(host: str, seen: frozenset) -> list[set[str]]:
        return [] if host in boot or host in seen else routes(host, seen | {host})

    candidates = {s for s in defined_in if s not in always}
    fn_candidates = {s for s in candidates if s in funcs_in}
    data_candidates = {s for s in candidates if s in data_in and s not in funcs_in}
    word = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)")

    def reads(code: str):
        """`(name, offset)` for each call of a function, or bare use of a top-level
        const/let/class, a lazy file defines. A name before a colon is an object key."""
        for m in word.finditer(code):
            name = m.group(1)
            if name in fn_candidates and re.match(r"\s*\(", code[m.end() :]):
                yield name, m.start()
            elif name in data_candidates and not re.match(r"\s*:(?!:)", code[m.end() :]):
                yield name, m.start()

    arrives_with = {s: {b for b, files in lazy.items() if files and set(files) & defined_in[s]} for s in candidates}
    gaps: list[str] = []
    for file_name in universe:
        route_sets = routes(file_name)
        own = _defined_any_form(FRONTEND / "js" / file_name)
        lines = (FRONTEND / "js" / file_name).read_text(encoding="utf-8").split("\n")
        for number, line in enumerate(lines, 1):
            if line.lstrip().startswith(("//", "*", "/*")):
                continue
            code = STRING_LITERAL.sub(lambda m: m.group(0) if "${" in m.group(0) else m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[0], line)
            for symbol, offset in reads(code):
                if symbol in own or all(symbol in c for c in route_sets):
                    continue
                if f"{file_name}:{symbol}" in LAZY_REACHED_AFTER_LOAD:
                    if used is not None:
                        used.add(f"{file_name}:{symbol}")
                    continue
                start = number - 1
                while start > 0 and not FUNCTION_START.match(lines[start]):
                    start -= 1
                before = "\n".join(lines[start : number - 1]) + "\n" + line[:offset]
                #: A `typeof name` or `window.name` test earlier in the same function (or on this line) is a
                #: guard, and so is one on another name the same script defines (the file
                #: arrives whole): space-swap.js tests one graph.js variable, then clears its siblings.
                siblings = {symbol}.union(*(names_of.get(f, set()) for f in defined_in[symbol]))
                if any(name in siblings for name in re.findall(r"(?:typeof\s+|window\??\.)([\w$]+)", before + code)):
                    continue
                if any(f'ensureModule("{b}")' in before for b in arrives_with[symbol]):
                    continue
                if any(f'lazyScript("/js/{f}")' in before for f in defined_in[symbol]):
                    continue
                missing = len([c for c in route_sets if symbol not in c])
                gaps.append(f"{file_name}:{number}: {symbol} is defined only in {sorted(defined_in[symbol])}; {missing} of {len(route_sets)} ways this file loads do not carry it")
    return gaps


def test_no_lazy_file_calls_a_name_only_another_bundle_defines():
    used: set[str] = set()
    gaps = lazy_to_lazy_gaps(used)
    assert not gaps, "\n".join(gaps)
    assert used == set(LAZY_REACHED_AFTER_LOAD), f"no longer needed, take out: {sorted(set(LAZY_REACHED_AFTER_LOAD) - used)}"


def _probe_gaps(tmp_path, monkeypatch, defined_in: str) -> list[str]:
    """A copy of the frontend where obj-reorder.js reads a const that `defined_in` holds."""
    import shutil

    shutil.copytree(FRONTEND / "js", tmp_path / "js")
    shutil.copy(FRONTEND / "index.html", tmp_path / "index.html")
    with (tmp_path / "js" / defined_in).open("a", encoding="utf-8") as handle:
        handle.write("\nconst OBJ_PROBE_CONST = 1;\n")
    with (tmp_path / "js" / "obj-reorder.js").open("a", encoding="utf-8") as handle:
        handle.write("\nfunction objProbeRead() {\n  return OBJ_PROBE_CONST;\n}\n")
    monkeypatch.setattr(sys.modules[__name__], "FRONTEND", tmp_path)
    return [gap for gap in lazy_to_lazy_gaps() if "OBJ_PROBE_CONST" in gap]


def test_a_const_read_from_a_file_later_in_the_chain_is_a_gap(tmp_path, monkeypatch):
    """The 2026-11-01 E2E pageerror (`OBJ_EDITABLE is not defined`): obj-reorder.js
    read a top-level const obj-clip.js, which loads after it, defined. The same
    read is fine from a file that loads first (obj-ref.js, obj-order.js)."""
    late = _probe_gaps(tmp_path / "late", monkeypatch, "obj-clip.js")
    assert late and late[0].startswith("obj-reorder.js:"), late
    assert not _probe_gaps(tmp_path / "early", monkeypatch, "obj-ref.js")
    assert not _probe_gaps(tmp_path / "earlier", monkeypatch, "obj-drag.js")


def test_the_object_move_chain_is_read_in_load_order():
    chains = dict(_loader_chains())
    assert chains["obj-ref.js"] == ["obj-order.js", "obj-drag.js", "obj-reorder.js", "obj-clip.js", "obj-carry.js", "obj-tray.js"]


def test_a_wrapped_file_s_window_exports_are_its_globals():
    """doc23-1102: files wrapped in one closure declare nothing at column zero; their
    `Object.assign(window, {...})` names are what the lints above must see."""
    assert _window_exports("(() => {\n  function a() {}\n  Object.assign(window, { a, b: a, c });\n})();\n") == {"a", "b", "c"}
    assert "docMathRender" in _top_level_functions(FRONTEND / "js" / "documents-math.js")
    funcs, _ = _top_level_bindings(FRONTEND / "js" / "documents-history.js")
    assert "docDiffLines" in funcs
