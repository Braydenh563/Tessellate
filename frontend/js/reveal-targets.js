// reveal-targets.js: landing on the feature a catalogue row names. Moved out
// of settings-panes.js on 2026-10-05 (the boot-script gzip budget, ratchet in
// tests/test_static_compression.py): a row in the palette, Tools and features
// or Quick access reaches `revealFeature` only by a person's click, so none
// of this is needed to draw the first screen. Loaded on first use by
// `LAZY_MODULES.reveal` (app.js), whose stand-in for `revealFeature` fetches
// this file and then calls the real one. `catalogueRun` stays in
// settings-panes.js: dashboard.js reads its return value at render time, and
// its `run` closure only names `revealFeature` when a row is clicked.

// --- landing on the feature a catalogue row names ----------------------------
//
// The owner, 2026-09-24: "I clicked on the "suggested links" option in the
// tools and features panel and all it did was take me to the graph page, it
// didnt actually open the menu option for suggested links in the graph like it
// should have." Measured: of the 110 written rows in Tools and features, 50
// switched tab (or opened the Library sub-tab, or a Settings pane) and stopped
// there while naming one control on it, and the palette's two board rows did
// nothing at all unless a board was already open. Each row was a hand-written
// closure, and `switchTab("graph")` is the shortest closure that looks like it
// works.
//
// So a row declares where it goes instead (`tests/test_catalogue_reveal.py`
// has the three forms), and every row that names something smaller than a
// tab names one entry here. `revealFeature` does the same five things for
// each: the tab, the lazy bundle, the menu or panel or dialog the control is
// in, a wait until the control is really on screen, and the app's own
// jump-to highlight on it (`flashRevealed`, the ring `flashEntry` and a
// Settings deep link already wear), so the eye lands where the row said.
//
// A target is `{ tab?, settings?, module?, open?, el | sel+built, text?,
// focus?, flash?, fallback? }`: `el` is an id in index.html, `sel` a selector
// for something built at runtime by the function `built` names (with `{arg}`
// filled in from the row), `text` picks a menu row by its words, and
// `fallback` is what is ringed instead when the feature needs something the
// notebook does not have yet (a board to find a card on, a document to set a
// word goal for): the control that makes one, rather than a row that does
// nothing.

//: Resolves to the element once it is on screen (a layout box, not hidden),
//: or null when it has not arrived in `ms`. Polled rather than observed: the
//: things waited for arrive by a tab's module loading, a fetch, a render on
//: the next frame or a dialog's own animation, and a poll is one answer to
//: all four.
function revealWait(find, ms = 3000) {
  const started = performance.now();
  return new Promise((resolve) => {
    const tick = () => {
      let el = null;
      try {
        el = find();
      } catch {
        el = null;
      }
      if (el && el.getClientRects().length) return resolve(el);
      if (performance.now() - started > ms) return resolve(null);
      setTimeout(tick, 60);
    };
    tick();
  });
}

//: A `<details>` dock menu, opened. Setting `open` is what a press on its
//: summary does, without the press's chance of closing one already open.
function revealDetails(id) {
  const menu = $(id);
  if (menu && menu.tagName === "DETAILS") menu.open = true;
}

//: The first visible element matching `sel`, or the first whose text
//: carries `text` when a menu row is picked by its words.
function revealQuery(sel, text) {
  const all = [...document.querySelectorAll(sel)].filter((el) => el.getClientRects().length);
  if (!text) return all[0] || null;
  const want = text.toLowerCase();
  return all.find((el) => (el.textContent || "").toLowerCase().includes(want)) || null;
}

//: A row's ⋯ menu in the note list, opened, for the features that live in it
//: (a thread, making a note private, its similar notes). The first note is as
//: good as any: the row is about the menu, not about a note.
async function revealEntryMenu() {
  await switchTab("notes");
  showNotesSection("browse");
  //: Pressed until its menu shows, three times at most: the list is fetched
  //: and drawn again as the tab arrives, and a menu opened on the first
  //: drawing goes with the row it belonged to (measured: the first press
  //: alone left no menu on screen).
  //: And the list is let settle first: a press on a row the next drawing
  //: replaces opens a menu that goes with it, a moment after it showed.
  let rows = -1;
  for (let settle = 0; settle < 12; settle += 1) {
    await new Promise((resolve) => setTimeout(resolve, 120));
    const now = document.querySelectorAll("#entry-list li").length;
    if (now && now === rows) break;
    rows = now;
  }
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const opener = await revealWait(() => document.querySelector("#entry-list li .menu-wrap > button"));
    if (!opener) return;
    opener.click();
    if (await revealWait(() => revealQuery('[role="menuitem"]'), 700)) break;
  }
}

//: A row that sits in one of an open menu's groups ("Connect ›", "Add ›")
//: is in the page and not on screen until its group is opened, so the group
//: that holds it is pressed.
function revealSubmenuFor(text) {
  const want = text.toLowerCase();
  for (const group of document.querySelectorAll(".action-menu:not(.hidden) .menu-group")) {
    const holds = [...group.querySelectorAll('[role="menuitem"]')].some(
      (item) => !item.classList.contains("has-submenu") && (item.textContent || "").toLowerCase().includes(want)
    );
    if (holds) {
      group.querySelector(".has-submenu")?.click();
      return;
    }
  }
}

//: The formatting strip, shown. The note editor's and the document editor's
//: strips start folded to one row (`docToolbarCollapsed`, documents.js), so
//: a tool that lives in the strip (Insert, the checklist, Find, Focus) is on
//: the page and not on screen until the strip is opened, which is what a
//: person would do to reach it; the choice is remembered, as theirs is.
async function revealStrip() {
  await ensureModule("library");
  if (typeof docToolbarCollapsed === "function" && docToolbarCollapsed()) setDocToolbarCollapsed(false);
}

//: The graph's gear panel, open. Below 600 it is the one sheet the phone
//: layout gives the map's controls (`openGraphControlsSheet`); above, the
//: floating panel. Either way the same `#graph-options` is what shows.
function revealGraphOptions() {
  if (window.matchMedia(PHONE_TABS).matches) {
    if (!graphSheetClose) openGraphControlsSheet($("graph-options-toggle"));
    return;
  }
  setGraphOptionsOpen(true);
}

//: A document open on the Documents tab. Its own load opens the newest when
//: none is (`loadDocuments`), so this is the tab plus a check.
async function revealDocument() {
  await switchTab("documents");
  await revealWait(() => (typeof currentDoc !== "undefined" && currentDoc ? $("doc-title") : null), 2500);
  return typeof currentDoc !== "undefined" && Boolean(currentDoc);
}

//: A board open on its canvas: the one already open, else the newest (a map
//: when `wantMap`, since growing a map by keyboard means nothing on a board).
//: No board at all leaves the boards gallery showing, where the target's
//: `fallback` is the button that makes one.
async function revealBoard(wantMap = false) {
  await switchTab("library");
  document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click();
  await ensureModule("library");
  const onCanvas = !$("wb-canvas-view")?.classList.contains("hidden");
  const isMap = typeof wbIsMap === "function" && wbIsMap();
  if (window.currentBoardId && onCanvas && (!wantMap || isMap)) return true;
  const boards = await apiJson("/whiteboard/boards").catch(() => []);
  const pick = wantMap
    ? boards.find((board) => board.type === "map")
    : boards.find((board) => board.id === window.currentBoardId) || boards.find((board) => board.id != null);
  if (!pick) return false;
  await openWhiteboardBoard(pick.id);
  return true;
}

//: A dashboard widget, or its row in the widget picker when it is switched
//: off or the notebook is new enough that the dashboard shows its welcome
//: instead: the picker is where a hidden widget is turned on.
async function revealDashWidget(name) {
  await switchTab("dashboard");
  const card = await revealWait(() => document.querySelector(`#dash-grid [data-widget="${name}"]`), 1500);
  if (card) return;
  $("dash-widgets-open")?.click();
}

const REVEAL_TARGETS = {
  // Capture & notes
  "notes-capture": { tab: "notes", open: () => showNotesSection("capture"), el: "entry-content", focus: true },
  "notes-template": { tab: "notes", open: () => showNotesSection("capture"), el: "entry-template" },
  "notes-improve": { tab: "notes", open: () => showNotesSection("capture"), el: "improve-btn" },
  "notes-dictation": { tab: "notes", open: () => showNotesSection("capture"), el: "mic-note" },
  "notes-attach": { tab: "notes", open: () => showNotesSection("capture"), el: "entry-attach-file" },
  "notes-checklist": {
    tab: "notes",
    open: async () => {
      showNotesSection("capture");
      await revealStrip();
    },
    sel: '#note-toolbar [data-md="task"]',
    built: "showNotesSection",
    fallback: "note-toolbar",
  },
  "writing-room": { tab: "notes", open: () => showNotesSection("writing-room"), el: "draft-thoughts", focus: true },
  "notes-ask": { tab: "notes", open: () => showNotesSection("ask"), el: "question", focus: true },
  //: UX-08: the bin is the Library with its own "Include the bin" ticked.
  "notes-questions": { tab: "notes", open: () => showNotesSection("questions"), el: "questions", flash: false },
  "library-bin": {
    tab: "library",
    open: () => {
      const box = $("library-show-binned");
      if (box && !box.checked) {
        box.checked = true;
        box.dispatchEvent(new Event("change", { bubbles: true }));
      }
    },
    el: "library-filter-menu",
  },
  "notes-thread": {
    open: async () => {
      await revealEntryMenu();
      revealSubmenuFor("Continue thought");
    },
    sel: '[role="menuitem"]',
    text: "Continue thought",
    built: "kebabMenu",
    fallback: "entry-list",
  },
  "notes-private": { open: revealEntryMenu, sel: '[role="menuitem"]', text: "Make private", built: "kebabMenu", fallback: "entry-list" },
  "notes-related": {
    open: async () => {
      await revealEntryMenu();
      revealSubmenuFor("Similar notes");
    },
    sel: '[role="menuitem"]',
    text: "Similar notes",
    built: "kebabMenu",
    fallback: "entry-list",
  },
  "notes-favourite": {
    tab: "notes",
    open: () => showNotesSection("browse"),
    sel: "#entry-list .favourite-btn",
    built: "renderEntries",
    fallback: "entry-list",
  },
  "notes-forgotten": {
    tab: "notes",
    open: () => {
      showNotesSection("browse");
      const sort = $("note-sort");
      if (sort.value !== "forgotten") {
        sort.value = "forgotten";
        sort.dispatchEvent(new Event("change"));
      }
    },
    el: "note-sort",
  },
  "notes-filter-help": {
    tab: "notes",
    open: () => {
      showNotesSection("browse");
      //: The '?' is the `data-help-for` recipe now, so opening it is pressing
      //: it; only when it is not already open, since a press toggles.
      if ($("search-help").getAttribute("aria-expanded") !== "true") $("search-help").click();
    },
    el: "search-help-hint",
  },
  "recycle-bin": {
    tab: "library",
    module: "library",
    open: () => {
      document.querySelector('#library-subtabs button[data-target="library-view-documents"]')?.click();
      libraryKind = "archived";
      const binned = $("library-show-binned");
      if (binned && !binned.checked) {
        binned.checked = true;
        binned.dispatchEvent(new Event("change"));
      }
      renderLibraryFilters();
      renderLibrary();
    },
    sel: '#library-filters [data-kind="archived"]',
    built: "renderLibraryFilters",
  },
  sketch: { open: () => openSketch(), el: "sketch-card", flash: false },
  meeting: { open: () => openMeetingRecorder(), el: "meeting-card", flash: false },
  "voice-note": { open: () => ensureModule("meetings").then(() => openVoiceNote()), el: "meeting-card", flash: false },
  recordings: { tab: "library", open: () => ensureModule("meetings").then(() => openRecordings()), el: "library-view-recordings", flash: false },
  //: Ctrl+D's own door (`openTodaysPage`, timeline.js): today's page where it
  //: lives, or the composer with the day's title. The composer's box is the
  //: element that is always there to land on.
  "todays-note": { open: () => openTodaysPage(), el: "entry-content", flash: false },
  "page-reader": { module: "library", open: () => window.openPageReader?.(), el: "ocr-workspace", flash: false, fallback: "library-view-media" },

  // Ask & chat
  "chat-input": { tab: "chat", el: "chat-input", focus: true, flash: false },
  "chat-answers": { tab: "chat", el: "chat-input", focus: true, flash: false },
  "finder": { open: () => openFinder(), el: "finder-input", focus: true, flash: false },
  "chat-new": { tab: "chat", open: () => newChatConversation(), el: "chat-input", focus: true, flash: false },
  "chat-attach": { tab: "chat", open: () => $("attach-note").click(), el: "note-picker-panel" },
  "chat-conversations": { tab: "chat", el: "conversation-list", fallback: "chat-sidebar" },
  "chat-agent-mode": { tab: "chat", sel: '#chat-mode-seg [data-chat-mode="agent"]', built: "switchTab" },
  //: Below the dock's width the toggle lives in the How it answers panel
  //: (a sheet on a phone), so that is opened when the toggle is not on screen.
  "chat-web-search": {
    tab: "chat",
    open: () => {
      if (!$("web-search-toggle")?.getClientRects().length && !chatDockMoreOpen()) openChatDockMore();
    },
    el: "web-search-toggle",
  },
  "chat-export": {
    tab: "chat",
    open: async () => {
      //: Export is about a saved chat: with none open, the newest is opened,
      //: and with none at all the box that starts one is ringed instead.
      if (!chatConv?.id) {
        const saved = await apiJson("/conversations").catch(() => []);
        const newest = (saved.items || saved || [])[0];
        if (newest) await openConversation(newest.id);
      }
      const opener = await revealWait(() => document.querySelector("#chat-actions-menu .menu-wrap > button"), 1500);
      opener?.click();
    },
    sel: '[role="menuitem"]',
    text: "Export as Markdown",
    built: "mountChatActionsMenu",
    fallback: "chat-input",
  },
  //: On a phone the agent is the Chat tab (`toggleAgentPalette` says why),
  //: so either surface is the landing.
  "agent-palette": {
    open: () => toggleAgentPalette(),
    sel: "#command-palette-overlay, #chat-input",
    built: "toggleAgentPalette",
    flash: false,
  },
  "atlas-help": { open: () => askAtlasAbout(""), sel: '[data-sheet="guide"]', built: "openHelpChat", flash: false },

  // Documents
  "doc-new": { tab: "documents", open: () => createDocument(), el: "doc-title", focus: true },
  "doc-templates": { tab: "documents", open: () => openDocTemplateDialog(), el: "doc-template-dialog", flash: false },
  "doc-insert": {
    open: async () => (await revealDocument()) && (await revealStrip(), revealDetails("doc-toolbar-insert")),
    el: "doc-toolbar-insert",
    fallback: "doc-new",
  },
  "doc-tables": {
    open: async () => (await revealDocument()) && (await revealStrip(), revealDetails("doc-toolbar-insert")),
    sel: '#doc-toolbar-insert [data-md="table"]',
    built: "revealDetails",
    fallback: "doc-new",
  },
  "doc-outline": {
    open: async () => {
      await switchTab("documents");
      showDocSidebarSection("outline");
    },
    el: "doc-outline-wrap",
    fallback: "doc-sidebar",
  },
  "doc-crumbs": { open: revealDocument, el: "doc-crumbs", fallback: "doc-title" },
  //: CodeMirror's own search panel where the engine is mounted, the plain
  //: bar where it is not (`toggleDocFindBar` picks).
  "doc-find": {
    open: async () => {
      if (!(await revealDocument())) return;
      //: Find and replace is an editing tool: a document open to read (a
      //: phone opens them that way) is switched to its editing view first.
      if (typeof docView !== "undefined" && docView === "rendered") setDocView(lastEditView);
      toggleDocFindBar(true);
    },
    sel: "#doc-find-bar, #doc-panes .cm-search",
    built: "toggleDocFindBar",
    fallback: "doc-new",
  },
  "doc-focus": { open: revealDocument, el: "doc-focus-toggle", fallback: "doc-new" },
  "doc-properties": { open: revealDocument, sel: "#doc-editor .doc-props", built: "renderDocProperties", fallback: "doc-title" },
  "doc-connections": { open: async () => (await revealDocument()) && $("doc-connections").click(), el: "connections-overlay", flash: false, fallback: "doc-new" },
  "doc-prose": { open: async () => (await revealDocument()) && $("doc-prose").click(), el: "doc-prose-panel", fallback: "doc-prose" },
  "doc-dictionary": { module: "library", open: () => openDocDictionary(), el: "doc-dictionary-dialog", flash: false },
  "doc-word-goal": { open: async () => (await revealDocument()) && $("doc-word-goal").click(), el: "doc-word-goal-dialog", flash: false, fallback: "doc-new" },
  "doc-history": { open: async () => (await revealDocument()) && $("doc-history").click(), el: "doc-history-dialog", flash: false, fallback: "doc-new" },
  "doc-ai": { open: async () => (await revealDocument()) && $("doc-ai").click(), el: "doc-ai-panel", fallback: "doc-ai" },
  //: The exports are a group inside the ⋯ menu (`foldDocMenuGroup`), so the
  //: group's own row is pressed to open it.
  "doc-export": {
    open: async () => {
      if (!(await revealDocument())) return;
      revealDetails("doc-dock-menu");
      $("doc-export-md")?.closest(".menu-group")?.querySelector(".has-submenu")?.click();
    },
    el: "doc-export-md",
    fallback: "doc-new",
  },

  // Boards and maps
  "board-new": {
    open: () => revealBoardsGallery(),
    el: "wb-boards-new-menu",
  },
  "board-create": { open: () => createNewBoard(), sel: ".prompt-card", built: "promptDialog", flash: false },
  "map-create": { open: async () => { await revealBoardsGallery(); await wbNewUntitledBoard("map"); }, el: "whiteboard-container", flash: false },
  "map-keyboard": { open: () => revealBoard(true), el: "whiteboard-container", fallback: "wb-boards-new-menu" },
  "map-templates": { open: () => revealBoard(true), el: "wb-map-templates", fallback: "wb-boards-new-menu" },
  //: On a map, where laying the tree out again is one button; on a board
  //: it is a right-click on a note with links, which no row can press.
  "board-arrange": {
    open: async () => {
      if (!(await revealBoard(true))) return;
      //: On a phone the rail is a sheet behind the Tools opener.
      if (!$("wb-map-tidy")?.getClientRects().length && $("wb-tools-opener")?.getClientRects().length) {
        $("wb-tools-opener").click();
      }
    },
    el: "wb-map-tidy",
    fallback: "wb-boards-new-menu",
  },
  //: Below 720 the overview steps aside for the tools (07-whiteboard-misc.css),
  //: so there the board itself is the landing.
  "board-overview": { open: async () => (await revealBoard()) && wbToggleNavigator(true), el: "wb-navigator", fallback: "whiteboard-container" },
  "board-find": { open: async () => (await revealBoard()) && wbOpenBoardSearch(), el: "wb-search-bar", fallback: "wb-boards-new-menu" },
  "board-tools": { open: () => revealBoard(), el: "wb-tools-panel", fallback: "wb-boards-new-menu" },
  "board-context": { open: () => revealBoard(), el: "wb-context", fallback: "wb-topbar" },
  "board-export": {
    open: async () => (await revealBoard()) && wbExportBoard(),
    sel: ".wb-export-card",
    built: "wbExportBoard",
    flash: false,
    fallback: "wb-boards-new-menu",
  },

  // Library
  "library-docs": { tab: "library", open: () => revealLibrarySub('[data-target="library-view-docs"]'), el: "library-view-docs", flash: false },
  "library-images": { tab: "library", open: () => revealLibrarySub('[data-media-kind="images"]'), el: "library-view-media", flash: false },
  "library-files": { tab: "library", open: () => revealLibrarySub('[data-media-kind="files"]'), el: "library-view-media", flash: false },
  "library-links": { tab: "library", open: () => revealLibrarySub('[data-target="library-view-links"]'), el: "library-view-links", flash: false },
  "library-skills": { tab: "library", open: () => revealLibrarySub('[data-target="library-view-skills"]'), el: "library-view-skills", flash: false },
  "library-contents": { tab: "library", open: () => revealLibrarySub('[data-target="library-view-contents"]'), el: "library-view-contents", flash: false },

  // Map and discovery
  "graph-edit": {
    tab: "graph",
    open: async () => {
      await ensureModule("graph");
      await revealWait(() => (typeof graphNodesRef !== "undefined" && graphNodesRef.length ? $("graph-box") : null), 2500);
      const node = typeof graphNodesRef !== "undefined" ? graphNodesRef[0] : null;
      if (node) openGraphPopup({ ...graphNodeScreenPoint(node), stopPropagation() {} }, node);
    },
    el: "graph-popup",
    flash: false,
    fallback: "graph-add-node",
  },
  "graph-physics": { tab: "graph", open: revealGraphOptions, el: "graph-physics" },
  //: KG4: note types and their fields.
  "note-types": { open: () => openNoteTypesSheet(), sel: '[data-sheet="note-types"] .sheet-card', built: "openNoteTypesSheet", flash: false },
  //: New meeting (INBOX 644): its sheet, the title field first.
  "meeting-new": { open: () => openNewMeeting(), sel: '[data-sheet="new-meeting"] .sheet-card', built: "openNewMeeting", flash: false },
  //: KG3: the kinds of link, the built-ins and a person's own.
  "relation-types": { open: () => openRelationTypesSheet(), sel: '[data-sheet="relation-types"] .sheet-card', built: "openRelationTypesSheet", flash: false },
  //: KG5: every person, place and thing named in the notes.
  entities: { open: () => openEntitiesSheet(), sel: '[data-sheet="entities"] .sheet-card', built: "openEntitiesSheet", flash: false },
  //: The suggestions inbox (KG9): one sheet, opened at the kind asked for.
  suggestions: { open: () => openSuggestionsInbox("links"), sel: '[data-sheet="suggestions"] .sheet-card', built: "openSuggestionsInbox", flash: false },
  "graph-suggest": { open: () => openSuggestionsInbox("links"), sel: "#inbox-kind", built: "openSuggestionsInbox", flash: false, fallback: "link-suggest-btn" },
  "timeline-zoom": { tab: "timeline", open: () => revealDetails("timeline-options-menu"), el: "timeline-scale-group" },
  "timeline-bands": { tab: "timeline", open: () => revealDetails("timeline-options-menu"), el: "timeline-band-section" },
  "global-find": { open: () => openGlobalFind(), el: "global-find-bar", flash: false, fallback: "wb-search-bar" },
  tensions: { open: () => openSuggestionsInbox("tensions"), sel: "#inbox-kind", built: "openSuggestionsInbox", flash: false },
  //: Tidy (INBOX 691): its sheet, or opened at one review; the tag manager
  //: and the filings to check, each named in Tools and features at last.
  tidy: { tab: "notes", open: () => openTidySheet(), sel: '[data-sheet="tidy"] .sheet-card', built: "openTidySheet", flash: false },
  "tidy-links": { tab: "notes", open: () => openTidySheet("link-reasons"), sel: "#tidy-review", built: "openTidySheet", flash: false },
  "tidy-duplicates": { tab: "notes", open: () => openTidySheet("duplicates"), sel: "#tidy-review", built: "openTidySheet", flash: false },
  "tag-manager": { open: () => openTagsSheet(), sel: '[data-sheet="tags"] .sheet-card', built: "openTagsSheet", flash: false },
  "notes-order": { tab: "notes", el: "entry-list" },
  "notes-review": { tab: "notes", open: () => showNotesFilter("is:review"), el: "note-search" },

  // Plan and focus: the dashboard's widgets
  "widget-on-this-day": { open: () => revealDashWidget("on-this-day"), sel: '[data-widget="on-this-day"]', built: "renderDashboard" },
  "widget-focus": { open: () => revealDashWidget("focus"), sel: '[data-widget="focus"]', built: "renderDashboard" },
  "widget-digest": { open: () => revealDashWidget("digest"), sel: '[data-widget="digest"]', built: "renderDashboard" },
  "widget-rediscover": { open: () => revealDashWidget("random"), sel: '[data-widget="random"]', built: "renderDashboard" },
  "widget-orphans": { open: () => revealDashWidget("orphans"), sel: '[data-widget="orphans"]', built: "renderDashboard" },
  "widget-unfinished": { open: () => revealDashWidget("unfinished"), sel: '[data-widget="unfinished"]', built: "renderDashboard" },
  "widget-pace": { open: () => revealDashWidget("pace"), sel: '[data-widget="pace"]', built: "renderDashboard" },
  "widget-week": { open: () => revealDashWidget("week"), sel: '[data-widget="week"]', built: "renderDashboard" },
  statistics: { open: () => openStatistics(), sel: ".stats-card", built: "openStatistics", flash: false },
  "widget-heatmap": { open: () => revealDashWidget("heatmap"), sel: '[data-widget="heatmap"]', built: "renderDashboard" },
  "widget-streak": { open: () => revealDashWidget("streak"), sel: '[data-widget="streak"]', built: "renderDashboard" },
  "dash-layout": {
    tab: "dashboard",
    open: () => {
      if (!dashEditMode) $("dash-edit").click();
    },
    el: "dash-edit",
  },
  //: Below 1100 the form is a sheet opened by New reminder
  //: (`openReminderCompose`); above, it is on the page.
  "reminder-magic": { tab: "reminders", open: () => openReminderCompose(), el: "reminder-magic", focus: true },

  // Make it yours: Settings rows, each ringed in its pane
  "set-theme": { settings: "appearance", el: "theme-seg" },
  "set-accent": { settings: "appearance", el: "accent-swatches" },
  "set-typography": { settings: "appearance", el: "fontsize-seg" },
  "set-radius": { settings: "appearance", el: "radius-slider" },
  "set-background": { settings: "appearance", el: "bg-art-toggle" },
  "set-companion": { settings: "appearance", el: "avatar-buddy-row" },
  "set-contrast": { settings: "appearance", el: "contrast-toggle" },
  "set-custom-css": { settings: "appearance", el: "custom-css" },
  "set-search-relevance": { settings: "searchindex", el: "search-relevance-group" },
  "set-export": { settings: "data", el: "export-json" },
  "set-import-md": { settings: "data", el: "import-md" },
  "set-backups": { settings: "data", el: "backup-now" },
  "set-updates": { settings: "about", el: "update-check-now", fallback: "settings-about" },
  //: One row per tool the agent can call, built from the backend's own list
  //: when the features browser opens (`renderFeatures`): the tool's own row
  //: in Settings, Tools it can use, where it is switched on or off.
  "ai-tool": { settings: "tools", sel: '#tool-list [data-tool="{arg}"]', built: "renderToolSettings", fallback: "settings-tools" },
  // One package's row in Settings, Packages (`extra-row-<id>`, settings-packages.js):
  // the OCR workspace's "RapidOCR, not installed" Install (INBOX 717).
  "extra-row": { settings: "extras", sel: "#extra-row-{arg}", built: "renderExtras", fallback: "settings-extras" },
  "workspace-new": { open: () => openSpaceCreate(), el: "space-create-dialog", flash: false },

  // Data and control
  palette: { open: () => openPalette(), el: "palette-overlay", flash: false },
  features: { open: () => openFeatures(), el: "features-card", flash: false },
  shortcuts: { open: () => openShortcuts(), el: "shortcuts-card", flash: false },
  onboarding: { open: () => openOnboarding(), el: "onboarding-card", flash: false },
  //: The manual (manual.js, lazy): Find anything, the palette and a quick-access tile open it, not Settings, Help.
  manual: { open: () => lazyScript("/js/manual.js").then((ok) => ok && openManual()), sel: ".manual-overlay", built: "openManual", flash: false },
};

//: The Library's gallery of boards, not a board on its canvas.
function revealBoardsGallery() {
  return switchTab("library").then(() => {
    document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click();
    return ensureModule("library").then(() => wbShowBoardsLanding());
  });
}

//: One of the Library's sub-tabs, pressed the way a person presses it, so its
//: own handler decides what loads.
function revealLibrarySub(selector) {
  document.querySelector(`#library-subtabs button${selector}`)?.click();
}

async function revealFeature(key, arg = "") {
  let target = REVEAL_TARGETS[key];
  //: `settings:<section>` is a row that names a whole pane ("Settings →
  //: Models"): the pane is the feature, so it is shown and not ringed.
  if (!target && key.startsWith("settings:")) {
    const section = key.slice("settings:".length);
    target = { settings: section, el: `settings-${section}`, flash: false };
  }
  if (!target) return false;
  const fill = (text) => (text || "").replace("{arg}", String(arg).replace(/["\\]/g, ""));
  try {
    if (target.settings) await openSettingsModal(target.settings);
    if (target.tab) await switchTab(target.tab);
    if (target.module) await ensureModule(target.module);
    //: Raced, not awaited outright: some openers resolve only when a person
    //: answers the dialog they open (`createNewBoard` asks for a name), and
    //: what is waited for below is the dialog, which is there long before.
    if (target.open) await Promise.race([Promise.resolve(target.open(arg)), new Promise((r) => setTimeout(r, 1500))]);
  } catch (error) {
    console.warn("revealFeature", key, error);
  }
  const find = () => (target.el ? $(target.el) : revealQuery(fill(target.sel), target.text));
  const land = (el) => {
    if (target.flash !== false) flashRevealed(el);
    if (target.focus) el.focus({ preventScroll: true });
  };
  const found = await revealWait(find);
  if (!found) {
    const fallback = target.fallback ? await revealWait(() => $(target.fallback), 800) : null;
    if (fallback) flashRevealed(fallback);
    return false;
  }
  land(found);
  //: **A list drawn twice as it arrives takes the ring with it.** Settings →
  //: Tools it can use renders its rows on open and again when its own fetch
  //: lands, so the row ringed first was gone a moment later (measured: every
  //: AI tool row "visible but not ringed"). So a found element that has left
  //: the page is found again and ringed again.
  //: Checked twice, since a slow fetch can land after the first look.
  let current = found;
  for (const pause of [350, 550]) {
    await new Promise((resolve) => setTimeout(resolve, pause));
    if (current.isConnected) continue;
    let again = await revealWait(find, 1000);
    //: A menu goes with the row it was opened on, so a menu row that left
    //: is opened again rather than looked for.
    if (!again && target.open) {
      try {
        await Promise.race([Promise.resolve(target.open(arg)), new Promise((r) => setTimeout(r, 1500))]);
      } catch (error) {
        console.warn("revealFeature", key, error);
      }
      again = await revealWait(find, 1500);
    }
    if (!again) break;
    land(again);
    current = again;
  }
  return true;
}


// --- a source's quoted line, marked in its note (CHAT_PLAN 8 row 7) ----------
//
// `openNoteAtPassage` (capture-ask.js) flashes the note's card; this marks the
// span the answer quoted inside it with the Custom Highlight API, so the
// card's own markup, which the list redraws at will, is never rewritten.

//: The passage, from a string or from the clicked card: its answer's first
//: mark for this note carries the offsets into the note's text.
function notePassageFor(id, from) {
  if (typeof from === "string") return from;
  const scope = from?.closest?.(".msg") || from?.closest?.("#tab-notes, #command-palette-results");
  const marker = scope?.querySelector(`.answer-citation[data-note-id="${id}"][data-start]`);
  const entry = allEntries.find((e) => e.id === id);
  if (!marker || !entry) return "";
  return plainText(String(entry.content || "").slice(Number(marker.dataset.start), Number(marker.dataset.end)));
}

//: Every character of `root`'s text with whitespace runs folded to one
//: space, each mapped back to its node and offset, so a passage taken from
//: the markdown finds itself in the rendered card.
function foldedText(root) {
  const map = [];
  let text = "";
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    for (let i = 0; i < node.data.length; i += 1) {
      const ch = /\s/.test(node.data[i]) ? " " : node.data[i].toLowerCase();
      if (ch === " " && text.endsWith(" ")) continue;
      text += ch;
      map.push([node, i]);
    }
  }
  return { text, map };
}

function passageRange(root, passage) {
  const want = passage.replace(/\s+/g, " ").trim().toLowerCase().slice(0, 160);
  if (want.length < 3) return null;
  const { text, map } = foldedText(root);
  const at = text.indexOf(want);
  if (at === -1) return null;
  const range = document.createRange();
  const [startNode, startOffset] = map[at];
  const [endNode, endOffset] = map[at + want.length - 1];
  range.setStart(startNode, startOffset);
  range.setEnd(endNode, endOffset + 1);
  return range;
}

async function markNotePassage(id, from) {
  const passage = notePassageFor(id, from);
  if (!passage || !window.Highlight) return false;
  const body = await revealWait(() => document.querySelector(`#entry-list li[data-id="${id}"] .entry-content`), 2000);
  const range = body && passageRange(body, passage);
  if (!range) return false;
  CSS.highlights.set("source-quote", new window.Highlight(range));
  clearTimeout(markNotePassage.timer);
  markNotePassage.timer = setTimeout(() => CSS.highlights.delete("source-quote"), 8000);
  return true;
}

//: Which package row a notice is about, from the package's name as the
//: server's words give it ("Voice notes", "Translate offline", ...).
function packagesNoticeTarget(message) {
  if (/Read scanned PDFs|PDF pages/.test(message)) return "pdfpages";
  if (/Voice notes/.test(message)) return "voice";
  if (/Search by meaning/.test(message)) return "semantic";
  if (/Import documents/.test(message)) return "documents";
  if (/RapidOCR/.test(message)) return "rapidocr";
  if (/Search inside images|Tesseract/.test(message)) return "ocr";
  if (/Python|Pyodide/.test(message)) return "pyodide";
  if (/Translate/.test(message)) return "translate";
  if (/Live captions/.test(message)) return "captions";
  return "";
}

function packagesNoticeOpen(message) {
  const id = packagesNoticeTarget(message);
  return id ? revealFeature("extra-row", id) : revealFeature("settings:extras");
}

//: Moved here from settings-wiring.js and spaces-find.js (the boot gzip budget): the
//: shortcut sheet and the New space dialog open only by a click or a chord, through
//: stand-ins (lazy-entries.js) and the rows above.
function renderShortcutList() {
  for (const listId of SHORTCUT_LIST_IDS) {
    const list = $(listId);
    if (list) buildShortcutList(list);
  }
}

//: **The key chip is the button** (INBOX 810, Row actions): a column of
//: thirty-one bordered "Change" buttons was the heaviest thing in the pane,
//: louder than the keys it changes. Pressing the keys starts the rebind and
//: pressing them again cancels it; its title says which ("Change" or
//: "Cancel"), and the back-to-default is a quiet icon after the words.
function buildShortcutList(list) {
  list.replaceChildren();
  for (const [id, def] of Object.entries(shortcuts)) {
    const li = document.createElement("li");
    const capturing = capturingShortcut === id;
    const change = document.createElement("button");
    change.className = "ghost small quiet shortcut-key";
    change.type = "button";
    const combo = document.createElement("kbd");
    combo.textContent = capturing ? "Press keys…" : def.keys;
    if (capturing) combo.classList.add("capturing");
    //: A pencil says the keys are the way to change them (INBOX 1300 C22).
    const pen = document.createElement("i");
    pen.className = `ph ${capturing ? "ph-x" : "ph-pencil-simple"} shortcut-edit`;
    pen.setAttribute("aria-hidden", "true");
    change.append(combo, pen);
    change.title = capturing ? "Cancel" : "Change";
    change.setAttribute(
      "aria-label",
      capturing ? `Cancel changing the shortcut for: ${def.label}` : `Change the shortcut for: ${def.label}, now ${def.keys}`
    );
    change.addEventListener("click", () => {
      capturingShortcut = capturingShortcut === id ? null : id;
      setShortcutStatus(
        capturingShortcut ? "Press the keys you want, or Escape to cancel." : ""
      );
      renderShortcutList();
      //: The list was redrawn: the focus goes back to the same row's keys.
      list.querySelector(`[data-shortcut="${id}"] .shortcut-key`)?.focus();
    });

    const label = document.createElement("span");
    label.textContent = def.label;
    li.dataset.shortcut = id;
    li.append(change, label);

    // Only offer "default" when it isn't already the default.
    const changed = def.keys !== DEFAULT_SHORTCUTS[id].keys;
    if (changed) {
      const revert = document.createElement("button");
      revert.className = "ghost small quiet icon-only";
      revert.type = "button";
      setLabel(revert, "ph:arrow-counter-clockwise");
      revert.title = `Back to ${DEFAULT_SHORTCUTS[id].keys}`;
      revert.setAttribute("aria-label", revert.title);
      revert.addEventListener("click", () => {
        shortcuts[id].keys = DEFAULT_SHORTCUTS[id].keys;
        saveShortcutOverrides();
        renderShortcutList();
      });
      li.appendChild(revert);
    }
    list.appendChild(li);
  }
  //: Thirty-one rows: typed to (row 1643, `listFilter`).
  listFilter(list, { label: "Filter shortcuts" })?.refresh();
}

function openShortcuts() {
  capturingShortcut = null;
  setShortcutStatus("");
  renderShortcutList();
  //: **The editor's rows come from the editor's own table**
  //: (DOCUMENTS_PLAN Phase 4 item 4: "a `?` shortcut sheet generated from the
  //: same table so the two cannot disagree"). documents.js is lazily loaded,
  //: so the section says where its contents are rather than sitting empty
  //: when this dialog is opened before that bundle has ever been fetched.
  ensureModule("appPalette").then(() => renderToolShortcutList($("shortcut-list-tools")));
  const editorList = $("shortcut-list-documents");
  const editorNote = $("shortcut-list-documents-note");
  if (editorList && typeof renderDocShortcutSheet === "function") {
    renderDocShortcutSheet(editorList);
    editorNote?.classList.add("hidden");
  } else if (editorNote) {
    editorNote.classList.remove("hidden");
  }
  //: The board's rows, from the board's own table (whiteboard-commands.js),
  //: and the section scrolled into view when "?" was pressed on a board.
  const boardList = $("shortcut-list-whiteboard");
  const boardNote = $("shortcut-list-whiteboard-note");
  const onBoard = typeof wbCommandsLive === "function" && wbCommandsLive();
  if (boardList && typeof renderWbShortcutSheet === "function") {
    renderWbShortcutSheet(boardList);
    boardNote?.classList.add("hidden");
  } else if (boardNote) {
    boardNote.classList.remove("hidden");
  }
  $("shortcuts-overlay").classList.remove("hidden");
  if (onBoard) $("shortcut-head-whiteboard")?.scrollIntoView({ block: "start" });
  $("shortcuts-close").focus();
}
