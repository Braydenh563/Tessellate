// space-swap.js: a space switch swaps the data in place (INBOX 1520, audit
// 1031 Z1). Lazy, loaded by the first switch (`setActiveSpace`, spaces-find.js).
//
// It used to be `location.reload()`, which kept the tray (sessionStorage) but
// emptied the Undo stack, re-paid the whole boot, and put the person back on
// the Dashboard's first paint. Every list in the app is scoped by the
// `X-Workspace-ID` header, so the swap has three parts, in this order:
//   1. leave the old space: what is open there is saved and closed, while the
//      header still names it (a save sent after the switch would land in the
//      new space);
//   2. forget what the old space left in memory: `SPACE_SCOPED`, one row per
//      surface, naming every module-level cache fed by the server. A cache
//      missing from the table is a row from the old space that outlives the
//      switch, so `tests/test_space_swap_z1.py` fails on an `apiJson`-fed
//      collection that is neither here nor on its short exempt list;
//   3. read the new space again, the same steps `startApp` runs, and let every
//      other tab draw on its next visit (the visit loads its data already; the
//      panes are emptied here so it never flashes the old rows first).
// The Undo stack and the tray are not in the table on purpose: they carry
// across. An Undo entry remembers the space it was made in (`pushUndo`), and
// `spaceEnterFor` takes the person back there before it runs.

//: `const`, not two `let`s: the global-scope ratchet counts top-level lets.
(() => {
  const spaceState = { running: null };

  //: Every cache a space's data leaves in memory, by surface. A lazy surface's
  //: row starts with a `typeof` guard: its names do not exist until its file is in.
  const SPACE_SCOPED = {
    notes() {
      allEntries = [];
      entriesEverLoaded = false;
      entriesComplete = false;
      activeCategory = null;
      draftsOnly = false;
      favouritesOnly = false;
      editingId = null;
      inlineAction = null;
      linkSource = null;
      noteSearch = "";
      noteSearchCorrection = null;
      notesCurrentPage = 1;
      noteSearchWhy.clear();
      attachmentMetaCache.clear();
      categoryMeta = new Map();
      notesRailCache.clear();
      referenceCountsCache.clear();
      reminderCountsCache.clear();
      noteTopicsCache.clear();
      thumbUrlCache.clear();
      mapBoardIndexCache = null;
      mapBoardIndexAt = 0;
      mapBoardIndexWalk = null;
      if (typeof objOrderCache !== "undefined") objOrderCache.clear();
      //: The way back for a large settings change is held in memory only; it is not carried into another space.
      if (typeof settingsHistoryBigKept !== "undefined") settingsHistoryBigKept.clear();
      const box = $("note-search");
      if (box) box.value = "";
      //: The list is drawn from `allEntries`, not read from it, so emptying the array left the old
      //: space's rows on screen under the new name until the load landed (24 to 75 ms measured).
      //: The list's own loading recipe stands in: its skeletons, drawn here at the flip, and the
      //: render that follows the load replaces them. The two notices are the old space's too.
      const list = $("entry-list");
      if (list) {
        list.replaceChildren();
        $("empty-message")?.classList.add("hidden");
        $("no-match-message")?.classList.add("hidden");
        if (typeof showEntrySkeletons === "function") showEntrySkeletons();
      }
    },
    dashboard() {
      dashStatsInflight = null;
      dashGraphInflight = null;
      dashRemindersInflight = null;
      dashStatsAt = dashGraphAt = dashRemindersAt = 0;
    },
    chat() {
      attachedNoteIds = [];
      attachedImages = [];
      attachedDocuments = [];
      attachedBoards = [];
      attachedFiles = [];
      renderAttachments();
      renderImageAttachments();
      renderDocumentAttachments();
      renderBoardAttachments();
      renderFileAttachments();
      captureDocumentList = [];
      captureDocumentTitles = new Map();
      captureDocuments.clear();
      //: A half-typed model address is the old space's: the status poll fills the field again.
      backendFieldsDirty = false;
      //: The open thread belongs to the space it was held in.
      if (typeof newChatConversation === "function" && chatConv?.id != null) newChatConversation();
      if (typeof newChat === "function" && conversation.length) newChat();
    },
    search() {
      if (typeof finderHits === "undefined") return;
      finderHits = [];
      finderCounts = {};
      finderIndexTotals = {};
    },
    timeline() {
      if (typeof timelineRows === "undefined") return;
      timelineRows = [];
      timelineById = new Map();
      timelineDensity = {};
      timelineGroupNames = [];
      timelineNextCursor = null;
    },
    graph() {
      if (typeof graphStructure === "undefined") return;
      graphStructure = null;
      graphAdjacency = null;
      graphTrace = null;
      graphTraceRoutes = [];
      graphHighlightIds = null;
      graphHiddenCategories = new Set();
      graphHiddenKeys = new Set();
      graphGroupOf = new Map();
      graphPopupId = null;
      gcTopicSummaries.clear();
      window.gcStop?.();
    },
    library() {
      if (typeof libraryItems === "undefined") return;
      libraryItems = [];
      libraryCounts = {};
      libraryOverview = {};
      libraryTruncated = {};
      libraryDocsAll = [];
      libraryImagesCache = [];
      bookmarksCache = [];
      ocrSiblingCache = null;
      librarySelection.clear();
      libraryDocsSelection.clear();
      libraryMediaSelection.clear();
      libraryBoardsSelection.clear();
      libraryLinksSelection.clear();
      window.wbBoardsAll = [];
      if (typeof libraryBoardsLast !== "undefined") [libraryBoardsLast, libraryBoardsLastText] = [null, ""];
      window.wbLastCreatedBoard = null;
    },
    documents() {
      if (typeof docs === "undefined") return;
      docs = [];
      docBlockTextCache.clear();
      docHistories.clear();
      docsMadeThisSession.clear();
    },
  };

  //: Panes of a tab that is not on screen, emptied so a visit paints from the new
  //: space or from nothing, never from the old rows. Each tab's visit loads its own
  //: data; the Dashboard rebuilds when its grid has no widget in it.
  const SPACE_PANES = ["dash-grid", "library-grid", "doc-list", "reminder-groups", "timeline-feed"];

  //: What is open in the old space is saved and put away, with the header still on it.
  async function spaceLeave() {
    if (typeof docDirty !== "undefined" && docDirty) await saveDocument({ silent: true }).catch(() => {});
    if (typeof wbFlushNudge === "function") await wbFlushNudge().catch(() => {});
    if (typeof docLastTranslateLanguage !== "undefined") docLastTranslateLanguage = "";
    if (typeof currentDoc !== "undefined" && currentDoc) {
      docDirty = false;
      showNoDocument();
    }
    if (window.currentBoardId != null && typeof wbShowBoardsLanding === "function") {
      window.currentBoardId = null;
      wbShowBoardsLanding();
    }
    for (const dialog of document.querySelectorAll("dialog[open]")) dialog.close();
    closeSpaceMenu();
  }

  //: The steps `startApp` runs for the data that is not a tab's own. Each is isolated:
  //: one broken endpoint must not leave the rest on the old space.
  function spaceReload() {
    const steps = [
      ["notes", loadEntries],
      ["recent questions", loadRecentQuestions],
      ["the ask history badge", loadAskHistoryBadge],
      ["suggestions", loadSuggestions],
      ["your most-used items", loadMostUsed],
      ["the spaces", loadSpaces],
      ["conversations", loadConversationList],
      ["reminders", () => pollReminders()],
    ];
    return Promise.all(
      steps.map(([label, run]) =>
        Promise.resolve()
          .then(run)
          .catch((error) => {
            if (!error?.isLockout) toast(voiceLine("failed", { what: `load ${label}`, why: error.message }), true, { retry: run });
          })
      )
    );
  }

  //: `heard`: another window made this switch and wrote the pref already, so this one
  //: must not write it again (it could overwrite a later switch there).
  async function swapSpace(id, heard = false) {
    //: One switch at a time: a second press while the first reads waits its turn.
    if (spaceState.running) {
      await spaceState.running;
      return id === activeSpaceId() ? undefined : swapSpace(id, heard);
    }
    if (id === activeSpaceId()) {
      closeSpaceMenu();
      return undefined;
    }
    spaceState.running = spaceSwapNow(id, heard);
    try {
      await spaceState.running;
    } finally {
      spaceState.running = null;
    }
    return undefined;
  }

  async function spaceSwapNow(id, heard) {
    const from = activeSpaceId();
    await spaceLeave();
    //: This window's own space first, then the pref other windows and new ones read.
    api.space = id;
    if (!heard) prefs.set("spaceId", id);
    //: Reads still in flight under the old space are dropped when they land (`api()`).
    api.epoch += 1;
    clearApiCache();
    for (const [surface, forget] of Object.entries(SPACE_SCOPED)) {
      try {
        forget();
      } catch (error) {
        console.error(`Forgetting ${surface} for the space switch failed:`, error);
      }
    }
    const active = document.body.dataset.tab || "dashboard";
    for (const pane of SPACE_PANES) {
      const node = $(pane);
      if (node && !node.closest(`#tab-${active}`)) node.replaceChildren();
    }
    renderSpaceMenu();
    updateCaptureSpaceLabel();
    document.dispatchEvent(new CustomEvent("spacechange", { detail: { id, from, epoch: api.epoch } }));
    const entries = spaceReload();
    //: After the notes, as `startApp` does: every tab wants them, none should guess.
    await entries;
    if (id !== activeSpaceId()) return;
    try {
      await refreshActiveTab();
    } catch (error) {
      toast(voiceLine("failed", { what: "load this tab", why: error.message }), true, { retry: refreshActiveTab });
    }
  }

  //: An Undo from another space: say so and go back there first, because the
  //: server answers an id of another space with 404. "All spaces" sees every row,
  //: so an entry made there, or an Undo run from there, needs no switch. Resolves
  //: true when the entry may run now.
  async function spaceEnterFor(action) {
    const here = activeSpaceId();
    if (!action.space || action.space === here || here === SPACE_ALL) return true;
    const name = action.space === SPACE_ALL ? "All spaces" : spacesCache.find((s) => s.id === action.space)?.name || action.space;
    toast(`That was in ${name}. Switching back to it.`);
    await swapSpace(action.space);
    return activeSpaceId() === action.space;
  }

  //: The file's whole surface: what other files and the stand-ins call (ranked row 37a).
  Object.assign(window, { swapSpace, spaceEnterFor });
})();
