// app-features.js: the rows "Tools and features" lists, as data. Moved out
// of dashboard.js (Brief bootdiet, 2026-10-10): about 195 lines of strings the
// first screen never reads. Lazy (app.js `LAZY_MODULES.appPalette`); the
// palette's bundle names it too, so `paletteFeatureRows` always finds it, and
// `openFeatures`, Quick access and `paletteAbouts` (settings-panes.js) wait
// for it. It is not a `LAZY_ENTRY_POINTS` stand-in on purpose: its callers read
// the array straight away, and a stand-in returns a promise.
// --- the "everything this app does" browser ----------------------------------
// Grouped, searchable, and every entry either jumps you there or explains
// itself: the fastest way to discover features you didn't know existed.
function featureCatalog() {
  const groups = [
    { group: "Audio", items: [
      { name: "New meeting", desc: "A meeting note: when, who, agenda, notes, decisions and action items.", reveal: "meeting-new" },
      { name: "Record a meeting", desc: "Record a meeting or lecture, saved as you go; transcribed when the Voice notes add-on is installed.", reveal: "meeting" },
      { name: "Voice note", desc: "A voice memo, kept in Library, Recordings.", reveal: "voice-note" },
      { name: "Dictation", desc: "Speak a note into Capture; the Voice notes add-on types it.", reveal: "notes-dictation" },
      { name: "Recordings", desc: "Every recording kept: play at 0.5 to 2x, the waveform, markers, trim.", reveal: "recordings" },
      { name: "Audio overview", desc: "Your notes, or a brief before a meeting, read aloud in a natural voice and saved as a recording; needs the Natural voice package.", reveal: "studio" },
      { name: "Live captions", desc: "Write what the microphone hears as you go, on this computer; run it again to stop and save a note.", act: () => toggleLiveCaptions() },
    ] },
    { group: "Capture & notes", items: [
      { name: "Capture a thought", desc: "Save anything; Atlas files it into a category and suggests tags.", reveal: "notes-capture" },
      { name: "Templates", desc: "Start a note from a prefilled shape (journal, recipe, meeting…).", reveal: "notes-template" },
      { name: "Improve writing", desc: "Proofread a note before saving, no model needed; rewrite or condense it with AI.", reveal: "notes-improve" },
      // The writing room is a sub-tab of Notes and was in the palette but in
      // no catalogue row, which is the shape this audit was for: a surface
      // that shipped, got a command, and never got its line in the list of
      // what the app can do.
      { name: "Writing room", desc: "Turn rough thoughts into a drafted note, section by section.", reveal: "writing-room" },
      { name: "Sketch pad", desc: "Draw something and save it as a note with a caption.", reveal: "sketch" },
      { name: "Attachments", desc: "Attach files and images to any note.", reveal: "notes-attach" },
      // Beside Attachments, which is the entry a person who has files in the
      // notebook is already reading. Asked for directly: "I want an easier and
      // more accessible way to access the ocr workspace as a proper and more
      // central feature." This browser and the command palette are the app's
      // two answers to that, and the reader had been in neither.
      { name: "OCR workspace", desc: "Open a PDF or picture beside the text read from it, page by page.", reveal: "page-reader" },
      //: The reader's own row in Settings, Packages (the target `extra-row`,
      //: which the OCR workspace's Manage and Install also go to).
      { name: "Reading engines", desc: "Tesseract and RapidOCR, which read the text in pictures, and whether each is installed.", reveal: "extra-row", arg: "ocr" },
      { name: "Threads", desc: "Continue a thought to build a train of related notes.", reveal: "notes-thread" },
      { name: "Note links", desc: "Type [[ to point one note at another; the link works both ways.", reveal: "notes-capture" },
      { name: "Checklists", desc: "Tick items off inside a note; the dashboard tracks what is left.", reveal: "notes-checklist" },
      { name: "Private notes", desc: "Encrypt a note so it is readable only while the app is unlocked.", reveal: "notes-private" },
      { name: "Pins & tags", desc: "Pin important notes and organise with tags.", reveal: "notes-favourite" },
      //: INBOX 691: the tidying tools, each findable here (the owner: "no use
      //: having them if the user doesnt know about them").
      { name: "Tidy", desc: "Reviews with no AI: weak links, stray tags, notes without a category, duplicates, old reminders.", reveal: "tidy" },
      { name: "Specific link reasons", desc: "Name what two linked notes share, a tag, a name or a week, instead of “similar in meaning”.", reveal: "tidy-links" },
      { name: "Find duplicates", desc: "Notes that say much the same thing, merged into one with nothing lost.", reveal: "tidy-duplicates" },
      { name: "Manage tags", desc: "Rename, merge or remove tags across every note.", reveal: "tag-manager" },
      { name: "Filings to check", desc: "Notes Atlas filed with little certainty, each with Accept, Refile and Split.", reveal: "notes-review" },
      { name: "Bin", desc: "Deleted notes, documents, reminders and OCR readings are recoverable until the bin is cleared.", reveal: "recycle-bin" },
    ]},
    { group: "Ask & chat", items: [
      { name: "Ask your notebook", desc: "Questions answered strictly from your own notes.", reveal: "notes-ask" },
      { name: "Chat", desc: "A full conversation with your notebook, saved and resumable.", reveal: "chat-input" },
      { name: "Attach to a message", desc: "Point a message at notes, documents, files, images or a map you already have.", reveal: "chat-attach" },
      { name: "Saved conversations", desc: "Every chat is kept, searchable, and can be picked up later.", reveal: "chat-conversations" },
      { name: "Personas", desc: "Change the voice Atlas writes in: its own, Coach, Analyst, or yours.", reveal: "settings:personas" },
      { name: "Run a skill", desc: "One-click requests like “Summarise my week”; can act on your notes.", reveal: "settings:skills" },
      { name: "Agent mode", desc: "Let Atlas use its tools, search your notes, open a page, create, tag, link and organise.", reveal: "chat-agent-mode" },
      // The popup agent has the same capability as Chat's agent mode and is
      // reachable from every tab, which is exactly why it needs a row: a chord
      // nobody has been told about is not a feature anyone has.
      { name: "Ask from anywhere", desc: "Ctrl+Shift+A opens Atlas over whatever you are working on.", reveal: "agent-palette" },
      { name: "What it remembers", desc: "See and edit the facts Atlas has kept about you.", reveal: "settings:memory" },
      { name: "Web search", desc: "Opt-in, off by default: one of the two features that can go online.", reveal: "chat-web-search" },
      { name: "Export chat", desc: "Download a conversation as Markdown.", reveal: "chat-export" },
      { name: "Search relevance", desc: "How strict semantic search is about what counts as a real match.", reveal: "set-search-relevance" },
      //: Chat's answers that need no model (ai/utilities.py), named nowhere in
      //: either list, so "calculator" and "convert" found nothing (Brief 90).
      { name: "Quick answers", desc: "Sums, percentages, unit and currency conversions, dates and word counts, answered in Chat with no model.", reveal: "chat-answers" },
    ]},
    // **Documents had no rows at all**, and the editor is one of the largest
    // surfaces in the app: blocks, an outline, breadcrumbs, a spelling and
    // style check with its own dictionary, tables, properties, block links and
    // embeds, version history. Every row below opens the control it names on
    // the newest document (`revealDocument`, app.js), and with no document at
    // all it rings New document instead: a document-scoped action with no
    // document open is a row that would otherwise do nothing.
    { group: "Documents", items: [
      { name: "New document", desc: "Long-form writing in Markdown, with live formatting as you type.", reveal: "doc-new" },
      { name: "Document templates", desc: "Start from a prefilled document instead of a blank page.", reveal: "doc-templates" },
      { name: "Blocks and the “/” menu", desc: "Type / for headings, quotes, callouts, tables, columns and embeds.", reveal: "doc-insert" },
      { name: "Outline", desc: "Every heading as a list you can jump around by, marking where you are.", reveal: "doc-outline" },
      { name: "Breadcrumbs", desc: "The heading trail above the text says where in the document the caret is.", reveal: "doc-crumbs" },
      { name: "Find and replace", desc: "Search the document, step through matches, replace one or all.", reveal: "doc-find" },
      { name: "Focus mode", desc: "Hide everything but the text you are writing.", reveal: "doc-focus" },
      { name: "Document properties", desc: "Title, tags and your own fields, stored as front matter at the top.", reveal: "doc-properties" },
      { name: "Tables", desc: "Build and edit Markdown tables without counting pipes.", reveal: "doc-tables" },
      { name: "Block links and embeds", desc: "Link or quote a single paragraph from anywhere, by its own short id.", reveal: "doc-insert" },
      { name: "Backlinks", desc: "What points at this document, from notes, maps, chats and other documents.", reveal: "doc-connections" },
      { name: "Spelling and style", desc: "Findings in the margin for spelling, repeated words and clumsy phrasing.", reveal: "doc-prose" },
      { name: "Your dictionary", desc: "Words you have taught it, so they stop being flagged everywhere.", reveal: "doc-dictionary" },
      { name: "Word goal", desc: "Set a target and watch the count, reading time and structure as you write.", reveal: "doc-word-goal" },
      { name: "Version history", desc: "Earlier saves of a document, with what changed, restorable.", reveal: "doc-history" },
      { name: "AI edit", desc: "Rewrite, shorten, translate or review a passage, with the change reviewable before it lands.", reveal: "doc-ai" },
      { name: "Export a document", desc: "Download it as Markdown, or print it to PDF with its formatting kept.", reveal: "doc-export" },
    ]},
    // Boards and maps were in the same position as Documents: built, reached
    // from the Library's own sub-tab, and mentioned nowhere in the list of
    // what the app does. A map is a board, so the two
    // share a group rather than pretending to be separate canvases.
    { group: "Boards, maps & drawing", items: [
      { name: "New board", desc: "A whiteboard of cards, drawings, images and links you arrange yourself.", reveal: "board-new" },
      { name: "Mind maps", desc: "Topics branching from one central idea, each topic a real note.", reveal: "map-create" },
      { name: "Grow a map by keyboard", desc: "Tab adds a branch off the selected topic, Enter one beside it.", reveal: "map-keyboard" },
      { name: "Map templates", desc: "Start a map from a shape: a decision, a project, a subject to revise.", reveal: "map-templates" },
      { name: "Arrange as mind map", desc: "Re-tidy a sprawling board into a readable tree in one move.", reveal: "board-arrange" },
      { name: "Board overview", desc: "A miniature of the whole board, to see where you are and jump.", reveal: "board-overview" },
      { name: "Find a card", desc: "Search the board you are on and step through the matches.", reveal: "board-find" },
      { name: "The tool rail", desc: "Select, draw, shapes, text, links and images, grouped by what they do.", reveal: "board-tools" },
      { name: "Context bar", desc: "The properties of whatever is selected, above the selection itself.", reveal: "board-context" },
      { name: "Export a board", desc: "Save the board, or just what you selected, as an image.", reveal: "board-export" },
    ]},
    // The Library is the app's filing cabinet and had no rows either, which
    // left six sub-tabs of real surfaces undiscoverable from here.
    { group: "Library", items: [
      { name: "Everything in one place", desc: "Notes, chats, documents, files and boards in one list you can filter.", tab: "library" },
      { name: "Your documents", desc: "Every document, with its size, when you last touched it, and a preview.", reveal: "library-docs" },
      { name: "Images", desc: "Every picture in the notebook, with its caption and where it is used.", reveal: "library-images" },
      { name: "Files", desc: "PDFs and other files, with a first-page preview and what has been read from them.", reveal: "library-files" },
      { name: "Bookmarks", desc: "Bookmarks, grouped, with the page's own title and description.", reveal: "library-links" },
      { name: "Skills", desc: "The skills you can run, what each one does, and how to add your own.", reveal: "library-skills" },
      { name: "Contents", desc: "A table of contents for the whole notebook, by category and tag.", reveal: "library-contents" },
      { name: "Where a file is used", desc: "Every file says which notes, documents and boards reference it.", reveal: "library-files" },
    ]},
    { group: "Map & discovery", items: [
      { name: "Graph view", desc: "Your notes as a network of links, threads and similarity.", tab: "graph" },
      { name: "Edit on the map", desc: "Click any node to edit its content and tags in place.", reveal: "graph-edit" },
      { name: "Physics controls", desc: "Gravity, Spread and Link force sliders reshape the layout; Reshuffle layout deals a new one.", reveal: "graph-physics" },
      { name: "Suggestions", desc: "Links to add, disagreements, names to merge and link types, decided one by one.", reveal: "suggestions" },
      { name: "Suggested links", desc: "Atlas proposes connections between related notes.", reveal: "graph-suggest" },
      { name: "People and things", desc: "Everyone and everything your notes name, each with its own page.", reveal: "entities" },
      { name: "Kinds of link", desc: "Say what a link is (Part of, Cites, your own), with its name from the other end.", reveal: "relation-types" },
      { name: "Note types", desc: "Meeting, Book, your own: a kind of note with its fields, kept at the top of each note.", reveal: "note-types" },
      { name: "Timeline", desc: "Everything you have made, in order, as a grid or a branching line.", tab: "timeline" },
      { name: "Zoom the timeline", desc: "By day, week, month or year, with a jump back to today.", reveal: "timeline-zoom" },
      { name: "Timeline bands", desc: "Group the timeline by category, tag or kind of thing.", reveal: "timeline-bands" },
      { name: "On this day", desc: "Notes you captured on this date in past months resurface.", reveal: "widget-on-this-day" },
      { name: "Related notes", desc: "See notes that mean something similar to the one you're reading.", reveal: "notes-related" },
      { name: "Find on this screen", desc: "Ctrl+F searches whatever tab you are looking at.", reveal: "global-find" },
    ]},
    { group: "Plan & focus", items: [
      { name: "Reminders", desc: "Due dates with priority, repeats, snooze and notifications.", tab: "reminders" },
      { name: "Magic add", desc: "Type “call mum tomorrow evening” and Atlas schedules it.", reveal: "reminder-magic" },
      { name: "Focus timer", desc: "A ring timer with 5 to 60 minute presets or any length from 1 to 180, optional breaks, a chime at the end and today's focused minutes.", reveal: "widget-focus" },
      { name: "Digest", desc: "Your day from the notes with no AI, and an AI recap of the week on request.", reveal: "widget-digest" },
      { name: "Tensions", desc: "Find where your notes contradict each other, a decision reversed, a date that moved.", reveal: "tensions" },
      // Resurfacing had shipped on two surfaces (the sort and the widget) and
      // was named on neither list.
      { name: "Forgotten first", desc: "Sort your notes by what is slipping out of reach: old, unlinked, unopened.", reveal: "notes-forgotten" },
      { name: "Rediscover", desc: "Three faded notes a day, with the reason each one surfaced.", reveal: "widget-rediscover" },
      { name: "Loose ends", desc: "How much of the notebook is connected, and the oldest notes that are not.", reveal: "widget-orphans" },
      { name: "Unfinished", desc: "Notes with checklist items still waiting to be ticked.", reveal: "widget-unfinished" },
      { name: "Writing pace", desc: "How many words you have written each day this fortnight.", reveal: "widget-pace" },
      { name: "Activity heatmap", desc: "A year of capture activity at a glance.", reveal: "widget-heatmap" },
      { name: "The manual", desc: "Every help topic on one page, to search or print.", reveal: "manual" },
      { name: "Statistics", desc: "Your notebook, reminders and usage, counted, with this week against last.", reveal: "statistics" },
      { name: "This week", desc: "Notes made, words written and reminders done, against last week.", reveal: "widget-week" },
      { name: "Streaks", desc: "How many days in a row you've captured something.", reveal: "widget-streak" },
    ]},
    { group: "Make it yours", items: [
      { name: "Theme", desc: "Light, dark, or follow your system.", reveal: "set-theme" },
      { name: "Accent colour", desc: "Presets or any custom colour you like.", reveal: "set-accent" },
      { name: "Typography & density", desc: "Font, text size, and how roomy the layout feels.", reveal: "set-typography" },
      { name: "Corner rounding & glass", desc: "Tune the shape and blur of every surface.", reveal: "set-radius" },
      { name: "Animated background", desc: "Aurora, constellations, blobs or particles behind the app.", reveal: "set-background" },
      { name: "A companion on screen", desc: "A small character that keeps its own place and reacts to what you do.", reveal: "set-companion" },
      { name: "Your look", desc: "Shuffle the face drawn from your name, or choose its parts yourself.", reveal: "settings:preferences" },
      { name: "Accessibility", desc: "High-contrast mode and the Motion choice.", reveal: "set-contrast" },
      { name: "Custom CSS", desc: "For tinkerers: your own style overrides.", reveal: "set-custom-css" },
      { name: "Zoom the whole app", desc: "Ctrl with plus or minus scales every surface, and Ctrl+0 puts it back.", act: () => nudgeZoom(1) },
      { name: "Tray", desc: "Hold a few cards (notes, documents, boards, pictures) while you change page, then paste or drag them out.", act: () => $("status-tray")?.click() },
      { name: "Your own order", desc: "Drag a card, or press Alt+Up or Alt+Down on it, to set Custom order in Notes and the Library; Ctrl+C copies a card.", reveal: "notes-order" },
      { name: "Dashboard layout", desc: "Show, hide, reorder and widen widgets.", reveal: "dash-layout" },
      // Workspaces are the top-left control every tab is filtered by, and
      // nothing in either list said they existed.
      { name: "Workspaces", desc: "Keep work, study and home in separate notebooks that share one app.", reveal: "workspace-new" },
      { name: "Note templates", desc: "Edit the shapes a new note can start from, or write your own.", reveal: "settings:templates" },
    ]},
    { group: "Data & control", items: [
      { name: "Export", desc: "Download everything as JSON, Markdown or CSV.", reveal: "set-export" },
      { name: "Import markdown", desc: "Bring in notes from an Obsidian-style vault.", reveal: "set-import-md" },
      { name: "Backups", desc: "Snapshot your notebook and restore it later.", reveal: "set-backups" },
      { name: "Sync between computers", desc: "Over the home network or through a folder you choose; a change made on both keeps the other words in History.", reveal: "sync-group" },
      { name: "Models", desc: "Choose the chat, utility, vision and reading models, and download more.", reveal: "settings:models" },
      { name: "Search and index", desc: "The search engine, the index it builds, and how strict a match must be.", reveal: "settings:searchindex" },
      { name: "AI tool permissions", desc: "Decide exactly what Atlas is allowed to do.", reveal: "settings:tools" },
      { name: "Background tasks", desc: "What the app is doing in the background, and what it has finished.", reveal: "settings:tasks" },
      { name: "Packages", desc: "The optional extras (OCR, speech, vision) and whether they are installed.", reveal: "settings:extras" },
      { name: "Account & security", desc: "Change your password, and what happens when the app locks.", reveal: "settings:account" },
      { name: "Where your data went", desc: "Every connection the app made, and whether anything left this computer.", reveal: "settings:privacy" },
      { name: "Logs", desc: "What the app and the models have been doing, in plain text.", reveal: "settings:logs" },
      { name: "Lock", desc: "Password-protect the app on shared devices.", act: () => lockNow() },
      { name: "Command palette", desc: "Ctrl/⌘-K to run a command or go to a place; its last row searches everything.", reveal: "palette" },
      //: Brief 90: the search over everything had no line here, so Ctrl+K
      //: "find anything" found nothing (deepen72b.js).
      { name: "Find anything", desc: "One search over notes, documents, boards, files, bookmarks, reminders and chats, with filters.", reveal: "finder" },
      { name: "Keyboard shortcuts", desc: "Press ? any time for the full list.", reveal: "shortcuts" },
      { name: "Help", desc: "How the parts of the app fit together, in the app itself.", reveal: "settings:help" },
      { name: "Updates", desc: "Which version you are on, and whether a newer one is out.", reveal: "set-updates" },
      { name: "Welcome tour", desc: "Replay the introduction to Tessellate.", reveal: "onboarding" },
    ]},
    //: Each row declares where it goes (`tab`, `reveal` or `act`) and
    //: `catalogueRun` (settings-panes.js) makes the `run` the dialog calls, so every row
    //: lands on what it names (tests/test_catalogue_reveal.py).
  ];
  //: The popup tools (settings-panes.js `POPUP_TOOLS`) join their groups from
  //: the registry, so a new tool is listed here by adding one entry there.
  for (const tool of POPUP_TOOLS) {
    groups.find((group) => group.group === tool.group)?.items.push({ name: tool.name, desc: `${tool.about} Keys: ${tool.keys}.`, act: tool.open });
  }
  return groups.map((group) => ({ ...group, items: group.items.map(catalogueRun) }));
}

//: **Every palette row is in the catalogue** (audit 1031 Z3): "Count words",
//: "Translate this", "Private chat", "Open the bin" and about fifty more were
//: in the palette and not in "Tools and features", which is the answer to
//: "where is". The rows the hand-written groups above have no line for (by
//: name, or by the place they reveal) join one derived group, so a command
//: added to `paletteCommands` is listed with no second edit.
function featureCommandRows(groups) {
  const names = new Set();
  const places = new Map();
  for (const group of groups) {
    for (const item of group.items) {
      names.add(item.name.toLowerCase());
      if (item.reveal) places.set(`${item.reveal}:${item.arg ?? ""}`, item);
    }
  }
  const items = [];
  //: The open document's, map's and board's own commands carry a `group`; the rows
  //: that are always there do not.
  for (const row of paletteCommands().filter((r) => !r.group)) {
    const name = richPickerSplitLabel(row.label).text;
    const place = row.reveal ? `${row.reveal}:${row.arg ?? ""}` : "";
    if (names.has(name.toLowerCase())) continue;
    //: A row the list already has under another name is found by the
    //: palette's words too ("Dictate a note" finds Dictation): `also` is
    //: read by the search and not drawn.
    const held = places.get(place);
    if (held) {
      held.also = `${held.also || ""} ${name} ${row.keywords || ""}`;
      continue;
    }
    names.add(name.toLowerCase());
    items.push({ name, desc: row.about || "A command in the palette.", run: row.run });
  }
  return { group: "More commands", items };
}

//: The popup tools (settings-panes.js `POPUP_TOOLS`): Calculator and equations over the box it is handed (`{target}`; its Insert buttons write there), else on its own. The box is passed, never remembered: a default of the palette's last box sent the shortcuts dialog's and the Guide's opens to a field from an earlier palette (INBOX 1530 g).
async function popupToolMaths(caught = {}) {
  const target = popupToolMaths.box(caught.target);
  await ensureModule("replyKit");
  openCalculator("", "work", { target });
}

//: The box the palette was opened over when it takes text, focused, else null (the Insert of the calculator and the pick of the picker then go nowhere but the clipboard). By id first: `editorSurfaceKind` answers null until the Library bundle has loaded, so a palette opened over the Chat box early dropped its box and the dialog opened with no Insert.
popupToolMaths.box = (target) => {
  const fit = target?.isConnected && (target.id === "question" || target.id in EDITOR_SURFACES || (typeof editorSurfaceKind === "function" && editorSurfaceKind(target)));
  if (fit) target.focus();
  return fit ? target : null;
};

//: The picker's tab for a palette row (INBOX 1544).
popupToolMaths.glyph = (mode) => editorPickGlyph(popupToolMaths.box(paletteCaughtNow().target), null, mode);

function renderToolShortcutList(list) {
  if (!list) return;
  list.textContent = "";
  for (const tool of POPUP_TOOLS) {
    const li = document.createElement("li");
    const keys = document.createElement("span");
    keys.className = "shortcut-keys";
    for (const chord of tool.keys.split(" or ")) {
      const kbd = document.createElement("kbd");
      kbd.textContent = chord.startsWith("/") ? chord : (typeof chordLabel === "function" ? chordLabel(chord) : chord);
      keys.appendChild(kbd);
    }
    const words = document.createElement("span");
    words.textContent = tool.where;
    li.append(keys, words);
    list.appendChild(li);
  }
}

//: **The palette's registry, and the Quick access row that reads it** (boot diet
//: 3, 2026-11-01): `paletteCommands` and the dashboard's Quick access draw were
//: 5 KB and 3 KB gzipped of boot script that only a dashboard draw, the palette
//: and the lists of what the app can do read. `renderQuickLinks` is a
//: `LAZY_ENTRY_POINTS` stand-in (bundle `featureRows`, nobody reads its return),
//: so the dashboard draws the tiles once this file is in, as it did before when
//: it waited for `featureCatalog`.
function paletteCommands() {
  //: **The documents editor's own commands, at the top, while one is open**
  //: (DOCUMENTS_PLAN Phase 4 item 4). The plan named `Ctrl+K` for an editor
  //: palette of its own, which is the chord this one already has: two
  //: palettes on one key is the collision the agent palette's comment records
  //: being caught twice. So the editor contributes a group here instead, and
  //: `docPaletteCommands` (documents.js) returns nothing at all unless the
  //: Documents tab is showing with a document in it. Guarded by `typeof`
  //: because that file is in the Library's lazy bundle and the palette opens
  //: from every tab, including before it has ever been fetched.
  const editor = typeof docPaletteCommands === "function" ? docPaletteCommands() : [];
  //: And an open map's (whiteboard-map.js, lazy for the same reason).
  if (typeof mapPaletteCommands === "function") editor.push(...mapPaletteCommands());
  //: The open board's commands, the same way (FEAT-11, whiteboard-commands.js):
  //: nothing unless a board is on screen, which needs the bundle in.
  const board = typeof wbPaletteCommands === "function" ? wbPaletteCommands() : [];
  //: Every row below declares where it goes (tests/test_catalogue_reveal.py)
  //: and `catalogueRun` makes its `run`; the editor's rows are commands on
  //: the document already open, so they keep their own.
  return [
    ...editor,
    ...board,
    { label: "ph:clipboard Go to Dashboard", tab: "dashboard", about: "Today at a glance: recent notes, reminders and widgets." },
    { label: "ph:clipboard-text Copy diagnostics", about: "Lag and errors as text. No note text.", act: () => ensureModule("diagnostics").then(() => diagCopy()) },
    { label: "ph:magnifying-glass-plus Zoom in", about: "Make everything in the app a step larger.", act: () => nudgeZoom(1) },
    { label: "ph:magnifying-glass-minus Zoom out", about: "Make everything in the app a step smaller.", act: () => nudgeZoom(-1) },
    { label: "ph:arrow-counter-clockwise Reset zoom to 100%", about: "Back to the size the app was drawn at.", act: () => { setZoom(100); hud("Zoom 100%"); } },
    { label: "ph:note-pencil Go to Notes", tab: "notes", about: "Every note, with capture, filters and the reading pane." },
    { label: "ph:chat-circle Go to Chat", tab: "chat", about: "A conversation with your notebook, saved as you go." },
    { label: "ph:graph Go to Graph", tab: "graph", about: "Your notes as a map of what links to what." },
    { label: "ph:file-text Go to Documents", tab: "documents", about: "Long-form writing, with blocks, an outline and history." },
    //: Two tabs the palette could not reach. The Library holds six sub-tabs of
    //: real surfaces (documents, images, files, links, skills, contents) and
    //: the Timeline is a top-level tab, and neither had a command: a jump list
    //: missing two of the seven places you can be is the one kind of gap that
    //: teaches people not to use it.
    { label: "ph:books Go to Library", tab: "library", about: "Documents, images, files, links, skills and boards." },
    { label: "ph:clock-counter-clockwise Go to Timeline", tab: "timeline", about: "Everything you have written, by the day it happened." },
    { label: "ph:alarm Go to Reminders", tab: "reminders", about: "What is due, and what you asked to be told about." },
    // Features reachable *only* from inside one surface are exactly the ones a
    // palette has to carry, or they are found by accident or not at all.
    // The inbox is a sheet; the board's overview and find bar live on a
    // board you have to be on already.
    { label: "ph:tray Suggestions: links, disagreements, names and link types", reveal: "suggestions" },
    { label: "ph:users People and things in my notes", reveal: "entities" },
    { label: "ph:tag Kinds of link: Part of, Cites and your own", reveal: "relation-types" },
    { label: "ph:list-bullets Note types: Meeting, Book and their fields", reveal: "note-types" },
    { label: "ph:scales Tensions: find where I disagreed with myself", reveal: "tensions" },
    //: Atlas is a surface with no tab of its own, which is exactly what a
    //: command palette is for (INBOX 224).
    //: The row wears Atlas's own face rather than a glyph (the owner: "find
    //: anything search" should have the avatar too), see `renderPalette`.
    { label: "Ask Atlas about the app", mark: "atlas", reveal: "atlas-help", chord: "askAtlas" },
    //: A companion that went somewhere it cannot be reached (INBOX 426 k).
    { label: "ph:arrow-counter-clockwise Call the companion back", about: "Bring the companion back to its corner of the window.", act: () => nameMarkBuddyCallBack() },
    //: Both did nothing at all unless a board was already on screen: the
    //: palette opens from every tab, and the two functions act on the board
    //: that is open. The reveal opens one first (the newest), and with no
    //: board at all rings the button that makes one.
    { label: "ph:map-trifold Board overview", reveal: "board-overview", about: "The whole board at once, to jump to any part of it." },
    { label: "ph:magnifying-glass Find on this board", reveal: "board-find", about: "Search the open board's cards, text and labels; Ctrl+H replaces." },
    //: Capture is a sub-tab of Notes, and focusing its box while another
    //: sub-tab was showing did nothing (the dashboard's own New note says so).
    { label: "ph:pencil-simple New note", reveal: "notes-capture", chord: "newNote" },
    //: Ctrl+D had no palette row (tests/test_consistency_contract.py: every
    //: chord is in the palette or says why it cannot be).
    { label: "ph:calendar-check Open today's note", reveal: "todays-note", chord: "todaysNote", about: "Today's page, or a new one titled with the day." },
    { label: "ph:lightning Quick note", about: "A note saved without leaving this page.", chord: "quickNote", act: () => openQuickNote() },
    { label: "ph:clipboard-text Paste as a note", about: "What you copied, saved as a new note.", chord: "pasteNote", act: () => pasteClipboardAsNote() },
    { label: "ph:file-text New document", reveal: "doc-new", chord: "newDocument" },
    { label: "ph:flow-arrow New diagram", about: "A flowchart, sequence, mind map or timeline built from blocks.", act: () => lazyScript("/js/documents-mermaid.js").then(() => diagramModel.door({ doc: true })) },
    { label: "ph:code New code file", act: () => ensureModule("library").then(() => LIBRARY_CREATE_BY_KIND.code.run()) },
    { label: "ph:sparkle Write a note from rough thoughts", reveal: "writing-room" },
    { label: "ph:sparkle New chat", reveal: "chat-new", chord: "newChat" },
    { label: "ph:ghost Private chat", reveal: "chat-private", about: "A chat that is not saved or remembered." },
    // The popup agent (Ctrl+Shift+A) has real capability, it's the same
    // tool-calling agent as Chat's agent mode, just reachable from anywhere
    //, but was reachable only by already knowing that chord. This palette
    // is the app's own "what can I do here" list; it belongs in it.
    { label: "ph:strategy Ask the agent anything", reveal: "agent-palette", chord: "askAgent" },
    { label: "ph:palette New sketch", reveal: "sketch", chord: "quickSketch" },
    //: A command, not a search (INBOX 666: the palette is commands and
    //: places; finding a meeting is Find anything's). INBOX 644: there was
    //: no way to start a meeting note by name anywhere in the app.
    { label: "ph:users-three New meeting", reveal: "meeting-new", about: "Agenda, notes, decisions and action items." },
    {
      // Reachable from anywhere, which is the point. Asked for directly: "I
      // would also like the meeting notes popup to be expanded as a proper
      // feature with more capabilities and expansion which is also accessible
      // throughout the app, not just from the dashboard." A recording is
      // started the moment a meeting starts, and "go to the Dashboard first"
      // is exactly the friction that means it does not get started at all.
      label: "ph:microphone Record a meeting or lecture",
      reveal: "meeting",
      chord: "recordMeeting",
    },
    { label: "ph:microphone-stage Voice note", reveal: "voice-note" },
    { label: "ph:microphone Dictate a note", reveal: "notes-dictation" },
    { label: "ph:waveform Recordings", reveal: "recordings" },
    { label: "ph:arrows-clockwise Sync between computers", reveal: "sync-group", keywords: "sync folder usb syncthing two computers merge devices pair network", about: "Keep two computers level, over the home network or through a folder." },
    { label: "ph:waveform Make an audio overview", reveal: "studio", about: "Your notes read aloud in a natural voice, saved as a recording." },
    {
      // The same ask about the page reader, in the same words: "I want an
      // easier and more accessible way to access the ocr workspace as a proper
      // and more central feature." It had four doors and every one of them
      // started from a file you had already found, which is no answer to "I
      // want to read something". `openPageReader` (library.js) opens it on what
      // you were last reading, else your newest readable file; the decision and
      // what was deliberately left out is in UI_MODERNISATION_PLAN.md, "how
      // the page reader is reached".
      //: "OCR" in the words (the owner, 2026-10-10: searching "ocr" in the
      //: palette, Find anything and Quick access's list found nothing).
      label: "ph:scan OCR workspace: read a document or image",
      reveal: "page-reader",
    },
    {
      // Asked for directly: "add creating a new board to the command
      // palette and tools and features as well", the only way in before
      // this was the Add button inside the whiteboard's own board-picker
      // panel, unreachable without already being on that tab.
      label: "ph:folders New whiteboard board",
      reveal: "board-create",
      about: "A blank board for cards, drawings, images and links.",
    },
    {
      //: The Library's New, Mind map, from anywhere: Untitled map N, its
      //: root in edit (MINDMAP_PLAN 15, rows 1 and 2).
      label: "ph:tree-structure New mind map",
      reveal: "map-create",
    },
    {
      //: The Library's sub-tabs, as commands. These are the two halves of the
      //: file gallery, and getting to either meant three clicks through a tab
      //: and a sub-tab strip that scrolls on a narrow window.
      label: "ph:image Browse images",
      reveal: "library-images",
    },
    {
      label: "ph:paperclip Browse files",
      reveal: "library-files",
    },
    {
      label: "ph:link Browse links",
      reveal: "library-links",
    },
    {
      //: The whole list of what the app can do, from the list of what the app
      //: can do: the features browser was reachable from a dashboard button
      //: and nowhere else, and it is the answer to "what was that thing
      //: called", which is exactly the question the palette is opened with.
      label: "ph:compass Tools and features",
      reveal: "features",
      about: "Everything the app can do, a line each, and where it is.",
    },
    {
      //: Resurfacing shipped as a sort and a widget and was named in neither
      //: list. The sort is the half a person can act on: it re-ranks the notes
      //: they are already looking at by what is slipping out of reach.
      label: "ph:hourglass Show forgotten notes first",
      reveal: "notes-forgotten",
    },
    {
      //: The word list the document spelling check reads, which is otherwise
      //: only reachable from inside a suggestion popup on a flagged word, so
      //: "what have I taught it" had no door at all.
      label: "ph:book-bookmark Words you have taught it",
      reveal: "doc-dictionary",
    },
    {
      //: Ctrl+F is bound globally (`openGlobalFind`) and the palette is where
      //: a person looks for a key they have forgotten.
      label: "ph:magnifying-glass Find on this screen",
      reveal: "global-find",
      chord: "find",
    },
    {
      //: Workspaces filter every tab in the app from one control in the top
      //: left, and nothing in the palette mentioned them.
      label: "ph:folders New workspace",
      reveal: "workspace-new",
    },
    // Filters as commands: the fastest route to "the notes I mean" without
    // remembering the operator syntax.
    ...[
      ["ph:star Show favourites", "is:favourite"],
      ["ph:tag Show untagged notes", "is:untagged"],
      ["ph:lock Show private notes", "is:private"],
      ["ph:link Show linked notes", "is:linked"],
      ["ph:check-square Show filings to check", "is:review"],
    ].map(([label, query]) => ({
      label,
      about: `The notes list, filtered to ${query}.`,
      act: () => showNotesFilter(query),
    })),
    //: UX-08: places Ctrl+K could not reach (tests/test_palette_synonyms.py).
    { label: "ph:trash Open the bin", reveal: "library-bin", keywords: "bin trash deleted binned restore recover", about: "Everything you threw away, in the Library, ready to restore." },
    { label: "ph:question Questions your notes ask", reveal: "notes-questions", keywords: "questions open questions", about: "The open questions found in your notes." },
    { label: "ph:chat-text Ask your notes", reveal: "notes-ask", keywords: "ask question answer search my notes", about: "An answer quoted from your own notes, with or without a model." },
    //: The Guide had no row: "guide" found the tour (CHAT_PLAN 9 row 3).
    { label: "ph:question Ask the Guide", reveal: "atlas-help", keywords: "guide help how do i how does where is question", about: "Ask how anything in the app works; it answers from the app's own help." },
    //: The tour's third door (the e2e flow pass): the Dashboard's first-run
    //: tile and Settings, Help were the only two (tests/test_palette_synonyms.py).
    { label: "ph:compass Take the guided tour", keywords: "tour walkthrough guide how to start show me around", about: "A short walk round the app, pointing at the real controls.", act: () => openTour("basics") },
    //: INBOX 1304: Get started, hidden or done, comes back from the palette too.
    { label: "ph:list-checks Show first steps", keywords: "unhide get started", act: () => lazyScript("/js/first-run.js").then(() => getStartedShow()) },
    { label: "ph:arrow-u-up-left Undo", keywords: "undo take back revert", about: "Undo the last change, wherever it was made.", act: () => performUndo() },
    { label: "ph:arrow-u-up-right Redo", keywords: "redo", about: "Do again what Undo took back.", act: () => performRedo() },
    {
      label: "ph:magnifying-glass What can I type in the filter?",
      reveal: "notes-filter-help",
      about: "The words the notes filter understands, like is:favourite.",
    },
    { label: "ph:gear Settings, Models", reveal: "settings:models", about: "Which local model answers, and where it runs." },
    { label: "ph:mask-happy Settings, Personas", reveal: "settings:personas" },
    { label: "ph:lightning Settings, Skills", reveal: "settings:skills" },
    { label: "ph:toolbox Settings, Tools it can use", reveal: "settings:tools" },
    { label: "ph:palette Settings, Appearance", reveal: "settings:appearance", keywords: "theme colour color accent font text size look", about: "The look, the accent colour, the glass and the text size." },
    { label: "ph:user-circle Settings, Profile", reveal: "settings:preferences", about: "Your name, and what the app knows to call you." },
    { label: "ph:sliders Settings, General", reveal: "settings:general", keywords: "recycle bin auto-clear chat history notifications", chord: "settings" },
    { label: "ph:floppy-disk Settings, Import & export", reveal: "settings:data", keywords: "backup backups restore import export data", about: "Bring notes in, take everything out, and back up." },
    { label: "ph:brain Settings, What it remembers", reveal: "settings:memory" },
    { label: "ph:note-blank Settings, Templates", reveal: "settings:templates", about: "The shapes a new note or document can start from." },
    { label: "ph:shield-check Settings, Account & security", reveal: "settings:account", about: "The password, the lock and when it asks for it." },
    { label: "ph:globe-hemisphere-west Settings, Privacy", reveal: "settings:privacy", about: "The two things that can go online, both off by default." },
    { label: "ph:list-checks Settings, Background tasks", reveal: "settings:tasks", about: "What the app is working on while you write." },
    { label: "ph:heartbeat Health", reveal: "settings:about", keywords: "integrity check last backup last error data folder size status storage disk space files", about: "How the notebook is: last backup, last error, what is running, size, integrity." },
    { label: "ph:chart-bar Statistics", quick: "statistics", keywords: "stats numbers counts usage week review growth", about: "Your notebook, reminders and usage, counted, with this week against last.", act: () => openStatistics() },
    { label: "ph:book-open-text Open the manual", reveal: "manual" },
    //: The small tools (Brief 89, UI_MODERNISATION utilities rows 2 to 4):
    //: "timer 10 minutes" and "insert template ..." also build their own rows
    //: from the words (`utilityPaletteRows`, app-palette.js).
    ...POPUP_TOOLS.map((t) => ({ label: `${t.icon} ${t.name}`, keywords: t.keywords, about: t.about, keys: t.keys, quick: `tool-${t.id}`, act: () => t.open(paletteCaughtNow().target) })),
    //: The picker's three tabs, each its own row (INBOX 1544): a pick goes into the box the palette was opened over, or is copied.
    { label: "ph:smiley Emoji", keywords: "emoji emoticon smiley sticker kaomoji face insert", about: "Pick an emoji; it goes where you were writing, or is copied.", keys: "Ctrl+;", act: () => popupToolMaths.glyph("emoji") },
    { label: "ph:shapes Icons", keywords: "icon icons glyph phosphor insert shortcode", about: "Pick an icon; it goes where you were writing as :ph-name:, or is copied.", keys: "Ctrl+Shift+;", act: () => popupToolMaths.glyph("icon") },
    { label: "ph:pi Symbols", keywords: "symbol symbols arrow greek currency euro degree copyright maths character insert", about: "Arrows, maths, Greek, currency and writing marks; one goes where you were writing, or is copied.", keys: "Ctrl+'", act: () => popupToolMaths.glyph("symbol") },
    //: Over a note, Chat or a board's text; an open document has its own "Insert an equation" row (docPaletteCommands), so this one steps aside there.
    ...(editor.some((c) => /equation/i.test(c.label)) ? [] : [{ label: "ph:function Insert equation", keywords: "equation formula maths math latex fraction root integral matrix insert write", about: "The equation editor, over the box you were writing in: Insert puts it there as TeX, or Copy takes it.", keys: "Alt+=", act: () => openMathEditor({ target: popupToolMaths.box(paletteCaughtNow().target) }) }]),
    //: A list with ticks on screen (L-ui-modernisation-25): the three keys navigation.js answers, as rows, through the same scope.
    ...(openSelectionScope() ? [
      { label: "ph:checks Select all in this list", keywords: "select all tick every row batch", about: "Ticks every row of the list on screen.", keys: "Ctrl+A", act: () => openSelectionScope()?.selectAll() },
      { label: "ph:x-square Clear the selection", keywords: "deselect untick clear selection none", about: "Unticks every row.", keys: "Esc", act: () => openSelectionScope()?.clear() },
      { label: "ph:trash Delete what is selected", keywords: "delete remove selected ticked rows bin", about: "The ticked rows, with the same confirm or Undo as the bar's Delete.", keys: "Delete", act: () => openSelectionScope()?.remove() },
    ] : []),
    { label: "ph:closed-captioning Live captions", quick: "captions", keywords: "live captions subtitles transcribe speech microphone listen real time stop", about: "Write what the microphone hears as you go, on this computer. Run it again to stop and save a note.", act: () => toggleLiveCaptions() },
    { label: "ph:text-aa Count words", keywords: "word count characters letters reading time selection length", about: "Words, characters and reading time of the selected text, or of the editor.", act: () => { const caught = { ...paletteCaughtNow() }; ensureModule("utilities").then(() => countSelection(caught)); } },
    { label: "ph:translate Translate this", keywords: "translate translation spanish language offline selection passage", about: "The selected passage into Spanish, offline (a package).", act: () => { const caught = { ...paletteCaughtNow() }; ensureModule("translate").then(() => translateCaught(caught)); } },
    { label: "ph:activity Activity", keywords: "running jobs stop background model unload memory agent runs", about: "Every job running now, with Stop, and the agent's runs.", act: () => openActivity("running") },
    { label: "ph:stop-circle Stop the model", keywords: "unload free memory model stop generating", about: "Stop any answer and unload the model from memory.", act: () => ensureModule("activity").then(() => window.stopActivityModel()) },
    { label: "ph:package Settings, Packages", reveal: "settings:extras", about: "Optional parts: speech, reading pages, better search." },
    { label: "ph:tree-evergreen Settings, Logs", reveal: "settings:logs", about: "What happened, for when something did not work." },
    { label: "ph:question Settings, Help", reveal: "settings:help", about: "How the app works, a section at a time." },
    { label: "ph:info Settings, About", reveal: "settings:about", about: "The version you have and whether a newer one exists." },
    { label: "ph:archive Back up now", keywords: "backup snapshot save a copy", about: "Save a copy of the whole notebook, now.", act: () => { openSettingsModal("data"); backupNow(); } },
    { label: "ph:export Export markdown", about: "Every note as a Markdown file, in one download.", act: () => downloadExport("markdown") },
    { label: "ph:palette Appearance panel", keywords: "pop out theme colour text font layout background art motion peek look panel", about: "Every look setting in a panel beside the app.", act: () => openAppearancePanel() },
    { label: "ph:circle-half Toggle light/dark", keywords: "theme dark mode light mode night", chord: "toggleTheme", act: toggleTheme },
    //: INBOX 430: also in Find anything, which lists these same commands;
    //: the row says which it will do, since this list is built per query.
    { label: nameMarkBuddyShowing() ? "ph:eye-slash Hide companion" : "ph:person-simple Show companion", chord: "toggleCompanion", act: () => nameMarkBuddyToggle() },
    ...(nameMarkBuddyShowing() ? [{ label: "ph:crosshair Focus companion", keywords: "companion atlas keyboard tab reach arrow keys menu", about: "Put the keyboard on it: arrow keys move it, Enter says hello, Shift+F10 opens its menu.", act: () => setTimeout(() => document.querySelector("#nm-buddy .nm-buddy-face")?.focus(), 150) }] : []),
    { label: "ph:keyboard Keyboard shortcuts", reveal: "shortcuts", chord: "help" },
    //: INBOX 896: the status bar's wifi icon, by name, from anywhere.
    { label: "ph:wifi-high Other devices", keywords: "lan network wifi phone open close trusted networks address", about: "Whether a phone on this network can open the app, with the switch and the trusted networks.", chord: "lanPanel", act: () => openLanPanel() },
    { label: "ph:arrow-left Go back", about: "To the page or view you were on before.", chord: "navigateBack", act: () => stepTabHistory(-1) },
    { label: "ph:arrow-right Go forward", about: "Forward again, after going back.", chord: "navigateForward", act: () => stepTabHistory(1) },
    { label: "ph:arrows-clockwise Reload the app", about: "Clears cached files first, so the newest version loads.", chord: "forceReload", act: () => forceReloadApp() },
    //: The one way in to private notes was a chip on a card (audit 1031 N49).
    { label: "ph:lock-key Unlock private notes", keywords: "unlock private notes vault password open", about: "Enter your password to read your private notes.", act: () => unlockPrivateNotes() },
    { label: "ph:lock Lock Tessellate", about: "Close the notebook until the password is typed again.", act: lockNow },
    { label: "ph:clock-counter-clockwise Where you left off", keywords: "unsaved typed draft recent resume pick up", about: "Every box that holds words you typed and have not saved, one press to jump back to it.", act: () => typedWords("open") },
    //: The top bar's other controls, so each is in the palette too (ledger 1410).
    { label: "ph:gear Open Settings", chord: "settings", act: () => openSettingsModal() },
    { label: "ph:bell Open notifications", keywords: "bell", act: () => openNotifications() },
    { label: "ph:squares-four Switch space", act: () => $("space-switcher-btn")?.click() },
    { label: "ph:power Quit Tessellate", act: () => quitApp() },
  ].map(catalogueRun);
}

//: **Quick access** (INBOX 461; the owner of the Start something row: "make
//: this a quick access section ... what is there can be default"). Up to
//: `QUICK_ACCESS_MAX` tiles, the same five as before until the person
//: arranges them. A tile is one of `QUICK_START` or a command from the
//: palette's own registry (`paletteCommands`, below): any row that
//: declares a `tab` or `reveal` has a stable key (`tab:x`, `reveal:x`) and the
//: one line it already says about itself, so nothing here is a second list of
//: what the app can do. A key that no longer names a command is dropped, and a
//: list that resolves to nothing is the default five.
function quickCatalogue(only = null) {
  const out = new Map();
  const abouts = paletteAbouts();
  let rows = [];
  try {
    rows = paletteCommands();
  } catch {
    // A command that cannot be built must not take the dashboard with it.
  }
  for (const row of rows) {
    //: A row that is an act (no tab, no reveal) is a tile only when it says so
    //: with `quick`, a short stable name: Live captions is one (libr-1011 1220).
    const key = row.keys && !row.quick ? "" : row.tab ? `tab:${row.tab}` : row.reveal ? `reveal:${row.reveal}` : row.quick ? `act:${row.quick}` : "";
    //: `only`: the ids a caller will look up. The parts of the other ~300 rows are skipped (5 to 19 ms at 4x
    //: on every return to the dashboard, which asked for five tiles; INBOX 1778 d).
    if (only && !only.has(key)) continue;
    const parts = key && paletteRowParts(row, abouts);
    if (parts && parts.about && !out.has(key)) out.set(key, { id: key, icon: parts.icon.replace(/^(ph:)?/, "ph:"), label: parts.label, hint: parts.about, run: row.run });
  }
  return out;
}

function quickAccessItems(saved, catalogue) {
  const links = [];
  for (const id of Array.isArray(saved) ? saved : []) {
    const link = QUICK_START.find((l) => l.id === id) || catalogue.get(id);
    if (link && !links.includes(link)) links.push(link);
  }
  return (links.length ? links : QUICK_START).slice(0, QUICK_ACCESS_MAX);
}

function quickAccessCurrent() {
  const saved = prefsCache?.dashboard_quick_access;
  return quickAccessItems(saved, quickCatalogue(new Set(Array.isArray(saved) ? saved : [])));
}

function renderQuickLinks() {
  const box = $("dash-quicklinks");
  if (!box) return;
  if (quickEditing) return quickAccessEdit();
  const heading = document.createElement("p");
  heading.className = "launch-label";
  heading.textContent = "Quick access";
  const head = document.createElement("div");
  head.className = "launch-head";
  //: **Its own ⋯ on the title's line, at the right** (the owner, 2026-10-10:
  //: "a subtle like meatball icon in the top right on the same line as the
  //: quick access title ... for easier and more intuitive access to these
  //: buttons"): the Quick access half of Customise (Edit, Reset highlights,
  //: Reset), the same items, so the two cannot disagree. On the heading's
  //: line it covers nothing, which was the fault of the ⋯ this row had once.
  head.append(heading, kebabMenu(dashCustomiseItems().filter((item) => item.group === "quick"), "Quick access options"));
  const row = document.createElement("div");
  row.className = "launch-row launch-row-start edge-fade scroll-row";
  const tints = quickTints();
  quickAccessCurrent().forEach((link, index) => row.appendChild(quickLinkButton(link, quickTintKey(link.id, index, tints))));
  const group = document.createElement("div");
  group.className = "launch-group";
  group.append(head, row);
  box.replaceChildren(group);
  window.edgeFadeWire?.(row);
}
