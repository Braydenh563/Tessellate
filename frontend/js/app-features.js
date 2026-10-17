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
  return [
    { group: "Audio", items: [
      { name: "New meeting", desc: "A meeting note: when, who, agenda, notes, decisions and action items.", reveal: "meeting-new" },
      { name: "Record a meeting", desc: "Record a meeting or lecture, saved as you go; transcribed when the Voice notes add-on is installed.", reveal: "meeting" },
      { name: "Voice note", desc: "A voice memo, kept in Library, Recordings.", reveal: "voice-note" },
      { name: "Dictation", desc: "Speak a note into Capture; the Voice notes add-on types it.", reveal: "notes-dictation" },
      { name: "Recordings", desc: "Every recording kept: play at 0.5 to 2x, the waveform, markers, trim.", reveal: "recordings" },
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
      { name: "Skills", desc: "One-click requests like “Summarise my week”; can act on your notes.", reveal: "settings:skills" },
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
    // what the app does. A map is a board (see `createConceptMap`), so the two
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
      { name: "AI skills", desc: "The skills you can run, what each one does, and how to add your own.", reveal: "library-skills" },
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
      { name: "Focus timer", desc: "A ring timer with 5 to 50 minute lengths, optional breaks, a chime at the end and today's focused minutes.", reveal: "widget-focus" },
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
      { name: "A companion on screen", desc: "A small character that finds a free spot on each page and reacts to what you do.", reveal: "set-companion" },
      { name: "Your look", desc: "Shuffle the face drawn from your name, or choose its parts yourself.", reveal: "settings:preferences" },
      { name: "Accessibility", desc: "High-contrast mode and reduce-motion.", reveal: "set-contrast" },
      { name: "Custom CSS", desc: "For tinkerers: your own style overrides.", reveal: "set-custom-css" },
      { name: "Zoom the whole app", desc: "Ctrl with plus or minus scales every surface, and Ctrl+0 puts it back.", act: () => nudgeZoom(1) },
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
  ].map((group) => ({ ...group, items: group.items.map(catalogueRun) }));
}
