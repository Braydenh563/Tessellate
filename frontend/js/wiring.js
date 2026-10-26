// wiring.js: offline badge, writing room and help wiring, pickers, the find
// bar, the graph's phone sheet, [[, duplicates. Moved out of app.js on
// 2026-09-26 as one contiguous range (INBOX 426 cc,
// docs/roadmap/agent-remaining/appjs-split.md). A classic script sharing
// app.js's globals, loaded in app.js's old order; nothing in an earlier file
// calls into it while the page loads (scratchpad/appjs-map.js --check).

// --- offline badge -----------------------------------------------------------
//
// Being offline is not an error here, the app is built to run that way. What
// the badge says is narrower: web search and any cloud model will not answer
// right now. `navigator.onLine` is the browser's own answer and is only ever
// a hint (it reports "online" for a machine on a LAN with no route out), but
// a false negative is impossible and a false positive costs nothing, which is
// the right way round for a passive indicator.
function reflectOnlineState() {
  $("offline-indicator")?.classList.toggle("hidden", navigator.onLine);
}
window.addEventListener("offline", reflectOnlineState);
window.addEventListener("online", reflectOnlineState);
reflectOnlineState();

// --- writing room wiring ---
$("draft-compose").addEventListener("click", composeDraft);
$("draft-undo").addEventListener("click", undoDraft);
$("draft-cancel").addEventListener("click", cancelDraft);
$("draft-save").addEventListener("click", () => saveDraftAsNote());

$("draft-title").addEventListener("click", suggestDraftTitle);
// Refine is Draft with an instruction in hand: the same pass, so it runs the
// same function rather than a second copy of it that could drift.
$("draft-refine").addEventListener("click", () => {
  if (!$("draft-instruction").value.trim()) {
    setDraftStatus("Say what to change, then refine.", true);
    $("draft-instruction").focus();
    return;
  }
  composeDraft();
});
$("draft-instruction").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  $("draft-refine").click();
});
$("draft-copy").addEventListener("click", async (event) => {
  const text = $("draft-text").value.trim();
  if (!text) {
    setDraftStatus("There's no draft to copy yet.", true);
    return;
  }
  if (await copyToClipboard(text, event.currentTarget)) setDraftStatus("Draft copied.");
});
// `appendSelectionToNote` is the app's one "add this text to a note you
// already have" path (the text-selection popup uses it): the same picker, the
// same undo entry, the same flash on the note it landed in.
$("draft-insert").addEventListener("click", () => {
  const text = $("draft-text").value.trim();
  if (!text) {
    setDraftStatus("There's no draft to insert yet.", true);
    return;
  }
  // The toast says it landed and offers the trip to it; the status line is
  // not written here because this returns before the picker has been
  // answered, and a line saying it was added is a lie until it was.
  appendSelectionToNote(text, { jump: false });
});
$("draft-add-source").addEventListener("click", async () => {
  if (draftSources.length >= DRAFT_MAX_SOURCES) {
    setDraftStatus(`Six notes is the most one draft can be written from.`, true);
    return;
  }
  const entry = await pickEntryDialog("Which note should Atlas write from?");
  if (!entry) return;
  if (draftSources.some((s) => s.id === entry.id)) return;
  draftSources.push({
    id: entry.id,
    label: clipText(entry.title || notePreviewText(entry.content) || "Untitled note", 60),
  });
  renderDraftSources();
  saveDraftLocally();
});
$("draft-continue-note").addEventListener("click", async () => {
  const entry = await pickEntryDialog("Which note should Atlas carry on?");
  if (!entry) return;
  if ($("draft-text").value.trim()) pushDraftUndo();
  $("draft-text").value = entry.content || "";
  draftNoteId = entry.id;
  draftNoteLabel = clipText(entry.title || notePreviewText(entry.content) || "a note", 40);
  $("draft-kind").value = "continue";
  markDraftQuickstart("continue");
  renderDraftTarget();
  // The note as it stands is version one, so the way back to what it said
  // before Atlas touched it is the same chip row as every other pass.
  rememberDraftVersion($("draft-text").value);
  updateDraftCount();
  saveDraftLocally();
  setDraftStatus("That note is in the draft. Add a thought, then draft to carry it on.");
  $("draft-thoughts").focus();
});
for (const id of ["draft-kind", "draft-tone", "draft-length"]) {
  $(id).addEventListener("change", () => {
    if (id === "draft-kind") {
      const kind = $("draft-kind").value;
      markDraftQuickstart(kind);
      //: The Translate chip goes back to the last language picked here.
      if (kind.startsWith("translate-")) {
        try {
          prefs.set("draft-translate", kind.slice("translate-".length));
        } catch {
          /* storage blocked: the chip keeps its default */
        }
      }
    }
    saveDraftLocally();
  });
}
renderDraftQuickstarts();
$("draft-extract").addEventListener("click", () => openExtractPreview($("draft-text").value));
$("extract-close").addEventListener("click", closeExtractPreview);
$("extract-cancel").addEventListener("click", closeExtractPreview);
$("extract-commit").addEventListener("click", commitExtractPreview);
$("draft-text").addEventListener("input", () => {
  updateDraftCount();
  saveDraftLocally();
});
//: One listener: the thoughts box keeps its draft and its word count (INBOX 63).
$("draft-thoughts").addEventListener("input", () => {
  saveDraftLocally();
  updateDraftCount();
});
$("draft-tags").addEventListener("input", saveDraftLocally);
// Ctrl/Cmd+Enter from the thoughts box drafts, matching the capture box.
$("draft-thoughts").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    composeDraft();
  }
});
$("draft-discard").addEventListener("click", async () => {
  if (!$("draft-text").value.trim() && !$("draft-thoughts").value.trim()) return;
  if (!(await confirmDialog("Discard this draft? It hasn't been saved as a note."))) return;
  foldedThoughts = "";
  $("draft-thoughts").value = "";
  $("draft-text").value = "";
  $("draft-tags").value = "";
  $("draft-thinking").classList.add("hidden");
  // The earlier versions and the notes it was being written from go with it:
  // a desk that is cleared and still lists six sources and four old drafts
  // has not been cleared.
  draftSources = [];
  draftVersions = [];
  renderDraftSources();
  renderDraftVersions();
  clearDraftTarget();
  setDraftStatus("");
  updateDraftCount();
  saveDraftLocally();
});
// --- one wiring for every "?" ----------------------------------------------
// Every "?" is this wiring (tests/test_ui_recipes.py fails if a hand-wired
// one comes back), so a new one is markup only:
//   <button type="button" class="icon-only ghost small graph-help-toggle"
//           data-help-for="thing-help" aria-controls="thing-help"
//           aria-expanded="false" title="…" aria-label="…">
//     <i class="ph ph-question" aria-hidden="true"></i></button>
//   <div class="help-body hidden" id="thing-help" role="dialog" aria-label="…">…</div>
// A `<button>` gives focus, Enter and Space for free; `wireHelpPopover` owns
// Escape, outside click and a second click, and its own guard makes a second
// pass over a wired pair do nothing (Settings renders some sections lazily).
//: **Every question the app offers to ask Atlas, in one table** (INBOX 224,
//: the owner: "also make atlas more accessible and have suggestions to ask it
//: something here and there like in tooltips or the help page in settings
//: etc."). Keyed by the id of the `data-help-for` panel it belongs under, so a
//: '?' popover and the question it suggests cannot describe two different
//: controls: they are looked up by the same key.
//:
//: Not all forty-nine popovers: a suggestion under a popover that already
//: answers the question is noise, and a table of forty-nine questions would be
//: forty-nine pieces of copy nobody re-reads. These are the panels whose
//: subject has more to it than the panel can hold.
const ATLAS_PROMPTS = {
  "command-palette-help": "What can the popup agent do that Chat cannot?",
  "help-chat-help": "What can you help me with?",
  "graph-show-help": "What do entity and board nodes add to the graph?",
  "autonomous-ai-help": "What can Atlas change in my notebook on its own?",
  "websearch-help": "How do I turn off web search?",
  "battery-mode-help": "What does Performance mode do?",
  "memory-help": "What does the app remember about me?",
  "backups-help": "Where are my backups kept, and how do I restore one?",
  "utility-model-help": "What is the utility model used for?",
  "templates-help": "How do I make a template of my own?",
  "statusbar-help": "What is the status bar telling me?",
};

//: The one door, so every suggestion in the app opens the same sheet with the
//: same question. settings.js owns the chat, and it loads after this file, so
//: this is checked rather than assumed: before settings.js has run there is no
//: sheet to open, and a suggestion pressed in that window should do nothing
//: rather than throw.
function askAtlasAbout(question) {
  if (typeof openHelpChat !== "function" || typeof askAtlas !== "function") return;
  openHelpChat();
  askAtlas(question);
}

//: The line at the foot of a help popover: the popover says what the control
//: does, and this offers the question it cannot answer in a paragraph. Added
//: here rather than written into forty-nine blocks of markup, and guarded by a
//: flag because `initHelpToggles` is re-runnable (Settings builds some of its
//: sections lazily).
function addAtlasLine(panel) {
  const question = ATLAS_PROMPTS[panel.id];
  if (!question || panel.dataset.atlasLine) return;
  panel.dataset.atlasLine = "1";
  // The one builder, so the offer looks the same in a popover as in an
  // empty state (`atlasSuggestion`).
  panel.appendChild(atlasSuggestion(question));
}

function initHelpToggles(root = document) {
  for (const trigger of root.querySelectorAll("[data-help-for]")) {
    const panel = document.getElementById(trigger.dataset.helpFor);
    if (!panel) continue;
    wireHelpPopover(trigger, panel);
    addAtlasLine(panel);
  }
}
window.initHelpToggles = initHelpToggles;
initHelpToggles();

//: The two empty states that are markup rather than script (the Chat tab's is
//: built in `renderChatEmptyState`). Appended once, here, so all three read
//: from the one builder: a hidden empty state is still in the document, so
//: there is nothing to wait for.
//: The Notes one is said shorter (the question sent is unchanged): the default
//: label ("Ask Atlas: How does the app decide where a note goes?") took two
//: lines at 390, 332x46, the shape Chat's offer was given a label to avoid.
for (const [id, question, label] of [
  ["empty-message", "How does the app decide where a note goes?", "Ask Atlas where notes go"],
  ["library-empty", "What can I keep in the Library?", undefined],
]) {
  $(id)?.appendChild(atlasSuggestion(question, label));
}

//: **The concept-map door, in the tab people look for it in.** Reported: "the
//: concept map feature is there in the graph but I have no clue how to use it,
//: it isnt a labeled feature and is it even there actually??" It was real and
//: it was three levels away -- Library, then a sub-tab called Boards & maps,
//: then "+ Create", then "New concept map". This tab is already the map of
//: your notes; the only difference is that this one is drawn for you. So the
//: counterpart gets a labelled button here that lands on the maps themselves.
//: Awaited: the sub-tab's handler is library.js's, fetched on the Library's
//: first visit, and a press before it arrived landed on the All view
//: (tests/test_new_document_opens_new.py).
$("graph-concept-maps")?.addEventListener("click", async () => {
  await switchTab("library");
  document.querySelector('#library-subtabs button[data-target="library-view-whiteboard"]')?.click();
  // The sub-tab click can leave the last board open on the canvas; a button
  // called "Mind maps" has to arrive at the list of them.
  wbShowBoardsLanding();
});
restoreDraftLocally();

// --- note picker wiring ---
$("attach-note").addEventListener("click", () => {
  if (notePickerOpen()) closeNotePicker();
  else openNotePicker();
});
$("note-picker-close").addEventListener("click", () => {
  closeNotePicker();
  $("attach-note").focus();
});

// --- image attachment wiring (vision-capable models) ---
$("attach-image").addEventListener("click", () => $("chat-image-input").click());
$("chat-image-input").addEventListener("change", async (e) => {
  if (e.target.files.length) await attachChatFiles(e.target.files);
  e.target.value = ""; // so choosing the same file twice still fires "change"
});
let notePickerSearchDebounceTimeout;
$("note-picker-search").addEventListener("input", () => {
  clearTimeout(notePickerSearchDebounceTimeout);
  notePickerSearchDebounceTimeout = setTimeout(renderNotePickerList, 150);
});
for (const button of document.querySelectorAll("#note-picker-sources [data-picker-source]")) {
  button.addEventListener("click", () => setNotePickerSource(button.dataset.pickerSource));
}

$("note-picker-done").addEventListener("click", () => {
  closeNotePicker();
  $("chat-input").focus();
});
$("note-picker-clear").addEventListener("click", () => {
  //: Clear means clear. This emptied `attachedNoteIds` only, so pressing it
  //: with three files and a map ticked left every one of them staged while the
  //: count line under the button re-read "Nothing attached yet", the panel
  //: contradicting itself in two places at once.
  //:
  //: Images too, now (INBOX 485: the count still read "1 image attached"
  //: after Clear). A staged one holds a live object URL, revoked here exactly
  //: as the send path revokes it, or its Blob leaks for the life of the tab.
  for (const image of attachedImages) if (image.objectUrl) URL.revokeObjectURL(image.objectUrl);
  attachedImages = [];
  renderImageAttachments();
  attachedNoteIds = [];
  attachedDocuments = [];
  attachedFiles = [];
  attachedBoards = [];
  renderAttachments();
  renderDocumentAttachments();
  renderFileAttachments();
  renderBoardAttachments();
  renderNotePickerList();
});
// Click-away and Escape close it, like every other popover in the app.
document.addEventListener("click", (event) => {
  if (!notePickerOpen()) return;
  // `.action-menu` for the same reason the notifications panel needs it: a
  // menu this panel owns is reparented to <body> while open, so a click on
  // one of its options is not a descendant of the panel and would otherwise
  // read as a click away. `.sheet-overlay` the same, on a phone
  // (`openNotePicker`'s own sheet path, chat-attach.js): the panel moves
  // out of `.note-picker` into the sheet's card, and the sheet already
  // owns its own scrim-click and Escape dismissal, so this listener has
  // nothing to add there and every click inside it, otherwise, closed the
  // sheet the instant it was touched.
  if (event.target.closest(".note-picker, .action-menu, .sheet-overlay")) return;
  closeNotePicker();
});
$("note-picker-panel").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.stopPropagation();
    closeNotePicker();
    $("attach-note").focus();
    return;
  }
  notePickerKeydown(event);
});

// --- chat dock "more" disclosure wiring (§37C) ---
$("chat-dock-more-btn").addEventListener("click", () => {
  if (chatDockMoreOpen()) closeChatDockMore();
  else openChatDockMore();
});
document.addEventListener("click", (event) => {
  if (!chatDockMoreOpen()) return;
  if (event.target.closest(".chat-dock-more, .action-menu, .select-menu, .sheet-overlay")) return;
  closeChatDockMore();
});
$("chat-dock-more-panel").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.stopPropagation();
    closeChatDockMore();
    $("chat-dock-more-btn").focus();
  }
});
$("chat-stop").addEventListener("click", () => {
  chatQueueState.held = true;
  chatController?.abort();
});
//: **Escape stops the answer being written** (CHAT_PLAN section 6, the
//: consistency rules: "Enter sends, Shift+Enter newline, Ctrl+K palette,
//: Escape stops streaming"). Only Ctrl+. did (the shortcut table's
//: `stopAI`); Escape mid-answer did nothing, measured by `chataudit.js`,
//: part `keys`. On the document, not the tab, so it is heard from the box
//: (open mid-answer for the queue, INBOX 1321), the Stop button or the page.
//: Only while the Chat tab is on screen and an answer is streaming, and not
//: while anything is open on top: a dialog, the note picker, a menu, each of
//: which takes its own Escape first (they stop the key or prevent it).
//: And only the answer on screen: a turn keeps streaming into the chat it
//: was asked in while the reader opens another (`releaseChatComposer` hides
//: Stop and gives the box back), and an Escape in the new chat's box used
//: to stop that answer unseen (the review, 2026-09-27). Stop is shown
//: exactly while the chat on screen is being answered, so Escape asks it.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || event.defaultPrevented || !chatController) return;
  if ($("tab-chat").classList.contains("hidden")) return;
  if ($("chat-stop").classList.contains("hidden")) return;
  if (document.querySelector(".modal-overlay:not(.hidden), .sheet-overlay:not(.hidden)")) return;
  event.preventDefault();
  chatQueueState.held = true;
  chatController.abort();
});
$("chat-new").addEventListener("click", newChatConversation);
{
  const sortSelect = $("chat-sidebar-sort");
  sortSelect.value = prefs.get(CHAT_SIDEBAR_SORT_KEY, null) || "recent";
  sortSelect.addEventListener("change", () => {
    prefs.set(CHAT_SIDEBAR_SORT_KEY, sortSelect.value);
    loadConversationList();
  });
}
$("persona-peek").addEventListener("click", togglePersonaPrompt);
$("chat-tune-search").addEventListener("click", () => {
  closeChatDockMore();
  openSettingsModal("searchindex", "search-relevance-group");
});
// Searching your chats lives in the Library now (§36F): with the documents,
// the files and the bin, and with sort beside it. This is the way there, said
// out loud, because a list that silently stops at eight is a list that has
// lost your chats.

// A typed find query is a literal, not a pattern: "a.b" must not match
// "axb", and an unbalanced "(" must not throw. CodeQL also flags the
// unescaped shape, and this file has already shipped one polynomial-ReDoS.
// Shared by the lightbox's document find and the global find bar below,
// rather than the same six-character regex copied twice.
function escapeForFind(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// --- global find bar (Ctrl+F on any tab except Documents, which keeps its
// own find-and-replace) -----------------------------------------------------
//
// Deliberately scoped to whichever `.tab-page:not(.hidden)` is currently on
// screen, not the whole document: searching the header, the status bar or a
// hidden tab's stale DOM would surface matches you could never scroll to,
// and the find-and-replace input's own value would match itself.
//
// **Known, accepted limit, not a bug**: the Notes list renders
// incrementally as you scroll (`renderIncrementally`) to keep a large
// notebook's DOM proportional to what's been scrolled past, a note not yet
// painted is not in the DOM yet and this cannot find it, the same limit a
// browser's own native find has on any virtualized list. `#note-search`
// (which filters the underlying data, not the rendered DOM) is the actual
// answer for "find a note I haven't scrolled to" and is not replaced by this.
let globalFindMatches = [];
let globalFindActive = -1;
//: **Find in the web reader is this bar, scoped to the page.** The reader's
//: own find button, or Ctrl+F while the focus is in the web panel with a page
//: open, roots the walk at the page's text rather than the whole Chat tab, so
//: "3 of 12" counts the article and not the conversation beside it. One find
//: bar, not a second one built for one panel.
let globalFindScope = null;

//: **Ctrl+F searches whatever is actually in front of you.** Asked for
//: directly: "allow the ctrl f find function to work within the settings
//: modal". Settings is a modal over the tab page, so a find rooted in the
//: visible `.tab-page` walked the notebook *behind* the dialog -- it found
//: nothing you could see and scrolled a page you were not looking at.
function globalFindWalkableRoot() {
  if (globalFindScope && globalFindScope.checkVisibility?.()) return globalFindScope;
  const settings = document.getElementById("settings-modal");
  if (settings && !settings.classList.contains("hidden")) return settings;
  return document.querySelector(".tab-page:not(.hidden)");
}

//: Settings hides fifteen of its sixteen sections, so a find rooted in the
//: modal only ever sees the one you are on. When a search comes up empty
//: there, this asks the other sections whether any of them contains the
//: words -- a plain `textContent.includes`, no walking and no highlighting --
//: and switches to the first that does, so Ctrl+F answers "where is the
//: setting for X" rather than "not on this page".
function settingsSectionContaining(needle) {
  const modal = document.getElementById("settings-modal");
  if (!modal || modal.classList.contains("hidden")) return null;
  const lower = needle.toLowerCase();
  for (const section of modal.querySelectorAll(".settings-section.hidden")) {
    if ((section.textContent || "").toLowerCase().includes(lower)) {
      return section.id.replace(/^settings-/, "");
    }
  }
  return null;
}

function globalFindClearHighlights() {
  for (const mark of document.querySelectorAll("mark.global-find-hit")) {
    mark.replaceWith(document.createTextNode(mark.textContent));
  }
  globalFindWalkableRoot()?.normalize();
  globalFindMatches = [];
  globalFindActive = -1;
}

let globalFindJumping = false;

function globalFindRun(needle) {
  globalFindClearHighlights();
  const root = globalFindWalkableRoot();
  const count = $("global-find-count");
  if (!needle || !root) {
    count.textContent = "";
    return;
  }
  const lower = needle.toLowerCase();
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.toLowerCase().includes(lower)) {
        return NodeFilter.FILTER_REJECT;
      }
      const el = node.parentElement;
      if (!el || el.closest("script, style, [hidden], .hidden")) {
        return NodeFilter.FILTER_REJECT;
      }
      // A note not yet scrolled into view by renderIncrementally, or a
      // collapsed section, has zero size, nothing to scroll to, so nothing
      // to count as a match. The same reasoning contrastAudit's own visible-
      // text walk used.
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const targets = [];
  let node;
  while ((node = walker.nextNode())) targets.push(node);
  // Nothing on this Settings page, try the other fifteen before giving up.
  //
  // `globalFindJumping` is not belt-and-braces. showSettingsSection hides the
  // section it moves away from, so without it a needle that lives only inside
  // a *collapsed* part of some section would switch to that section, find
  // nothing again, and be free to switch to the next one for ever, the
  // sections take it in turns being the hidden one.
  if (!targets.length && !globalFindJumping) {
    const jump = settingsSectionContaining(needle);
    if (jump && typeof showSettingsSection === "function") {
      globalFindJumping = true;
      try {
        showSettingsSection(jump);
        globalFindRun(needle);
      } finally {
        globalFindJumping = false;
      }
      return;
    }
  }
  const pattern = new RegExp(escapeForFind(needle), "gi");
  for (const textNode of targets) {
    const parts = textNode.nodeValue.split(new RegExp(`(${escapeForFind(needle)})`, "gi"));
    if (parts.length < 2) continue;
    const frag = document.createDocumentFragment();
    for (const part of parts) {
      if (pattern.test(part) && part.toLowerCase() === lower) {
        const mark = document.createElement("mark");
        mark.className = "global-find-hit";
        mark.textContent = part;
        frag.appendChild(mark);
      } else if (part) {
        frag.appendChild(document.createTextNode(part));
      }
    }
    textNode.replaceWith(frag);
  }
  globalFindMatches = [...root.querySelectorAll("mark.global-find-hit")];
  globalFindActive = globalFindMatches.length ? 0 : -1;
  globalFindShowActive();
}

function globalFindShowActive() {
  const count = $("global-find-count");
  for (const mark of globalFindMatches) mark.classList.remove("global-find-current");
  if (!globalFindMatches.length) {
    count.textContent = "No matches";
    return;
  }
  const mark = globalFindMatches[globalFindActive];
  mark.classList.add("global-find-current");
  mark.scrollIntoView({ block: "center", behavior: reducedMotionWanted() ? "auto" : "smooth" });
  count.textContent = `${globalFindActive + 1} of ${globalFindMatches.length}`;
}

function globalFindStep(delta) {
  if (!globalFindMatches.length) return;
  globalFindActive = (globalFindActive + delta + globalFindMatches.length) % globalFindMatches.length;
  globalFindShowActive();
}

function openGlobalFind(opts = {}) {
  const reader = document.getElementById("web-reader");
  const readerOpen = reader && !reader.classList.contains("hidden") && reader.checkVisibility?.();
  const scopeReader =
    readerOpen &&
    (opts.scope === "web-reader" || Boolean(document.activeElement?.closest?.("#web-panel")));
  const scope = scopeReader ? document.getElementById("web-reader-text") : null;
  if (scope !== globalFindScope) {
    globalFindClearHighlights();
    globalFindScope = scope;
  }
  const findInput = document.getElementById("global-find-input");
  if (findInput) {
    const words = scope ? "Find in this page" : "Find on this page";
    findInput.placeholder = `${words}…`;
    findInput.setAttribute("aria-label", words);
  }
  // Ctrl+F while the lightbox's own document find is already showing
  // should reach *that* one instead of stacking a second bar behind the
  // overlay it's not even visible through, the lightbox's find is real
  // extracted text with nothing else underneath it, the same job this bar
  // does for a tab.
  const lightboxFind = document.querySelector(".lightbox .lightbox-find:not(.hidden)");
  if (lightboxFind) {
    lightboxFind.focus();
    return;
  }
  // **A board is the same handoff as the lightbox, for the same reason.**
  // This bar walks the DOM of the visible tab and highlights text nodes, on
  // an open whiteboard that is the wrong tool twice over: the cards are laid
  // out inside a zoomed, transformed canvas layer, so a `mark` around a match
  // sits wherever the pan happens to have left it and often off-screen
  // entirely, and a card can be scrolled far outside the viewport with no
  // scrollIntoView that means anything on an infinite canvas. The board has
  // its own find, which pans the viewport to each match, send Ctrl+F there.
  //: **Find is scoped to what is in front of you.** With Settings open, the
  //: page-wide bar searched the tab hidden behind the dialog; Settings has
  //: its own search, which filters its panes, so Ctrl+F goes there.
  const settingsOpen = !$("settings-modal")?.classList.contains("hidden");
  if (settingsOpen && $("settings-search")) {
    $("settings-search").focus();
    $("settings-search").select();
    return;
  }
  const wbCanvas = document.getElementById("wb-canvas-view");
  const wbView = document.getElementById("library-view-whiteboard");
  if (
    wbCanvas && !wbCanvas.classList.contains("hidden") &&
    wbView && !wbView.classList.contains("hidden") &&
    typeof wbOpenBoardSearch === "function"
  ) {
    wbOpenBoardSearch();
    return;
  }
  const bar = $("global-find-bar");
  bar.classList.remove("hidden");
  const input = $("global-find-input");
  input.focus();
  input.select();
  if (input.value) globalFindRun(input.value);
}

function closeGlobalFind() {
  $("global-find-bar").classList.add("hidden");
  globalFindClearHighlights();
  globalFindScope = null;
  $("global-find-input").value = "";
}

$("global-find-input")?.addEventListener("input", (e) => globalFindRun(e.target.value.trim()));
$("global-find-input")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    globalFindStep(e.shiftKey ? -1 : 1);
  } else if (e.key === "Escape") {
    e.preventDefault();
    // Without this the same Escape also reaches the app-wide handler and
    // closes whatever dialog the find bar is searching -- Settings, now that
    // Ctrl+F works inside it. Escape closes the find bar; a second one closes
    // the dialog.
    e.stopPropagation();
    closeGlobalFind();
  }
});
$("global-find-next")?.addEventListener("click", () => globalFindStep(1));
$("global-find-prev")?.addEventListener("click", () => globalFindStep(-1));
$("global-find-close")?.addEventListener("click", () => closeGlobalFind());
// Switching tabs while the bar is open would otherwise leave it searching a
// now-hidden page, or (worse) leave <mark> wrappers stuck inside a tab-page
// that a later feature might re-render around and lose track of.
window.addEventListener("tabSwitched", () => {
  if (!$("global-find-bar").classList.contains("hidden")) closeGlobalFind();
});

$("conv-browse-all").addEventListener("click", async () => {
  //: Awaited: `libraryKind` is a `let` in library.js and the two renders are
  //: its functions, so all three need that file present (A1). Without the
  //: await the assignment would create a stray global that library.js then
  //: shadows, and the Library would open unfiltered.
  await switchTab("library");
  libraryKind = "chat";
  renderLibraryFilters();
  renderLibrary();
});

//: **Fork: keep this thread, try another direction.** Asked for directly.
//: The server copies (`POST /conversations/{id}/fork`) rather than branching: 
//: see that route's docstring for why a tree with shared ancestry is the
//: wrong size of machinery for one JSON blob per chat.
//:
//: Only meaningful once something has been said, so the button hides itself
//: on an empty pane rather than offering to duplicate nothing.
$("chat-fork").addEventListener("click", async () => {
  if (!chatConv || chatConv.id === null) {
    toast("Nothing to fork yet, ask something first.");
    return;
  }
  try {
    const fork = await apiJson(`/conversations/${chatConv.id}/fork`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    await loadConversationList();
    chatWriteRecord("chatForkUndo", fork);
    toastAction(`Forked to “${fork.title}”.`, "Open it", () => openConversation(fork.id), { go: { open: "conversation", id: fork.id } });
  } catch (error) {
    toast(error.message || "Couldn't fork this conversation.", true);
  }
});

//: Renaming, where the name is. It used to mean leaving the tab and finding
//: the chat in the Library, for a property whose whole purpose is helping
//: you recognise the thread you are currently looking at.
//: **A name you give before there is anything to name.**
//:
//: Reported: *"the click to rename this conversation button doesnt work."* It
//: did nothing, silently, and the reason is the guard this used to open with:
//: a chat has no row until its first message is sent (`convRef.id === null`
//: until the POST in `sendChatMessage` comes back), so on a fresh chat, which
//: is exactly when you would want to name the thing you are about to start, 
//: the handler returned before it did anything at all. No toast, no dialog,
//: no clue.
//:
//: A pending title rather than an error message: the name is remembered and
//: applied the moment the conversation exists. It also *wins over the AI's own
//: retitle*, which is the whole point, a thread someone bothered to name must
//: not be renamed out from under them three seconds later.
let chatPendingTitle = null;

async function renameCurrentConversation() {
  if (!chatConv) return;
  const current = $("chat-title").textContent;
  const next = await promptDialog("Rename this conversation:", current);
  if (!next || next === current) return;
  if (chatConv.id === null) {
    chatPendingTitle = next;
    $("chat-title").textContent = next;
    toast("Named. It is saved with your first message.");
    return;
  }
  try {
    await apiJson(`/conversations/${chatConv.id}`, {
      method: "PUT",
      body: JSON.stringify({ title: next }),
    });
    $("chat-title").textContent = next;
    chatWriteRecord("chatTitleUndo", chatConv.id, current, next);
    loadConversationList();
  } catch (error) {
    toast(error.message || "Couldn't rename this conversation.", true);
  }
}

//: Called by both places that create a conversation from the composer. Silent
//: and best-effort: a title that fails to stick is worth a wrong name in the
//: sidebar, not an error over the answer that just arrived.
function applyPendingChatTitle(conversationId, viewing) {
  const wanted = chatPendingTitle;
  chatPendingTitle = null;
  if (!wanted) return false;
  if (viewing) $("chat-title").textContent = wanted;
  apiJson(`/conversations/${conversationId}`, {
    method: "PUT",
    body: JSON.stringify({ title: wanted }),
    silent: true,
  })
    .then(() => loadConversationList())
    .catch(() => {});
  return true;
}

//: Built once, at boot, the header's ⋯ is the same for every conversation,
//: unlike a note card's, which is rebuilt per row.
mountChatActionsMenu();

//: The context pill's popover is wired in usage-ledger.js, with its rows.

$("chat-title").addEventListener("click", renameCurrentConversation);
$("chat-title").addEventListener("keydown", (event) => {
  //: Space and Enter, because this is a `<h2 role="button">` and the browser
  //: only gives those two keys to a real `<button>` for free.
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    renameCurrentConversation();
  }
});
$("chat-compress").addEventListener("click", compressChatContext);
$("chat-compress-apply").addEventListener("click", applyCompression);
$("chat-compress-cancel").addEventListener("click", () =>
  $("chat-compress-panel").classList.add("hidden")
);
$("chat-uncompress").addEventListener("click", () => {
  // Undo is one assignment, because nothing was ever removed, the turns have
  // been sitting there all along.
  chatSummary = null;
  renderCompressionState();
  toast("Back to sending the real messages.");
});
// Debounced, because the matcher walks every installed skill and this fires on
// every keystroke. 250ms is under the pause between words, so the suggestion is
// there by the time you stop typing to read it, and never mid-word.
let chatNudgeTimer = null;
$("chat-input").addEventListener("input", () => {
  clearTimeout(chatNudgeTimer);
  chatNudgeTimer = setTimeout(() => {
    // Emptying the box by hand is the same event as sending, as far as the
    // suggestions are concerned: the draft they were about is gone.
    if (!$("chat-input").value.trim()) resetChatNudge();
    else renderChatNudge();
  }, 250);
});
//: The composer's recall position: an index into the conversation's sent
//: messages, or null when the box holds your own typing. `draft` is what was
//: in the box before the first step, given back past the newest.
const chatRecall = { index: null, draft: "" };

function chatRecallStep(box, direction) {
  const sent = [...document.querySelectorAll("#chat-messages .msg.user")]
    .map((bubble) => bubble.dataset.sent)
    .filter(Boolean);
  if (!sent.length) return false;
  const recalled = chatRecall.index !== null && box.value === sent[chatRecall.index];
  if (!recalled) {
    //: Only from an empty box: text you are writing keeps its arrow keys.
    if (box.value || direction > 0) return false;
    chatRecall.draft = box.value;
    chatRecall.index = sent.length;
  }
  const next = chatRecall.index + direction;
  if (next < 0) return true;
  if (next >= sent.length) {
    chatRecall.index = null;
    box.value = chatRecall.draft;
  } else {
    chatRecall.index = next;
    box.value = sent[next];
  }
  box.setSelectionRange(box.value.length, box.value.length);
  box.dispatchEvent(new Event("input", { bubbles: true }));
  return true;
}

$("chat-input").addEventListener("keydown", (e) => {
  // Enter sends, Shift+Enter (or Ctrl/Cmd+Enter) writes a newline. The box is
  // a textarea now, so "send" has to be chosen rather than inherited.
  if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
    e.preventDefault();
    sendChatMessage();
    return;
  }
  //: **ArrowUp and ArrowDown step through what you sent**, the way a terminal
  //: or a chat app's composer does (the owner, 2026-09-24: "the small things
  //: every user expects", then "include down arrow as well to toggle between
  //: previous inputs"). Up from an empty box (or from a recalled message you
  //: have not changed) fills the box with the one before; Down walks back to
  //: the newest, then to what you had typed. A box you have typed into keeps
  //: its arrows for moving the caret.
  if ((e.key === "ArrowUp" || e.key === "ArrowDown") && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
    if (chatRecallStep(e.target, e.key === "ArrowUp" ? -1 : 1)) e.preventDefault();
  }
});
$("persona-select").addEventListener("change", async () => {
  // Remember the choice so the Notes quick-ask uses the same persona.
  const persona = $("persona-select").value;
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ active_persona: persona }),
  }).catch(() => {});
  // Update the local cache too, not just the server, renderChatEmptyState()
  // and the Notes quick-ask both read prefsCache.active_persona directly,
  // and neither reloads preferences on its own after this change.
  if (prefsCache) prefsCache.active_persona = persona;
  // If a fresh, empty chat is on screen right now, its greeting named the
  // *previous* persona: redraw it rather than leaving it stale until the
  // next "+ New" (ROADMAP Tier 3 §21).
  if ($("chat-messages").querySelector(".chat-empty")) {
    $("chat-messages").querySelector(".chat-empty").remove();
    renderChatEmptyState();
  }
});
//: **Live or Source, never a separate Preview** (INBOX 430, the owner: "note
//: forms use the live view with a source toggle, no Preview"). The note box
//: already renders as you type (documents.js, the note surface's Live
//: rendering), so a Preview pane was a second copy of what the box shows, in
//: a box you could not type in. The strip's toggle is Source now: the
//: markdown as typed, without the live formatting, and back. One choice for
//: every note box, remembered (`noteSourceWanted`).
function noteSourceOn() {
  try {
    return prefs.get("note-source-view", null) === "1";
  } catch {
    return false;
  }
}

function syncNoteSourceButtons() {
  for (const button of document.querySelectorAll("#entry-preview-toggle, [data-note-preview]")) {
    button.setAttribute("aria-pressed", String(noteSourceOn()));
    button.classList.toggle("is-active", noteSourceOn());
  }
}

function setNoteSource(on) {
  try {
    prefs.set("note-source-view", on ? "1" : "0");
  } catch {
    /* storage blocked: this box only */
  }
  //: A box not mounted yet reads the choice when it mounts.
  for (const id of ["entry-content", "entry-edit-content"]) {
    const host = $(id);
    if (host && typeof setNoteSurfaceSource === "function") setNoteSurfaceSource(host, on);
  }
  syncNoteSourceButtons();
}

$("entry-preview-toggle")?.addEventListener("click", () => setNoteSource(!noteSourceOn()));
syncNoteSourceButtons();

//: The persona the greeting speaks as: the override, or Chat's own when the
//: override is "Same as Chat", or the assistant's name when Chat has none.
function dashboardGreetingPersona() {
  return (prefsCache && prefsCache.dashboard_persona) || $("persona-select")?.value || aiNameNow();
}

//: Its face beside the picker (the owner: "I want the persona avatar to
//: appear next to where you set the persona for the dashboard greeting").
function paintDashboardPersonaMark() {
  fillPersonaMark($("dashboard-persona-mark"), dashboardGreetingPersona(), 28);
}

for (const id of RESPONSE_MODE_SELECTS) {
  $(id)?.addEventListener("change", (e) => setResponseMode(e.target.value));
}
// The AI status dot. Hover is CSS; these are the paths hover doesn't cover: 
// touch, where there is no hover at all, and keyboards.
$("ai-status").addEventListener("click", () => toggleAiStatusPopup());
document.addEventListener("click", (event) => {
  // Anywhere outside closes it, the way every other popover here behaves.
  if (!event.target.closest(".ai-status-wrap")) toggleAiStatusPopup(false);
});
$("ai-status").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    toggleAiStatusPopup(false);
    $("ai-status").focus();
  }
});

// The status bar (§36D). Every item goes somewhere: a count you cannot act on
// is a number, and a number in permanent furniture is the decoration the
// roadmap warned this bar would become if anything was added without a job.
$("status-notes").addEventListener("click", () => {
  switchTab("notes");
  showNotesSection("browse"); // or you land on whichever sub-tab was last open
});
$("status-reminders").addEventListener("click", () => switchTab("reminders"));
//: A running job's slot opens Activity's Running tab, where it can stop
//: (rule 5, decision 70); its history stays in Settings, Background tasks.
$("status-task").addEventListener("click", () => window.openActivity?.("running"));
$("status-command").addEventListener("click", () => openPalette());
$("status-agent")?.addEventListener("click", () => toggleAgentPalette());
//: settings.js owns the Guide sheet and loads after this file, so the lookup
//: is deferred to the click rather than taken now. The same shape the phone's
//: More sheet already uses for the same function.
$("status-guide")?.addEventListener("click", () => {
  openHelpChat();
});

$("status-find")?.addEventListener("click", () => openFinder());

//: The dashboard's own doorway to the same dialog. `keydown` as well as
//: `click`, so a person who starts typing at it is not told to press it
//: first: the letter they typed opens the dialog and is the first letter of
//: the query, which is what a field would have done.
const dashFind = $("dash-find");
if (dashFind) {
  dashFind.addEventListener("click", () => openFinder());
  dashFind.addEventListener("keydown", (event) => {
    if (event.key.length !== 1 || event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    openFinder(event.key);
    //: Opened with the letter already in it, so `openFinder`'s own `select()`
    //: would highlight it and the next keystroke would replace it.
    const input = document.getElementById("finder-input");
    if (input) input.setSelectionRange(input.value.length, input.value.length);
  });
  const keysHint = dashFind.querySelector(".dash-find-keys");
  if (keysHint) keysHint.textContent = shortcutHint("findAnything") || (STATUS_META_KEY.startsWith("\u2318") ? "\u2318P" : "Ctrl+P");
}

// Paint it before any poll lands, so the bar is furniture from the first frame
// rather than four boxes that pop into existence a second later.
renderStatusBar();

$("graph-refresh").addEventListener("click", () => {
  graphHighlightIds = null; // a refresh clears any "similar notes" spotlight
  renderGraph();
});
$("graph-export-png")?.addEventListener("click", exportGraphPng);
// Direct instruction: "I want to be able to unroot and reset the graph to
// free float if I want with a button." One request releases every pinned
// node at once (routes_graph.py's unpin_all_nodes) rather than tracking
// each one down to double-click it individually; renderGraph() afterwards
// re-fetches from /graph, which is what actually clears fx/fy, the same
// path #graph-refresh already uses, so a freshly unpinned layout settles
// through the ordinary simulation rather than a special-cased one.
$("graph-unpin-all")?.addEventListener("click", async (event) => {
  // The button rides the Physics fold's own `<summary>` (index.html), so a
  // press on it is also a press on the disclosure. `preventDefault` cancels
  // the summary's activation behaviour and nothing else: a `type="button"`
  // has no default action of its own to lose.
  event.preventDefault();
  try {
    const result = await apiJson("/graph/unpin-all", { method: "POST" });
    graphHighlightIds = null;
    await renderGraph();
    toast(
      result.unpinned
        ? `${result.unpinned} note${result.unpinned === 1 ? "" : "s"} released: the layout can move freely again.`
        : "Nothing was pinned."
    );
  } catch (error) {
    toast(error.message || "Couldn't unpin the graph.", true);
  }
});
$("graph-similarity").addEventListener("change", renderGraph);
$("graph-entities")?.addEventListener("change", renderGraph);
$("graph-documents")?.addEventListener("change", renderGraph);
$("graph-maps")?.addEventListener("change", renderGraph);
// The tuned-once controls, folded away. Remembered, because whether you want
// physics sliders on screen is a property of how you use the map rather than
// of one visit: and because a panel that reopens closed every time is one
// people stop opening.
// Each fold in the options panel remembers whether it is open, for the reason
// the panel itself does: which of these you want on screen is a property of
// how you use the map, not of one visit. Closed is the default, which is what
// gets the list back under the panel's own cap (GRAPH_PLAN, "Decision made,
// 2026-09-20"); a fold you opened stays open until you close it.
function initGraphOptionFolds() {
  for (const fold of document.querySelectorAll("#graph-options details.graph-options-fold")) {
    if (fold._foldWired || !fold.id) continue;
    fold._foldWired = true;
    const key = `graph-fold-${fold.id}`;
    try {
      fold.open = prefs.get(key, null) === "1";
    } catch (error) {
      fold.open = false;
    }
    fold.addEventListener("toggle", () => {
      try {
        prefs.set(key, fold.open ? "1" : "0");
      } catch (error) {
        /* A browser with storage refused still folds, it just forgets. */
      }
    });
  }
}
initGraphOptionFolds();

function setGraphOptionsOpen(open) {
  const panel = $("graph-options");
  const toggle = $("graph-options-toggle");
  if (!panel || !toggle) return;
  //: **Below 600 the panel never floats** (UI_MODERNISATION_PLAN Phase 11
  //: item 4). Measured at 390x844 on the running app: open, it is 350x288
  //: over a map that is 362x653, which is 42% of the map covered by a panel
  //: whose own content is 795px scrolling inside 286px. The same controls
  //: are the sheet below, so the saved "open" pref still rides here (a
  //: window widened again opens what it had open) and only the floating
  //: half is refused.
  const phone = window.matchMedia(PHONE_TABS).matches;
  panel.classList.toggle("hidden", !open || phone);
  toggle.setAttribute("aria-expanded", String(open && !phone));
  toggle.classList.toggle("is-on", open && !phone);
  prefs.set("graph-options-open", open ? "1" : "0");
}

//: The phone's one sheet of map controls (`openGraphControlsSheet`) lives in
//: graph.js, the Graph tab's lazy bundle, since 2026-10-03 (INBOX 434: the
//: bytes paid for the note outbox at boot). Its close handle stays here,
//: because this file's listeners and settings-panes.js read it.
let graphSheetClose = null;

$("graph-options-toggle").addEventListener("click", (event) => {
  // The click must not reach the document listener below, which would read
  // the panel it has just opened as a click outside it and close it again.
  event.stopPropagation();
  if (window.matchMedia(PHONE_TABS).matches) {
    if (graphSheetClose) graphSheetClose();
    else openGraphControlsSheet(event.currentTarget);
    return;
  }
  setGraphOptionsOpen($("graph-options").classList.contains("hidden"));
});
//: A window dragged across the boundary with the sheet open would leave the
//: map's controls in a dialog the desktop layout has no opener for, and the
//: fold below 1100 moves one of the pieces the sheet borrowed. Closing puts
//: every one of them back where the width that is arriving expects it.
window.matchMedia(PHONE_TABS).addEventListener("change", () => graphSheetClose?.());
// A popover closes the three ways every popover in this app closes: its own
// button, a click outside it, and Escape. It gained the last two when it
// stopped being a strip in the column and became the gear's menu (INBOX 21):
// a panel anchored to a button that only that button can dismiss is the one
// shape a menu never has.
document.addEventListener("click", (event) => {
  const panel = $("graph-options");
  if (!panel || panel.classList.contains("hidden")) return;
  if (panel.contains(event.target) || $("graph-options-toggle").contains(event.target)) return;
  if (!event.target.isConnected) return;
  setGraphOptionsOpen(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  const panel = $("graph-options");
  if (!panel || panel.classList.contains("hidden")) return;
  // **The Escape is spent here.** The full-screen handler further down is on
  // the same target for the same key, and listener order alone does not stop
  // it: the comment there says a panel over the map "takes the first Escape",
  // which was only ever true if something actually stopped the event. One key
  // press that closes a panel and leaves full screen at the same time is the
  // bug that sentence was written to prevent.
  event.stopImmediatePropagation();
  setGraphOptionsOpen(false);
});
// Trace (§9), folded away the same way Options is (§37F): it is a mode you
// step into to ask one question, not a strip worth drawing on every visit.
// Closing it does not clear an active trace: the path stays drawn on the map
// itself, the same as Options' sliders keep their values while hidden.
$("graph-trace-toggle").addEventListener("click", () => {
  const open = $("graph-trace").classList.contains("hidden");
  setTracePanelOpen(open);
  if (open && !graphSheetClose) setGraphOptionsOpen(false);
});
$("graph-focus-clear").addEventListener("click", () => {
  graphFocusModeId = null;
  recordTabVisit("graph", null);
  $("graph-focus-clear").classList.add("hidden");
  renderGraph();
  toast("Exited Focus Mode.");
});
$("graph-highlight-clear").addEventListener("click", () => {
  graphHighlightIds = null;
  applyGraphHighlight();
  toast("Highlight cleared.");
});
//: The trace strip's X leaves trace mode, strip and result both, the same
//: as Escape: it used to be `clearTrace()`, which kept the mode on and only
//: reset the two ends, under a tooltip that said it left (INBOX 421 d).
$("graph-trace-clear").addEventListener("click", () => setTracePanelOpen(false));
// The legend's own collapse: asked for twice: "the categories toggle line
// needs to be collapsible or redesigned." A fixed row taken from the
// canvas whether or not anyone reads it; collapsing it reclaims that row
// entirely. Persisted like the graph's other view preferences
// (graph-colour, right above) rather than reset every visit.
(() => {
  const row = document.querySelector(".graph-legend-row");
  const toggle = $("graph-legend-toggle");
  if (!row || !toggle) return;
  const apply = (collapsed) => {
    row.classList.toggle("legend-collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.title = collapsed ? "Show the legend" : "Hide the legend";
    toggle.setAttribute("aria-label", toggle.title);
    // A menu item, not the bare caret it was when it sat in the strip: the
    // dock's View menu (Phase 8) names what each row does, and a row that is
    // only an arrow names nothing.
    setLabel(toggle, collapsed ? "ph:eye Show legend" : "ph:eye-slash Hide legend");
  };
  apply(prefs.get("graphLegendCollapsed", null) === "1");
  toggle.addEventListener("click", () => {
    const collapsed = !row.classList.contains("legend-collapsed");
    apply(collapsed);
    prefs.set("graphLegendCollapsed", collapsed ? "1" : "0");
  });
})();
// What the colours mean, remembered like the layout is, it is a property of
// how you read your notebook, not of one visit.
$("graph-colour").addEventListener("change", (event) => {
  prefs.set("graph-colour", event.target.value);
  renderGraph();
});
// What the sizes mean (INBOX 430), remembered the same way.
$("graph-size").addEventListener("change", (event) => {
  prefs.set("graph-size", event.target.value);
  renderGraph();
});
$("graph-hide-orphans").addEventListener("change", renderGraph);
// Labels toggle just flips a class, no need to rebuild the whole map.
$("graph-labels").addEventListener("change", (e) => {
  $("graph-box").classList.toggle("graph-labels-hidden", !e.target.checked);
  // The canvas renderer reads the tickbox in its own draw (a label is drawn or
  // it is not: there is no layer to fade), so it needs one more frame.
  if (typeof gcRequestDraw === "function") gcRequestDraw();
  // The layer's positions are skipped while it is hidden (see graph.js's tick
  // handler: it is one <g> per note, transformed ~300 times a settle, and
  // moving something invisible is work nobody can see). A settled simulation
  // has no further ticks, so turning them back on has to reposition them here
  // or the names sit detached from their notes until something redraws.
  graphCatchUpLabels();
});
let graphSearchDebounceTimeout;
$("graph-search").addEventListener("input", () => {
  clearTimeout(graphSearchDebounceTimeout);
  graphSearchDebounceTimeout = setTimeout(applyGraphHighlight, 150);
});

// Physics sliders: persist, then rebuild the simulation with the new forces.
for (const key of ["gravity", "spread", "link-force"]) {
  const input = $(`graph-${key}`);
  input.value = prefs.get(`graph-${key}`, null) ?? 50;
  input.addEventListener("change", () => {
    prefs.set(`graph-${key}`, input.value);
    renderGraph();
  });
}

// Node popup: edit a note in place on the map.
$("graph-popup-close").addEventListener("click", closeGraphPopup);
// Resizing the window changes the map's size, so an open popup needs re-clamping.
// Only once the graph bundle has been asked for: placeGraphPopup is a stand-in
// before that, and a bare listener made every window resize on a session that
// never opened Graph fetch the whole bundle to clamp a popup that cannot exist.
window.addEventListener(
  "resize",
  () => {
    if (lazyModuleLoads.has("graph")) placeGraphPopup();
  },
  { passive: true }
);
$("graph-popup-save").addEventListener("click", saveGraphPopup);
// Save is shown only once the note differs from what loaded (GRAPH_PLAN
// Phase 6), so both fields have to tell the gate when they change.
for (const id of ["graph-popup-content", "graph-popup-tags"]) {
  $(id).addEventListener("input", syncGraphPopupSave);
}
// "Open in Notes" now lives in the popup's action row (renderGraphPopupActions).
// Clicking empty canvas dismisses the popups.
$("graph-svg").addEventListener("click", () => {
  closeGraphPopup();
  closeGraphNewNote();
});
// Grow the map: double-click empty space to add a note right there.
$("graph-svg").addEventListener("dblclick", (event) => {
  if (event.target.closest(".graph-node")) return; // node dblclick pins it
  openGraphNewNote(event);
});
$("graph-add-node").addEventListener("click", () => openGraphNewNote(null));
$("graph-new-close").addEventListener("click", closeGraphNewNote);
$("graph-new-save").addEventListener("click", saveGraphNewNote);
$("graph-new-content").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) saveGraphNewNote();
});

//: The zoom strip's buttons and full screen are wired in graph.js, the
//: graph's own bundle (2026-10-10, the boot script budget): nothing on the
//: Graph tab can be pressed before it has loaded (`switchTab`'s `inert`),
//: and the two callers here and in navigation.js run only while the card is
//: already full screen, which only graph.js can have made it.

//: **One flag for "something fills the whole window"** (INBOX 726, the owner:
//: "I can see atlas on the edges when on the full screen graph", then "the
//: same full screen companion issue with other full screens probably too").
//: The companion floats over the page at z-index 44; a full-screen surface
//: is a fixed card with rounded corners at 1000, so the companion showed
//: round its edges. `<html data-fullscreen="graph whiteboard">` lists the
//: surfaces that are up, and the companion's own container fades out on any
//: of them (08-consistency.css, `#nm-buddy-band`), whichever avatar it is
//: drawing. Each surface is *watched* rather than told: a full screen is left
//: from many places (Escape, the back button, a tab switch, the palette), and
//: the one that forgot to say so is the one that leaves the companion gone.
//: The class is the truth, so the class is what is observed. A new full-screen
//: surface must be registered here; `tests/test_ui_batch_726.py` fails if a
//: `*fullscreen` class is toggled anywhere that no watch names.
const fullscreenSurfaces = new Set();

function setFullscreenSurface(name, on) {
  fullscreenSurfaces[on ? "add" : "delete"](name);
  if (fullscreenSurfaces.size) document.documentElement.dataset.fullscreen = [...fullscreenSurfaces].join(" ");
  else delete document.documentElement.dataset.fullscreen;
}

function watchFullscreenSurface(name, id, isUp) {
  const el = $(id);
  if (!el) return;
  const sync = () => setFullscreenSurface(name, isUp(el) && !el.closest(".hidden"));
  const watch = new MutationObserver(sync);
  watch.observe(el, { attributes: true, attributeFilter: ["class"] });
  //: A tab switched away from leaves its full screen class on, under `hidden`.
  for (const page of document.querySelectorAll(".tab-page")) watch.observe(page, { attributes: true, attributeFilter: ["class"] });
  sync();
}

watchFullscreenSurface("graph", "graph-card", (el) => el.classList.contains("graph-fullscreen"));
//: The board, a mind map (a board with a tree) and Present frames (which
//: enters the same full screen first).
watchFullscreenSurface("whiteboard", "library-view-whiteboard", (el) => el.classList.contains("wb-fullscreen"));
//: The document's focus mode, which is also the only caller of the browser's
//: own `requestFullscreen` (documents.js), so that is covered by it.
watchFullscreenSurface("documents", "tab-documents", (el) => el.classList.contains("doc-focus"));
//: The OCR workspace is a modal over the whole window (shown, not full-screen
//: by class); the lightbox sets its own flag when it opens and closes
//: (lightbox-view.js), since it is built and removed rather than shown.
watchFullscreenSurface("ocr", "ocr-workspace", (el) => !el.classList.contains("hidden"));
// Escape leaves full screen ("restore on Esc"), guarded on the class. INBOX
// 275: listener order does not stop an event, so anything open over the map
// (the lightbox, a dialog) owns its Escape through `activeOverlay()`, which
// is asked below, rather than through a new `stopPropagation()` here.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (!$("graph-card")?.classList.contains("graph-fullscreen")) return;
  if (activeOverlay() || event.helpPopoverSpent) return;
  toggleGraphFullscreen();
});

// Wave M: batch operations + skill/persona sharing.
// Reported directly: "there's also no refresh button on the your notes
// subtab", every other list in the Library had one (`#library-refresh` and
// its four siblings); the notebook's own front page did not. `loadEntries`
// is the same reload every autosave and filter change already calls.
$("notes-refresh")?.addEventListener("click", () => loadEntries());
//: The Notes dock's primary (and the phone's floating +): Capture, with the
//: box ready to type in. `showNotesSection`'s own `focus` lands on the
//: sub-tab button, which is right for a keyboard moving between sections
//: and wrong here, where the press meant "I want to write".
$("notes-new-note").addEventListener("click", () => startNewNote());

//: **Every "new note" lands in the box, ready to type** (INBOX 434): the
//: button, Ctrl+Shift+N, the dashboard's actions and the empty states all
//: come here. Ctrl+Shift+N went to Notes and focused a box that was hidden
//: whenever Notes was last on Browse: the focus fell to <body> and what was
//: typed next went nowhere, or fired a single-key shortcut.
function startNewNote() {
  if ($("tab-notes").classList.contains("hidden")) switchTab("notes");
  showNotesSection("capture");
  // The box is a live editor (documents.js `mountNoteSurface`) that mounts
  // over the textarea the first time Capture shows, and the mount takes the
  // focus a plain `focus()` had just set: measured in Chromium, the textarea
  // was the active element 50ms after the press and nothing was at 750.
  // Focusing the surface the mount resolves to lands on the editor whether
  // this is its first showing or its fiftieth.
  const box = $("entry-content");
  box?.focus();
  //: `mountNoteSurfaceNow` (app.js) fetches the editor's bundle when it is
  //: not in yet; the bare `mountNoteSurface` is undefined until then, which
  //: left the focus on the body on a fresh boot (INBOX 432, measured).
  mountNoteSurfaceNow(box).then((surface) => surface?.focus()).catch(() => {});
}
$("select-btn").addEventListener("click", () =>
  selectMode ? exitSelectMode() : enterSelectMode()
);
//: The Manage categories panel (notes-list.js), from the notes sidebar's
//: Categories head and from Settings (INBOX 431 (e)).
$("manage-categories-btn").addEventListener("click", () => openManageCategories());
$("manage-categories-foot").addEventListener("click", () => openManageCategories());
//: The tag manager (tag-manager.js, lazy): the Notes ⋯ menu and Settings
//: (INBOX 447 (4)); the sidebar's Tags row and the palette open it too.
//: Tidy (INBOX 691, tidy.js): fetched once the boot is done, so its count is on the dock.
$("notes-tidy").addEventListener("click", () => openTidySheet());
setTimeout(() => ensureModule("tidy"), 4e3);
$("notes-manage-tags").addEventListener("click", () => {
  $("notes-more-menu")?.removeAttribute("open");
  openTagsSheet();
});

//: **Select all, as one toggle** (owner: "no select all option??"). Every
//: note the current filter shows, across pages, since the batch actions act
//: on `selectedIds` rather than on what is painted; pressed again with all
//: of them ticked it clears. One button rather than a Select all and a
//: Deselect all pair: the bar already has Cancel to leave select mode.
function toggleSelectAllRows(rows, repaint) {
  const all = rows.length > 0 && rows.every((row) => selectedIds.has(row.id));
  for (const row of rows) {
    if (all) selectedIds.delete(row.id);
    else selectedIds.add(row.id);
  }
  updateBatchCount();
  repaint();
}
$("batch-select-all").addEventListener("click", () => toggleSelectAllRows(libraryVisibleRows(), renderEntries));
//: Notes and boards only, the rule `timelineRowEl` applies to its ticks: the
//: bar's actions are actions on an Entry, and a document or reminder id in
//: `selectedIds` would be handed to the wrong table (a delete of the wrong
//: row). The first version of this button selected every visible row.
function timelineSelectableRows() {
  return timelineVisibleRows().filter((row) => row.kind === "note" || row.kind === "board");
}
$("timeline-batch-select-all")?.addEventListener("click", () =>
  toggleSelectAllRows(timelineSelectableRows(), paintTimeline)
);

$("batch-tag").addEventListener("click", batchTag);
$("batch-delete").addEventListener("click", batchDelete);
$("batch-cancel").addEventListener("click", exitSelectMode);

$("tools-toggle").addEventListener("change", async () => {
  // The pill reads from this checkbox, so anything else that flips it, a
  // skill that needs tools, a restored preference, has to redraw the pair or
  // the two disagree about which mode you are in.
  renderChatModeSeg();
  // Remember the choice so it survives restarts.
  await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ tools_enabled: $("tools-toggle").checked }),
  }).catch(() => {});
});

// In-chat web-search toggle: reflects and flips the web_search_enabled pref,
// with a clear active state (it's the same setting as Settings → Web search).
function renderWebSearchToggle() {
  const on = Boolean(prefsCache && prefsCache.web_search_enabled);
  const button = $("web-search-toggle");
  button.classList.toggle("active", on);
  button.setAttribute("aria-pressed", on ? "true" : "false");
  //: **Web stays pressable with no model, and says what it does then** (the
  //: owner, 2026-10-10: "Do plan and web search work with the composer??").
  //: The answer from your notes never searches the web: a search is a tool
  //: call, and tools need Agent mode. The button also opens the search panel,
  //: which works with no model at all, so greying it would take browsing away
  //: to say something a title can say.
  button.dataset.enabledTitle ??= button.title;
  button.title = agentModeAvailable() ? button.dataset.enabledTitle : "Browse the web here. With no model, answers come from your notes only.";
}
// Plan Plan: send what is in the box as a request that must be planned first.
//
// The instruction is a sentence rather than a flag on the request because the
// planning path is the model's own `make_plan` tool: the server already knows
// how to receive a plan, show it, tick its steps and let the user stop it
// mid-run (§35K). What was missing was any way to *ask* for one. Adding a
// parameter would mean a second route into the same behaviour that could drift
// from the first; asking in words uses the machinery that is already proven.
//
// Agent mode is turned on rather than required. A plan whose steps cannot be
// carried out is a list, and "why did nothing happen?" is a worse experience
// than a mode that changed under you and said so.
const PLAN_PREFIX =
  "Plan this before you do any of it. Call make_plan with the goal and the " +
  "steps, then carry the plan out.";

// Plan mode is a TOGGLE, not a second send button.
//
// It was: type your request, then press Plan instead of Send. That put the
// decision in the wrong place, you had to remember, after writing, to use a
// different button, and pressing Enter (which is how anyone sends a message)
// silently skipped planning. Asked for directly: "the user should be able to
// select it as a togglable mode, so that when they write in their prompt and
// press the send button or enter etc, it will use the plan mode".
//
// So it arms instead. Turn it on, write, send however you like. It stays on
// across messages the same way Web does, because "I am working on something
// that needs planning" is a state you are in for a while, not a one-off.
let planModeOn = false;

function renderPlanToggle() {
  const button = $("chat-plan");
  if (!button) return;
  button.setAttribute("aria-pressed", String(planModeOn));
  button.classList.toggle("active", planModeOn);
  button.title = planModeOn
    ? "Plan mode is on, your next message is planned first, and the steps are shown before anything touches your notes. Click to turn off."
    : `Plan mode: plan the request first, ${aiNameNow()} draws the steps and shows them before it starts`;
}

// Applied by sendChatMessage on the way out, so every route into it, the Send
// button, Enter, a suggestion chip, goes through planning when the mode is on.
// Reading the flag at send time rather than at click time is the whole point.
function applyPlanMode(question) {
  if (!planModeOn) return null;
  return `${question}\n\n${PLAN_PREFIX}`;
}

$("chat-plan").addEventListener("click", async () => {
  planModeOn = !planModeOn;
  renderPlanToggle();
  if (!planModeOn) {
    toast("Plan mode off.");
    return;
  }
  // A plan whose steps cannot be carried out is a list, so arming the mode
  // arms what it needs. Announced rather than silent: a mode that changed
  // under you and said so beats "why did nothing happen?".
  if (!$("tools-toggle").checked) {
    await setChatMode("agent");
    toast("Plan mode on, and switched to Agent, a plan needs to be able to act.");
  } else {
    toast("Plan mode on: your next message gets planned first.");
  }
  $("chat-input").focus();
});

renderPlanToggle();

$("web-search-toggle").addEventListener("click", async () => {
  //: On with the panel shut, a click opens the panel rather than turning web
  //: off (the owner, 2026-10-26: it took off-then-on to see it). A click with
  //: the panel open turns web off.
  if (prefsCache?.web_search_enabled && $("web-panel").classList.contains("hidden")) {
    toggleWebPanel(true);
    return;
  }
  const next = !(prefsCache && prefsCache.web_search_enabled);
  prefsCache = await apiJson("/preferences", {
    method: "PUT",
    body: JSON.stringify({ web_search_enabled: next }),
  }).catch(() => prefsCache);
  renderWebSearchToggle();
  $("pref-web-search").checked = next; // keep the Settings checkbox in sync
  if (next) {
    toggleWebPanel(true); // turning it on reveals the search panel
    toast("Web search on: Atlas can search, and you can browse here.");
  } else {
    toggleWebPanel(false);
    toast("Web search off.");
  }
});
$("web-panel-close").addEventListener("click", () => toggleWebPanel(false));
//: Enter searches; there is no Search button to press. ArrowDown walks from
//: the field into the results (and ArrowUp from the first result back to the
//: field, below), which is how every search list the owner compares this to
//: behaves. Skipped while an input method is composing, where Enter picks a
//: candidate.
$("web-query").addEventListener("keydown", (e) => {
  if (e.isComposing) return;
  if (e.key === "Enter") {
    e.preventDefault();
    runWebSearch();
  } else if (e.key === "ArrowDown") {
    const first = document.querySelector(
      "#web-reader:not(.hidden) #web-reader-back, #web-results .web-result-title, #web-search-history:not(.hidden) .web-recent"
    );
    if (first) {
      e.preventDefault();
      first.focus();
    }
  } else if (e.key === "Escape" && webRequest) {
    e.preventDefault();
    e.stopPropagation();
    stopWebRequest();
  }
});
$("web-query").addEventListener("input", renderWebSearchHistory);
$("web-stop").addEventListener("click", stopWebRequest);
$("web-results").addEventListener("keydown", (e) => {
  if (e.key !== "ArrowUp" || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const first = $("web-results").querySelector(".web-result-title");
  if (e.target !== first) return;
  e.preventDefault();
  $("web-query").focus();
});
//: The recent rows walk with the arrows too; they are a short vertical list,
//: so this is the plain previous/next rather than ARROW_NAV_LISTS's geometry.
$("web-search-history").addEventListener("keydown", (e) => {
  if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
  const rows = [...$("web-search-history").querySelectorAll(".web-recent")];
  const at = rows.indexOf(e.target);
  if (at < 0) return;
  e.preventDefault();
  const next = rows[at + (e.key === "ArrowDown" ? 1 : -1)];
  (next || (e.key === "ArrowUp" ? $("web-query") : rows[at])).focus();
});
$("web-reader-back").addEventListener("click", closeWebReader);
//: Escape inside the reader goes back to the results, as a browser's Back
//: would; the find bar has its own Escape and stops it first.
$("web-reader").addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || e.defaultPrevented) return;
  e.preventDefault();
  e.stopPropagation();
  closeWebReader();
});
$("web-reader-save").addEventListener("click", async () => {
  await ensureModule("webClip");
  saveWebPageAsNote();
});
//: Same act as the result row's own "Save as bookmark", from the other side
//: of the panel: you often only decide a page is worth keeping after reading
//: it, and until now that decision had nowhere to go from here.
$("web-reader-bookmark").addEventListener("click", async () => {
  await ensureModule("webClip");
  readerBookmark();
});
$("web-reader-ask").addEventListener("click", () => {
  if (webReaderPage) askAboutPage(webReaderPage.url, webReaderPage.title);
});
$("web-reader-cite").addEventListener("click", () => {
  if (webReaderPage) citeWebPage(webReaderPage);
});
$("web-reader-copy").addEventListener("click", (e) => {
  if (webReaderPage) copyWebLink(webReaderPage.url, e.currentTarget);
});
$("web-reader-open").addEventListener("click", () => {
  if (webReaderPage) openWebPageExternally(webReaderPage.url);
});
$("web-reader-find").addEventListener("click", () => openGlobalFind({ scope: "web-reader" }));

// Reminders (Wave D). The dashboard's own wiring (dash-edit,
// dash-widgets-open/search) moved to dashboard.js along with the code it
// drives; this comment used to cover both.
//: Enter adds it, the way a one-line "add" field works everywhere; a
//: reminder had to be clicked in with the mouse after typing it. Skipped
//: while an input method is composing, where Enter picks a candidate.
//: Escape in the sentence box clears what was typed, and on an empty box leaves
//: it, the way a search field behaves (WORLD_CLASS row 32: it did nothing). On a
//: phone the form is a sheet whose own Escape closes it, so a press the sheet
//: has taken is left alone.
$("reminder-text")?.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !event.defaultPrevented && !event.isComposing) {
    const box = event.currentTarget;
    if (box.value) {
      event.preventDefault();
      event.stopPropagation();
      box.value = "";
    } else if (!document.querySelector(".sheet-overlay:not(.hidden)")) {
      box.blur();
    }
    return;
  }
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  $("reminder-add").click();
});
$("reminder-add").addEventListener("click", async () => {
  const ok = await addReminder($("reminder-text").value.trim(), $("reminder-due").value, null, {
    priority: $("reminder-priority").value,
    recurring: $("reminder-recurring").value,
  });
  if (ok) {
    $("reminder-text").value = "";
    $("reminder-priority").value = "normal";
    $("reminder-recurring").value = "none";
    // A fresh default for the next one, measured from now.
    setDue(defaultDueValue());
    // On a phone the form was a sheet over the list; the toast says it
    // landed and the list behind is where it now is.
    reminderComposeSheetClose?.();
  }
});

// **What a phone comes to Reminders for is the list** (INBOX 392,
// UI_MODERNISATION_PLAN Phase 11 item 12): what is due, and ticking it off.
// Measured at 390 before: the add form (the sentence box, the text, date,
// time, priority and repeat fields, the quick-set strip and a note) filled
// the whole first screen and the list began at y=836 of 844; at 768x1024 the
// form wrapped to 690px and the list began at y=752. Below 1100 (the width at
// which the rest of the app goes to one column) the form leaves the page and
// the dock's "New reminder", floated as the + by `FAB_IDS` below 600, opens
// it as a sheet: the form itself, moved in and put back on close, so its
// handlers, its quick-set strip and its clock are the ones the desktop uses.
// Above 1100 the button takes the caret to the form, which is on the page.
const REMINDER_SHEET = "(max-width: 1099.98px)";
let reminderComposeSheetClose = null;

function openReminderCompose() {
  const form = $("reminder-compose");
  if (!form) return;
  // The sentence box: its times need no model (UX-01).
  const field = () => $("reminder-magic") || $("reminder-text");
  if (!window.matchMedia(REMINDER_SHEET).matches || typeof openSheet !== "function") {
    field()?.focus();
    return;
  }
  if (reminderComposeSheetClose) return;
  const home = form.parentElement;
  const next = form.nextElementSibling;
  reminderComposeSheetClose = openSheet({
    label: "New reminder",
    name: "reminder-compose",
    returnFocus: $("reminders-new"),
    build: (card) => {
      card.classList.add("reminder-compose-card");
      card.appendChild(form);
    },
    onClose: () => {
      reminderComposeSheetClose = null;
      home.insertBefore(form, next && next.parentElement === home ? next : null);
    },
  });
  field()?.focus();
}

$("reminders-new")?.addEventListener("click", openReminderCompose);
$("reminder-clear-done").addEventListener("click", clearDoneReminders);
$("reminders-page-size").value = remindersPageSize;
$("reminders-page-size").addEventListener("change", (e) => {
  remindersPageSize = e.target.value;
  prefs.set("reminders-page-size", remindersPageSize);
  remindersDonePage = 1;
  loadReminders();
});
$("reminders-done-page-prev").addEventListener("click", () => {
  if (remindersDonePage <= 1) return;
  remindersDonePage -= 1;
  loadReminders();
});
$("reminders-done-page-next").addEventListener("click", () => {
  remindersDonePage += 1; // clamped back down inside paginateDoneReminders if this overshoots
  loadReminders();
});
for (const button of document.querySelectorAll("#reminder-filter button")) {
  button.addEventListener("click", () => {
    reminderFilter = button.dataset.filter;
    for (const b of document.querySelectorAll("#reminder-filter button")) {
      setActiveChoice(b, b === button);
    }
    remindersDonePage = 1; // a filter switch can change what's even in Done
    loadReminders();
  });
}
//: **One calendar** (TIMELINE_PLAN decision 19, INBOX 768): Calendar opens
//: the Timeline's calendar showing only reminders, where a reminder drags to
//: another day; the month grid this tab drew beside its list went.
$("reminder-view-calendar").addEventListener("click", () => {
  switchTab("timeline");
  timelineCalendarCall("timelineCalendarReminders");
});
$("reminder-magic-add").addEventListener("click", magicAddReminder);
$("reminder-magic").addEventListener("keydown", (e) => {
  // Now a textarea, so Enter has to be claimed explicitly to keep the
  // one-line-and-go path. Shift+Enter is the escape hatch for a real newline.
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    magicAddReminder();
  }
});
for (const button of document.querySelectorAll("#reminder-presets button")) {
  button.addEventListener("click", () => {
    setDue(toLocalInputValue(presetDate(button.dataset.preset).toISOString()));
    if (!$("reminder-text").value.trim()) $("reminder-text").focus();
  });
}
// Nudges: adjusting an existing time is far quicker than retyping one.
//: Each nudge fades the readout in (`.stepper-fresh`), so the change is seen
//: where it lands. Arrow keys on a focused stepper nudge too (DESIGN.md
//: "Stepper"): up or right later, down or left earlier, by 15 minutes, and
//: by a day with Shift.
//: **Undo the nudges** (the owner at release: "is it possible to cancel or
//: reset any adjustments made with the buttons in this reminders bar?").
//: The steppers keep a running total; a Reset button beside them appears
//: once it is non-zero and moves the time back by exactly that much. Typing
//: a date or time, or saving, starts the total again.
let dueNudgeNet = 0;
const dueNudgeReset = document.createElement("button");
dueNudgeReset.type = "button";
dueNudgeReset.className = "ghost small stepper-reset hidden";
dueNudgeReset.title = "Put the time back to where it was before the steppers";
setLabel(dueNudgeReset, "ph:arrow-counter-clockwise Reset");
dueNudgeReset.addEventListener("click", () => {
  if (dueNudgeNet) nudgeDue(-dueNudgeNet);
  dueNudgeNet = 0;
  dueNudgeReset.classList.add("hidden");
});
document.querySelector("#reminder-due-row .stepper-pair")?.after(dueNudgeReset);
function clearDueNudges() {
  dueNudgeNet = 0;
  dueNudgeReset.classList.add("hidden");
}
function nudgeDueShown(minutes) {
  nudgeDue(minutes);
  dueNudgeNet += minutes;
  dueNudgeReset.classList.toggle("hidden", dueNudgeNet === 0);
  const readout = $("reminder-due-readout");
  readout.classList.remove("stepper-fresh");
  void readout.offsetWidth;
  readout.classList.add("stepper-fresh");
}
$("reminder-due-nudge-down").addEventListener("click", () => nudgeDueShown(-15));
$("reminder-due-nudge-up").addEventListener("click", () => nudgeDueShown(15));
$("reminder-due-day-down").addEventListener("click", () => nudgeDueShown(-60 * 24));
$("reminder-due-day-up").addEventListener("click", () => nudgeDueShown(60 * 24));
for (const stepper of document.querySelectorAll("#reminder-due-row .stepper")) {
  stepper.addEventListener("keydown", (event) => {
    const sign = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1 }[event.key];
    if (!sign || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    nudgeDueShown(sign * (event.shiftKey ? 60 * 24 : 15));
  });
}
// The two visible fields drive the hidden value.
$("reminder-date").addEventListener("input", () => { clearDueNudges(); syncDueFromParts(); });
$("reminder-time").addEventListener("input", () => { clearDueNudges(); syncDueFromParts(); });
//: Adding the reminder ends the nudging (delegated: #reminder-add has its own handler).
$("reminder-add").parentElement.addEventListener("click", (event) => {
  if (event.target.closest("#reminder-add")) clearDueNudges();
});
// --- duplicate tidy-up -----------------------------------------------------------
// Finding is arithmetic and always available. Merging offers the AI when it's
// running and a plain join when it isn't: the join reads worse but cannot
// lose anything, which is the property that matters when tidying.
// --- autocorrect -----------------------------------------------------------------
//: autocorrect.js (lazy, Brief 94) is fetched on the first focus of a box it
//: serves; once in, it listens for itself.
document.addEventListener("focusin", function autocorrectDoor(event) {
  if (!event.target.closest?.("[data-autocorrect], .note-surface")) return;
  document.removeEventListener("focusin", autocorrectDoor);
  lazyScript("/js/autocorrect.js");
});
