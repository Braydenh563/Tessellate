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
#: docs-1101: the history dialog's list, texts and open diff moved into documents-history.js's closure,
#: which lets go of them when the dialog closes, so they are no longer module-level names here.
#: doc22-1102: docNoteTypes, docNoteTypesAsked and docPropsDrawn (note types per notebook, two flags) moved
#: into documents-props.js's closure, so they are no longer module-level names here.
EXEMPT = {
    "uiStateOnServer": "the notebook's mirrored settings",
    "paletteUsage": "which palette commands were used, per notebook",
    "askHistoryTotal": "reset with the Ask history list (loadAskHistoryBadge reads it again)",
    "askBadgeTotal": "read again by loadAskHistoryBadge in the swap",
    "manageCategoriesRedraw": "a redraw callback, not data",
    "wbMapNoteState": "the map's open note panel (UI, not data): closed on the next redraw when its object is gone (wbMapCloseNote)",
    "extractProposal": "the extract preview, closed with its dialog",
    "attachedWebPage": "a page the person fetched, not a space's row",
    "webEngineInfo": "the web search engine, per notebook",
    "featureAiTools": "feature list, per notebook",
    "quickEditing": "a flag",
    "docPyStdlibLoad": "a download state",
    "docVariantFor": "a document's variant key, cleared with the document",
    "docFocusSavedWatch": "a flag",
    "storageInfo": "disk use of the whole notebook",
    "editorDocumentCache": "the editor's script, not a row",
    "entityPageClose": "a callback",
    "gcTopicAsk": "an in-flight guard",
    "graphPaneShownId": "cleared by the graph's own draw",
    "graphHighlightIds": "reset in the graph row",
    "graphGroupOf": "reset in the graph row",
    "graphTrace": "reset in the graph row",
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
    # Indent-aware: a file wrapped in one closure (audit row 37a) declares its module state two spaces in.
    gone = [n for n in EXEMPT if not re.search(rf"^\s*(?:let|var|const) {n}\b", everything, re.M)]
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
const grid = (id) => ({ id, classList: { add: (name) => log.push(["hide:" + id, name]) }, replaceChildren: () => log.push("clear:" + id), closest: (sel) => (sel === "#tab-" + ctx.document.body.dataset.tab ? (id === ctx.__activePane ? {} : null) : null) });
const ctx = {
  store, dialog,
  console, Math, Number, Object, Set, Map, JSON, Date, Array, String, Promise, Boolean, Error, CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
  log, events,
  api: { epoch: 0 },
  prefs: { get: (key, dflt) => (key in store ? store[key] : dflt), set: (key, value) => { store[key] = value; log.push(["pref", key, value]); } },
  SPACE_ALL: "all",
  activeSpaceId: () => ctx.api.space ?? (store.spaceId || "all"),
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
  docs: [1], docBlockTextCache: new Map([[1, 1]]), docHistories: new Map([[1, 1]]), docsMadeThisSession: new Set([1]),
  docDirty: false, currentDoc: null,
  saveDocument: async () => { log.push("saveDocument"); ctx.docDirty = false; },
  showNoDocument: () => { log.push("showNoDocument"); ctx.currentDoc = null; },
  wbFlushNudge: async () => { log.push("wbFlushNudge"); },
  wbShowBoardsLanding: () => log.push("wbShowBoardsLanding"),
  showEntrySkeletons: () => log.push("skeletons"),
  loadEntries: async () => { log.push(["loadEntries", ctx.activeSpaceId()]); },
  loadRecentQuestions: async () => { log.push(["loadRecentQuestions", ctx.activeSpaceId()]); },
  loadAskHistoryBadge: async () => { log.push(["loadAskHistoryBadge", ctx.activeSpaceId()]); },
  loadSuggestions: async () => { log.push(["loadSuggestions", ctx.activeSpaceId()]); },
  loadMostUsed: async () => { log.push(["loadMostUsed", ctx.activeSpaceId()]); },
  loadSpaces: async () => { log.push(["loadSpaces", ctx.activeSpaceId()]); },
  loadConversationList: async () => { log.push(["loadConversationList", ctx.activeSpaceId()]); },
  pollReminders: () => { log.push(["pollReminders", ctx.activeSpaceId()]); },
  refreshActiveTab: async () => { log.push(["refreshActiveTab", ctx.activeSpaceId()]); },
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


# --- a read still in flight from the old space is dropped --------------------------

API_HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const text = fs.readFileSync(process.argv[1], "utf8");
const start = text.indexOf("async function api(path, options = {}) {");
const source = text.slice(start, text.indexOf("\n}\n", start) + 3);
const toasts = [];
let release = null;
const ctx = {
  console, Error, Object, Promise, TypeError, Set, JSON, setTimeout, clearTimeout, FormData: class {}, AbortController,
  toasts, JOB_STARTING_PATH: /^$/,
  refuseStagedUrls() {}, clearApiCache() {}, authToken: () => "t", activeSpaceId: () => "alpha",
  noteServerUp() {}, noteServerDown() {}, showLockScreen() {}, recordBrowserLog() {}, plainHttpError: () => "bad",
  kickBackgroundTaskPoll() {}, setActiveSpace() {}, SPACE_ALL: "all",
  toast: Object.assign((m) => toasts.push(m), { refused: new Set() }),
  //: A fetch that answers when the test says so, with the kind of body it is told.
  fetch: () => new Promise((resolve) => { release = (type) => resolve({ ok: true, status: 200, headers: { get: () => type }, json: async () => ({}) }); }),
};
vm.createContext(ctx);
vm.runInContext(source + "\napi.retries = 0; api.epoch = 0;", ctx);
ctx.__out = (value) => process.stdout.write(JSON.stringify(value));
ctx.__release = (type) => release(type);
vm.runInContext("(async () => {" + process.argv[2] + "})()", ctx).catch((e) => { console.error(e); process.exit(1); });
"""


def _run_api(body: str):
    proc = subprocess.run(["node", "-e", API_HARNESS, str(JS_DIR / "app.js"), body], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout)


@needs_node
def test_a_read_that_started_before_a_switch_is_refused_when_it_lands() -> None:
    out = _run_api("""
    const outcome = async (options, type, switched) => {
      const call = api("/entries", options).then(() => "applied", (e) => (e.isStale ? "stale" : "other:" + e.message));
      await new Promise((r) => setTimeout(r, 0));
      if (switched) api.epoch += 1;
      __release(type);
      return call;
    };
    __out({
      read: await outcome({}, "application/json", true),
      readNoSwitch: await outcome({}, "application/json", false),
      write: await outcome({ method: "POST" }, "application/json", true),
      readOnlyPost: await outcome({ method: "POST", readOnly: true }, "application/json", true),
      file: await outcome({}, "image/png", true),
    });
    """)
    assert out == {
        "read": "stale",
        "readNoSwitch": "applied",
        "write": "applied",
        "readOnlyPost": "stale",
        "file": "applied",
    }, "a JSON read from the old space is dropped; a write and a file are not"


def test_the_swap_bumps_the_epoch_the_request_helper_reads() -> None:
    swap, app = _code(SWAP.read_text(encoding="utf-8")), _code(_text("app.js"))
    assert "api.epoch += 1" in swap and "spaceState.epoch" not in swap
    assert "sentAt !== api.epoch" in app
    for name in ("app.js", "lag-watch.js", "boot-guard.js"):
        assert "isStale" in _text(name), f"{name} would log a dropped read as an unhandled rejection"
    toast = re.search(r"^function toast\(.*?^\}", _text("status.js"), re.S | re.M).group(0)
    assert 'endsWith("Space changed.")' in toast


# --- a toast's own Undo goes back to its space first -------------------------------

TOAST_HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const text = fs.readFileSync(process.argv[1], "utf8");
const start = text.indexOf("function keepToastAction(");
const source = text.slice(start, text.indexOf("\n}\n", start) + 3);
const log = [];
let here = "alpha";
const ctx = {
  Date, Promise, log, noticeLive: new Map(), undoStack: [], NOTICE_UNDO_MS: 1000,
  recordNotification: () => 1, activeSpaceId: () => here, toast: (m, e) => log.push(["toast", m, e]),
  voiceLine: (key, slots) => `Couldn't ${slots.what}.`,
  spaceEnterFor: async (a) => { log.push(["enter", a.space]); return a.space !== "gone"; },
};
vm.createContext(ctx);
vm.runInContext(source, ctx);
ctx.__out = (v) => process.stdout.write(JSON.stringify(v));
ctx.__here = (v) => { here = v; };
vm.runInContext("(async () => {" + process.argv[2] + "})()", ctx).catch((e) => { console.error(e); process.exit(1); });
"""


@needs_node
def test_a_toast_undo_pressed_after_a_switch_enters_its_space_first() -> None:
    proc = subprocess.run(
        ["node", "-e", TOAST_HARNESS, str(JS_DIR / "status.js"), """
    const ran = () => log.push(["ran"]);
    const undo = keepToastAction("Deleted", "Undo", ran);
    __here("beta");
    await undo();
    const open = keepToastAction("Saved", "Open it", ran);
    await open();
    const bare = keepToastAction("Deleted", "Undo", ran, { record: false });
    await bare();
    __here("gone");
    const lost = keepToastAction("Deleted", "Undo", ran);
    __here("beta");
    await lost();
    __out(log);
    """],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert json.loads(proc.stdout) == [
        ["enter", "alpha"], ["ran"],
        ["ran"],
        ["enter", "beta"], ["ran"],
        ["enter", "gone"], ["toast", "Couldn't go back to the space it was made in.", "info"],
    ]


# --- a second window hears the switch ----------------------------------------------

@needs_node
def test_a_heard_switch_follows_in_place_and_does_not_write_the_pref_again() -> None:
    out = _run("""
    store.spaceId = "alpha";
    await swapSpace("beta", true);
    __out({ pref: log.filter((e) => e[0] === "pref"), space: activeSpaceId(), reads: log.filter((e) => e[0] === "loadEntries") });
    """)
    assert out["pref"] == [], "the window that made the switch wrote the pref; this one only follows"
    assert out["space"] == "beta" and out["reads"] == [["loadEntries", "beta"]]


def test_the_window_keeps_its_own_space_until_it_has_heard_the_storage_event() -> None:
    app = _code(_text("app.js"))
    reader = re.search(r"^function activeSpaceId\(\) \{.*?^\}", app, re.S | re.M).group(0)
    assert "api.space ??=" in reader, "the header must name this window's space, not the pref another window wrote"
    assert "prefs.set(" not in reader


@needs_node
def test_the_storage_event_for_the_space_pref_swaps_and_a_hidden_tab_waits() -> None:
    text = _code(_text("spaces-find.js"))
    block = text[text.index("{\n  const follow") : text.index("\n}\n", text.index("{\n  const follow")) + 3]
    harness = r"""
    const vm = require("vm");
    const calls = [], listeners = {}, doc = { hidden: false, addEventListener: (t, f) => { listeners[t] = f; } };
    const ctx = {
      document: doc, prefs: { get: () => ctx.__pref }, __pref: "beta",
      activeSpaceId: () => ctx.__here, __here: "alpha",
      swapSpace: (id, heard) => calls.push([id, heard]),
      window: { addEventListener: (t, f) => { listeners[t] = f; } },
    };
    vm.createContext(ctx);
    vm.runInContext(process.argv[1], ctx);
    listeners.storage({ key: "other" });
    listeners.storage({ key: "spaceId" });
    ctx.__here = "beta"; listeners.storage({ key: "spaceId" });
    doc.hidden = true; ctx.__here = "alpha"; delete listeners.visibilitychange;
    listeners.storage({ key: "spaceId" });
    const waited = calls.length === 1 && typeof listeners.visibilitychange === "function";
    doc.hidden = false; listeners.visibilitychange();
    process.stdout.write(JSON.stringify({ calls, waited }));
    """
    proc = subprocess.run(["node", "-e", harness, block], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert json.loads(proc.stdout) == {"calls": [["beta", True], ["beta", True]], "waited": True}


@needs_node
def test_the_visible_notes_list_is_emptied_at_the_flip_with_its_skeletons() -> None:
    """The old rows must not stand under the new space's name until the load lands (z1c-1101:
    1 to 6 frames of the old space's rows, 4.1 a switch over 10 switches, 0 after). The panes above
    stay left to their loads; the notes list is the one that has its own loading recipe."""
    out = _run("""
    store.spaceId = "alpha"; globalThis.document.body.dataset.tab = "notes"; globalThis.__activePane = "entry-list";
    await swapSpace("beta");
    __out(log.map((e) => (typeof e === "string" ? e : e[0])));
    """)
    assert "clear:entry-list" in out and "skeletons" in out
    assert out.index("clear:entry-list") < out.index("skeletons") < out.index("loadEntries")
    assert "hide:empty-message" in out and "hide:no-match-message" in out
