"""A space switch swaps the data in place (INBOX 1520, audit 1031 Z1).

No page reload follows a switch, so the tray and the Undo stack carry across
spaces; every cache a space leaves in memory is forgotten (`SPACE_SCOPED` in
space-swap.js), and an `apiJson`-fed collection nobody listed fails here.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR, LAZY_ENTRIES, app_js_files

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")
SWAP = JS_DIR / "space-swap.js"


def _text(name: str) -> str:
    return (JS_DIR / name).read_text(encoding="utf-8")


def _code(text: str) -> str:
    """The file without its comment lines, so prose naming a call is not the call."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def test_no_reload_follows_a_space_change() -> None:
    for name in ("spaces-find.js", "batch-space.js", "space-swap.js"):
        assert "location.reload" not in _code(_text(name)), f"{name} reloads the page"
    setter = re.search(r"^function setActiveSpace\(id\) \{.*?^\}", _text("spaces-find.js"), re.S | re.M)
    assert setter, "setActiveSpace is gone"
    body = setter.group(0)
    assert "swapSpace(id)" in body and "reload" not in body.replace("reloads", "")
    #: `swapSpace` is a stand-in that loads the module on the first switch.
    entries = LAZY_ENTRIES.read_text(encoding="utf-8")
    assert re.search(r'spaceSwap: \["swapSpace", "spaceEnterFor"\]', entries)


def test_only_the_swap_writes_the_space_pref() -> None:
    writers = [
        path.name
        for path in JS_DIR.glob("*.js")
        if 'prefs.set("spaceId"' in _code(path.read_text(encoding="utf-8"))
    ]
    assert writers == ["space-swap.js"], writers


def test_the_swap_is_a_lazy_module_and_part_of_the_app_text() -> None:
    assert re.search(r'spaceSwap: \["/js/space-swap\.js"\]', LAZY_ENTRIES.read_text(encoding="utf-8"))
    from tests._app_js import LAZY_PIECES

    assert "space-swap.js" in LAZY_PIECES
    assert "space-swap.js" not in [p.name for p in app_js_files()], "it loads on the first switch, not at boot"


def test_an_undo_entry_remembers_its_space_and_runs_after_a_switch_back() -> None:
    status = _text("status.js")
    assert re.search(r"const action = \{ label, undo, redo, at: Date\.now\(\), space: activeSpaceId\(\) \};", status)
    for run in ("performUndoNow", "performRedoNow"):
        body = re.search(rf"async function {run}\(\) \{{.*?^\}}", status, re.S | re.M).group(0)
        assert "spaceEnterFor" in body, f"{run} does not go back to the entry's space first"


def test_deleting_the_open_space_keeps_its_undo() -> None:
    body = _code(_text("batch-space.js"))
    assert "wasOpen ? null" not in body
    assert 'await setActiveSpace("default")' in body


# --- the lint: every server-fed cache is in the table ------------------------------

#: Module-level collections fed by a request that are not a space's data, each
#: with the reason. A name belongs here only when a row from another space can
#: never be in it.
EXEMPT = {
    "uiStateOnServer": "the notebook's mirrored settings",
    "paletteUsage": "which palette commands were used, per notebook",
    "askHistoryTotal": "reset with the Ask history list (loadAskHistoryBadge reads it again)",
    "askBadgeTotal": "read again by loadAskHistoryBadge in the swap",
    "manageCategoriesRedraw": "a redraw callback, not data",
    "extractProposal": "the extract preview, closed with its dialog",
    "attachedWebPage": "a page the person fetched, not a space's row",
    "webEngineInfo": "the web search engine, per notebook",
    "featureAiTools": "feature list, per notebook",
    "quickEditing": "a flag",
    "docPyStdlibLoad": "a download state",
    "docNoteTypes": "note types, per notebook",
    "docNoteTypesAsked": "a flag",
    "docPropsDrawn": "a flag",
    "docVariantFor": "a document's variant key, cleared with the document",
    "docFocusSavedWatch": "a flag",
    "docHistoryOpenDiff": "an open diff, closed with the document",
    "storageInfo": "disk use of the whole notebook",
    "editorDocumentCache": "the editor's script, not a row",
    "entityPageClose": "a callback",
    "gcTopicAsk": "an in-flight guard",
    "graphPaneShownId": "cleared by the graph's own draw",
    "graphHighlightIds": "reset in the graph row",
    "graphGroupOf": "reset in the graph row",
    "graphTrace": "reset in the graph row",
    "bookmarkGroupFilter": "a filter name chosen on the page",
    "contentsTopics": "the topics of an open document, redrawn on open",
    "docFileTypes": "file types, per notebook",
    "librarySemanticIds": "the ids of one search, replaced by the next",
    "ocrPageCounts": "a count per open file, redrawn on open",
    "marginDismissed": "per note id, harmless across spaces",
    "voiceStatus": "the speech helper",
    "meetingStream": "a live stream",
    "recordingWatches": "a live watch",
    "ocrEngineLatest": "the OCR engine's version",
    "ocrEngineTimer": "a timer",
    "noteOutboxFlushing": "a flag",
    "noteOutboxTimer": "a timer",
    "privacyReceipt": "a receipt of the whole notebook",
    "creditsLoad": "a promise for static text",
    "helpTopicsLoad": "a promise for static text",
    "modelCatalogNames": "the model catalogue",
    "modelCustom": "the model catalogue",
    "prefsCache": "the notebook's settings",
    "prefsInflight": "a request guard",
    "prefsSaveInFlight": "a request guard",
    "forgottenOrder": "the Forgotten list's sort",
    "changelogLoaded": "static text",
    "jobRunsInFlight": "jobs of the whole notebook",
    "jobRunsList": "jobs of the whole notebook",
    "jobRunsTimer": "a timer",
    "learnedOffset": "what the notebook learned",
    "learnedTotal": "what the notebook learned",
    "logRecords": "the app's log",
    "logStreamCursor": "the app's log",
    "samplingState": "model settings",
    "isDesktopShell": "the window",
    "skillsCache": "skills, per notebook",
    "backgroundTasks": "tasks of the whole notebook",
    "jobPollKick": "a timer",
    "modelStatus": "the model's state",
    "modelStatusProblem": "the model's state",
    "statusEverAnswered": "a flag",
    "tagSuggestOpening": "a flag",
    "editorFileCache": "the files of the code editor's folder, not a space's rows",
    "wbLibSets": "the board library's shape sets, per notebook",
    "wbSelectedItem": "the selection on an open board, closed with it",
    "wbUndoParents": "the board's own history, closed with it",
    "autoSessionPending": "sign-in state",
    "lockedByHand": "sign-in state",
    "pinHere": "sign-in state",
    "vaultOpen": "sign-in state",
    "_apiCache": "cleared by clearApiCache() in the swap",
    "currentDoc": "closed by the swap (showNoDocument)",
    "docDirty": "saved and reset by the swap",
    "docHistoryEntries": "reset in the documents row",
    "docHistoryContent": "reset in the documents row",
    "docBlockTextCache": "reset in the documents row",
    "docsMadeThisSession": "reset in the documents row",
    "docs": "reset in the documents row",
    "spacesCache": "read again by loadSpaces in the swap",
    "captureDocumentTitles": "reset in the chat row",
    "attachmentMetaCache": "reset in the notes row",
    "categoryMeta": "reset in the notes row",
    "notesRailCache": "reset in the notes row",
    "finderCounts": "reset in the search row",
    "finderHits": "reset in the search row",
    "thumbUrlCache": "reset in the notes row",
    "timelineById": "reset in the timeline row",
    "timelineDensity": "reset in the timeline row",
    "timelineNextCursor": "reset in the timeline row",
    "timelineRows": "reset in the timeline row",
    "bookmarksCache": "reset in the library row",
    "libraryItems": "reset in the library row",
    "libraryMediaSelection": "reset in the library row",
    "librarySelection": "reset in the library row",
}

DECL = re.compile(r"^(?:let|var|const) ([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\[\]|new Map\(\)|new Set\(\)|\{\}|null|\"\"|0|false)", re.M)
CALL = re.compile(r"\b(?:apiJson|api|apiPagedList)\(")


def _fed_by_a_request() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(JS_DIR.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        names = {m.group(1) for m in DECL.finditer(text)}
        lines = text.split("\n")
        for at, line in enumerate(lines):
            if not CALL.search(line):
                continue
            block = "\n".join(lines[at : at + 14])
            for name in names:
                if re.search(rf"(?<![\w.]){name}\s*=[^=>]|(?<![\w.]){name}\.(set|push|add)\(", block):
                    found.setdefault(name, set()).add(path.name)
    return found


def test_every_server_fed_collection_is_forgotten_or_exempt() -> None:
    swap = _code(SWAP.read_text(encoding="utf-8"))
    missing = {}
    for name, files in _fed_by_a_request().items():
        if name in EXEMPT or re.search(rf"\b{name}\b", swap):
            continue
        missing[name] = sorted(files)
    assert not missing, (
        "a module-level cache fed by a request is not in space-swap.js's SPACE_SCOPED "
        f"(add a reset, or an EXEMPT row with the reason): {missing}"
    )


def test_every_exempt_name_still_exists() -> None:
    everything = "\n".join(p.read_text(encoding="utf-8") for p in JS_DIR.glob("*.js"))
    gone = [n for n in EXEMPT if not re.search(rf"^(?:let|var|const) {n}\b", everything, re.M)]
    assert not gone, f"EXEMPT names that no longer exist: {gone}"


def test_every_name_the_table_resets_is_declared() -> None:
    swap = _code(SWAP.read_text(encoding="utf-8"))
    table = swap[swap.index("const SPACE_SCOPED") : swap.index("const SPACE_PANES")]
    names = set(re.findall(r"^\s{4}([A-Za-z_]\w*)(?: = |\.clear\(\))", table, re.M))
    names |= set(re.findall(r"^\s{4}[A-Za-z_]\w* = ([A-Za-z_]\w*) = ", table, re.M))
    everything = "\n".join(p.read_text(encoding="utf-8") for p in JS_DIR.glob("*.js"))
    undeclared = sorted(
        n for n in names if not re.search(rf"^(?:let|var|const) {n}\b", everything, re.M)
    )
    assert not undeclared, f"the table resets names no script declares: {undeclared}"


# --- behaviour ---------------------------------------------------------------------

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const log = [];
const events = [];
const store = {};
const dialog = { close: () => log.push("dialog.close") };
const grid = (id) => ({ id, replaceChildren: () => log.push("clear:" + id), closest: (sel) => (sel === "#tab-" + ctx.document.body.dataset.tab ? (id === ctx.__activePane ? {} : null) : null) });
const ctx = {
  store, dialog,
  console, Math, Number, Object, Set, Map, JSON, Date, Array, String, Promise, Boolean, Error, CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
  log, events,
  prefs: { get: (key, dflt) => (key in store ? store[key] : dflt), set: (key, value) => { store[key] = value; log.push(["pref", key, value]); } },
  SPACE_ALL: "all",
  activeSpaceId: () => store.spaceId || "all",
  clearApiCache: () => log.push("clearApiCache"),
  closeSpaceMenu: () => log.push("closeSpaceMenu"),
  renderSpaceMenu: () => log.push("renderSpaceMenu"),
  updateCaptureSpaceLabel: () => log.push("updateCaptureSpaceLabel"),
  toast: (text) => log.push(["toast", text]),
  $: (id) => (id === "note-search" ? ctx.__box : grid(id)),
  __box: { value: "x" },
  __activePane: "",
  document: {
    body: { dataset: { tab: "notes" } },
    querySelectorAll: () => ctx.__dialogs,
    dispatchEvent: (event) => { events.push(event); log.push(["event", event.type, event.detail.id, event.detail.from]); },
  },
  __dialogs: [],
  window: null,
  spacesCache: [{ id: "alpha", name: "Alpha" }, { id: "beta", name: "Beta" }],
  // the data the swap forgets
  allEntries: [{ id: 1 }], entriesEverLoaded: true, entriesComplete: true, activeCategory: "Cooking", draftsOnly: true, favouritesOnly: true,
  editingId: 4, inlineAction: {}, linkSource: 2, noteSearch: "q", noteSearchCorrection: {}, notesCurrentPage: 3,
  noteSearchWhy: new Map([[1, 1]]), attachmentMetaCache: new Map([[1, 1]]), categoryMeta: new Map([["a", 1]]), notesRailCache: new Map([[1, 1]]),
  referenceCountsCache: new Map([[1, 1]]), reminderCountsCache: new Map([[1, 1]]), noteTopicsCache: new Map([[1, 1]]), thumbUrlCache: new Map([[1, 1]]),
  mapBoardIndexCache: {}, objOrderCache: new Map([[1, 1]]),
  dashStatsInflight: {}, dashGraphInflight: {}, dashRemindersInflight: {}, dashStatsAt: 5, dashGraphAt: 5, dashRemindersAt: 5,
  attachedNoteIds: [1], attachedImages: [1], attachedDocuments: [1], attachedBoards: [1], attachedFiles: [1],
  renderAttachments() {}, renderImageAttachments() {}, renderDocumentAttachments() {}, renderBoardAttachments() {}, renderFileAttachments() {},
  captureDocumentList: [1], captureDocumentTitles: new Map([[1, 1]]), captureDocuments: new Set([1]),
  chatConv: { id: 9, turns: [] }, conversation: [1],
  newChatConversation() { log.push("newChatConversation"); ctx.chatConv = { id: null, turns: [] }; },
  newChat() { log.push("newChat"); ctx.conversation = []; },
  finderHits: [1], finderCounts: { a: 1 }, finderIndexTotals: { a: 1 },
  timelineRows: [1], timelineById: new Map([[1, 1]]), timelineDensity: { a: 1 }, timelineGroupNames: ["a"], timelineNextCursor: "c",
  graphStructure: {}, graphAdjacency: {}, graphTrace: {}, graphTraceRoutes: [1], graphHighlightIds: {}, graphHiddenCategories: new Set([1]),
  graphHiddenKeys: new Set([1]), graphGroupOf: new Map([[1, 1]]), graphPopupId: 3, gcTopicSummaries: new Map([[1, 1]]),
  libraryItems: [1], libraryCounts: { a: 1 }, libraryOverview: { a: 1 }, libraryTruncated: { a: 1 }, libraryDocsAll: [1], libraryImagesCache: [1], bookmarksCache: [1],
  librarySelection: new Set([1]), libraryDocsSelection: new Set([1]), libraryMediaSelection: new Map([[1, 1]]), libraryBoardsSelection: new Map([[1, 1]]), libraryLinksSelection: new Map([[1, 1]]),
  docs: [1], docBlockTextCache: new Map([[1, 1]]), docHistoryEntries: [1], docHistoryContent: new Map([[1, 1]]), docHistories: new Map([[1, 1]]), docsMadeThisSession: new Set([1]),
  docDirty: false, currentDoc: null,
  saveDocument: async () => { log.push("saveDocument"); ctx.docDirty = false; },
  showNoDocument: () => { log.push("showNoDocument"); ctx.currentDoc = null; },
  wbFlushNudge: async () => { log.push("wbFlushNudge"); },
  wbShowBoardsLanding: () => log.push("wbShowBoardsLanding"),
  loadEntries: async () => { log.push(["loadEntries", store.spaceId]); },
  loadRecentQuestions: async () => { log.push(["loadRecentQuestions", store.spaceId]); },
  loadAskHistoryBadge: async () => { log.push(["loadAskHistoryBadge", store.spaceId]); },
  loadSuggestions: async () => { log.push(["loadSuggestions", store.spaceId]); },
  loadMostUsed: async () => { log.push(["loadMostUsed", store.spaceId]); },
  loadSpaces: async () => { log.push(["loadSpaces", store.spaceId]); },
  loadConversationList: async () => { log.push(["loadConversationList", store.spaceId]); },
  pollReminders: () => { log.push(["pollReminders", store.spaceId]); },
  refreshActiveTab: async () => { log.push(["refreshActiveTab", store.spaceId]); },
  undoStack: [{ label: "kept" }], objTray: [{ id: 1 }],
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], "utf8"), ctx, { filename: "space-swap.js" });
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
vm.runInContext("(async () => {" + process.argv[2] + "})()", ctx).catch((e) => { console.error(e); process.exit(1); });
"""


def _run(body: str):
    proc = subprocess.run(
        ["node", "-e", HARNESS, str(SWAP), body],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)


@needs_node
def test_a_switch_forgets_every_cache_reloads_and_keeps_undo_and_tray() -> None:
    out = _run("""
    store.spaceId = "alpha";
    await swapSpace("beta");
    const names = ["allEntries", "entriesEverLoaded", "activeCategory", "noteSearch", "attachedNoteIds", "timelineRows", "libraryItems",
      "docs", "graphStructure", "finderHits", "dashRemindersInflight", "mapBoardIndexCache", "captureDocumentList"];
    const left = names.filter((n) => { const v = globalThis[n]; return Array.isArray(v) ? v.length : v; });
    const maps = ["noteSearchWhy", "attachmentMetaCache", "referenceCountsCache", "thumbUrlCache", "objOrderCache", "librarySelection", "docHistories", "gcTopicSummaries"]
      .filter((n) => globalThis[n].size);
    __out({ left, maps, undo: globalThis.undoStack.length, tray: globalThis.objTray.length, box: globalThis.__box.value, space: store.spaceId, log, chat: globalThis.chatConv.id });
    """)
    assert out["left"] == [] and out["maps"] == []
    assert out["undo"] == 1 and out["tray"] == 1, "Undo and the tray carry across the switch"
    assert out["space"] == "beta" and out["box"] == ""
    log = out["log"]
    flat = [e if isinstance(e, str) else e[0] for e in log]
    assert flat.index("clearApiCache") > flat.index("pref") if "pref" in flat else True
    # every read starts after the new space is the one the header names
    for step in ("loadEntries", "loadRecentQuestions", "loadAskHistoryBadge", "loadSuggestions", "loadMostUsed", "loadSpaces", "loadConversationList", "pollReminders", "refreshActiveTab"):
        assert [step, "beta"] in log, step
    assert log.index(["loadEntries", "beta"]) < log.index(["refreshActiveTab", "beta"])
    assert ["event", "spacechange", "beta", "alpha"] in log
    assert "newChatConversation" in log and out["chat"] is None
    assert "wbShowBoardsLanding" not in log


@needs_node
def test_what_is_open_is_saved_before_the_header_changes() -> None:
    out = _run("""
    store.spaceId = "alpha"; globalThis.docDirty = true; globalThis.currentDoc = { id: 7 }; globalThis.currentBoardId = 3;
    globalThis.__dialogs = [dialog];
    await swapSpace("beta");
    __out(log);
    """)
    flat = [e if isinstance(e, str) else e[0] for e in out]
    assert flat.index("saveDocument") < flat.index("pref")
    assert flat.index("showNoDocument") < flat.index("pref")
    assert flat.index("wbShowBoardsLanding") < flat.index("pref")
    assert "dialog.close" in flat


@needs_node
def test_panes_of_other_tabs_are_emptied_and_the_visible_one_is_left_to_its_load() -> None:
    out = _run("""
    store.spaceId = "alpha"; globalThis.document.body.dataset.tab = "library"; globalThis.__activePane = "library-grid";
    await swapSpace("beta");
    __out(log.filter((e) => typeof e === "string" && e.startsWith("clear:")));
    """)
    assert "clear:library-grid" not in out
    assert {"clear:dash-grid", "clear:doc-list", "clear:reminder-groups", "clear:timeline-feed"} <= set(out)


@needs_node
def test_a_second_switch_waits_for_the_first_and_the_same_space_is_a_no_op() -> None:
    out = _run("""
    store.spaceId = "alpha";
    await swapSpace("alpha");
    const noop = log.filter((e) => typeof e !== "string" && e[0] === "loadEntries").length;
    const first = swapSpace("beta");
    const second = swapSpace("all");
    await Promise.all([first, second]);
    const spaces = log.filter((e) => typeof e !== "string" && e[0] === "pref").map((e) => e[2]);
    __out({ noop, spaces, final: store.spaceId });
    """)
    assert out == {"noop": 0, "spaces": ["beta", "all"], "final": "all"}


@needs_node
def test_undo_from_another_space_says_so_and_goes_back_first() -> None:
    out = _run("""
    store.spaceId = "beta";
    const here = await spaceEnterFor({ label: "x", space: "beta" });
    const fromAll = (store.spaceId = "all", await spaceEnterFor({ label: "x", space: "alpha" }));
    const noSpace = await spaceEnterFor({ label: "old" });
    store.spaceId = "beta";
    const back = await spaceEnterFor({ label: "x", space: "alpha" });
    __out({ here, fromAll, noSpace, back, space: store.spaceId, toasts: log.filter((e) => e[0] === "toast").map((e) => e[1]) });
    """)
    assert out["here"] and out["fromAll"] and out["noSpace"], "same space, All spaces and an old entry need no switch"
    assert out["back"] and out["space"] == "alpha"
    assert out["toasts"] == ["That was in Alpha. Switching back to it."]
