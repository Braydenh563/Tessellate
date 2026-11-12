"""The Guide's reference: `HELP_TOPICS`, one factual entry per feature area.

Moved out of `help_chat.py` whole (audit 1031 AI23, 3,740 lines; a pure move,
text unchanged) so that module stays about how an answer is found. This one is
the table the model answers from and Settings, Help lists, plus the keyword
adjustments applied to it. It imports only `help_topics_more` and the speller's
registry, never `help_chat`, so there is no cycle. `help_chat.HELP_TOPICS` is
this list.
"""

from __future__ import annotations

from tessellate.ai import spelling
from tessellate.ai.help_topics_core_tail import TAIL_TOPICS
from tessellate.ai.help_topics_more import MORE_TOPICS

# One factual entry per feature area, the model's *only* source of facts
# about the app, and what Settings, Help lists (`#settings-help`, drawn from
# `help_listing` through `GET /help/topics` since INBOX 448; it was thirteen
# hand-copied topics that had drifted from this table). `keywords` decide which entries a question pulls
# in; `badge` is the quick-access chip attached to the reply when this
# entry gets used, so "how do I set a reminder" both answers correctly and
# offers one tap into the Reminders tab.
HELP_TOPICS: list[dict] = [
    {
        "id": "capture",
        "keywords": (
            "capture",
            "note",
            "template",
            "dictate",
            "sketch",
            "improve",
            "proofread",
            "generate title",
            "generate a title",
            "title from its words",
            "draft",
            "tag",
            "category",
            "categorise",
            "write",
            "compose",
        ),
        "body": (
            'Notes tab: the "Add a note" line under the filter row (parted from it by a divider) opens a card over the list, so the list does not move '
            "(title and words, or a to-do list with Note and To-do; the line has a To-do icon that opens it as a list, pictures and files (any the chat takes) from the paperclip or a paste or drop, held as removable chips until you save, Draw for a sketch of your own, a colour, tags and a reminder bell; Close keeps your draft, Escape closes, Ctrl+Enter saves). "
            'Or type into "Capture a thought" and Save. A local AI files '
            "it into a category and suggests tags; you can re-file or edit anytime. "
            "Save as draft keeps it unfiled under Drafts instead, and after either, "
            "Write another takes you back to the box. "
            "Use a template, dictate with the microphone icon, sketch with the "
            'palette icon, or run "Improve" to proofread first, which needs no model (rewording does). '
            "A note's ... menu has Generate title, which with no model takes the title from the "
            "note's first sentence and is named Title from its words. The Writing room has "
            '"Split into notes", which turns a block of pasted text into several '
            "notes, split by its headings, paragraphs and subjects with no model and by meaning, "
            "auto-linked, with one. A formatting toolbar, here or in a document, is one Tab stop: "
            "Tab reaches it once, Left and Right move between its buttons, and Tab goes on to the page."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "ask-chat",
        "keywords": (
            "ask",
            "chat",
            "agent",
            "conversation",
            "tool",
            "question",
            "popup agent",
            "everywhere",
            "calculate",
            "convert",
            "conversion",
            "units",
            "currency",
        ),
        "body": (
            '"Ask your notebook" (Notes tab) and the Chat tab both answer from '
            "saved notes, with the raw notes beside the answer, each saying why "
            "it is there; in Ask, "
            "Enter asks and Escape clears the question, and the clock button "
            "answers from your notes as they were on a day you pick. Its AI switch "
            "picks who answers: off, the answer is From your notes, quoted from your "
            "notes' own sentences with no AI, and it is the answer when no model runs, "
            "in Ask and in Chat. "
            "They also see your tab and last actions, locally. "
            "Sums, conversions (at the dated rates named), the time and days "
            'until a date are worked out, model or not; "what did I do last '
            'week" recaps every change, by day; short follow-ups (and last week?, '
            "why?, shorter, no, the gym one) read against the question before; "
            "a cited board, map or document opens in its own place. With no "
            "model, Chat also acts (remind me to..., pin or delete the X note), with Undo. "
            "An answer can end with an offer as a link, or a chart (see Offers and charts in an answer). "
            "A note's "
            "... menu, under AI actions, has Explain this note: read aloud, then what it links to "
            "and why. Agent mode "
            "(a toggle in Chat) lets the assistant use its tools to search, link, "
            "tag, organise and create; changing or removing asks first, "
            "and after it reads a web page or a clipped or imported note, so "
            "does every change and web request. "
            "Conversations save and rename in the sidebar; the same agent pops "
            "open over any tab with Ctrl/Cmd+Shift+A (from More on a phone), "
            "runs with no model, numbers its answers like Chat's, and Ctrl+Z takes back its last write. "
            "While an answer is coming, "
            "the line under it says what is happening: Reaching Atlas, Reading "
            "your notes, Waking the model, Atlas is thinking, Atlas is writing, "
            "or Atlas and the tool's name, or with no model Working it out without a model; with "
            "Progress indicators set to Still, no dots."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "skills",
        "keywords": ("skill",),
        "body": (
            "Skills are one-click requests shown above the chat box (e.g. "
            '"Summarise my week"). Built-in skills ship with the app; add your '
            "own in Settings, Skills (its tab row goes to Your skills, Add or Share; New skill in the pane's bar opens the form). A skill can use the AI's tools, so it "
            "does the work rather than just describing it. A skill can also be "
            "a Markdown file saved in the skills folder that Settings, Skills "
            "names; it is listed without a restart. With no model running, nine built-in skills "
            "still run, read straight off your notes with no AI and labelled as such: Summarise my week, "
            "Daily review, Catch up on a topic, Find loose ends, Auto-tag my notes, Link related notes, "
            "Tidy suggestions, Notebook health check and Find notes worth combining. "
            "The others are greyed and marked (needs a model) in the Skills menu: they are unavailable while no model is connected."
        ),
        "badge": {"label": "Skills", "section": "skills"},
    },
    {
        "id": "graph",
        "keywords": (
            "graph",
            "concept map",
            "mind map",
            "mindmap",
            "network",
            "connected to",
            "untouched since",
            "filter the graph",
            "note panel",
            "node panel",
            "hub",
        ),
        "body": (
            "The Graph tab shows notes as a force-directed map, links and threads "
            "drawn between them, plus optional AI similarity lines. Search "
            "highlights matches, dragging rearranges, and the legend toggles "
            "categories on and off. Mind maps (drawn by you, not the "
            "automatic graph) are made and managed from the Library. A mind "
            "map's topics are notes, kept out of Notes and Recently added; a "
            "search finds them. After Enter names a topic, typing renames it. "
            "The Graph's search box reads filters as well as words: "
            '"connected to Harbor", "untouched since June", "tagged work", '
            '"pinned", "with pictures", "edited last week"; any other '
            "words still have to match. The box says how many notes match; Enter jumps to the next "
            "match and pans to it, Shift and Enter to the one before, and Esc clears the search. "
            "Click a note for its panel: Open, Focus, "
            "Pin and Link are at its foot and the ⋯ holds the rest. The panel stands "
            "beside its note and follows it as you pan and zoom; drag its title to "
            "put it somewhere else and it stays there until you close it. A hub's lines "
            "run straight and faint until you point at it."
        ),
        "badge": {"label": "Graph", "tab": "graph"},
    },
    {
        "id": "reminders",
        #: "recurring" is spelt out rather than left to the inflection rule:
        #: doubling the final consonant is exactly the kind of irregularity
        #: that rule deliberately does not guess at.
        "keywords": ("reminder", "due date", "snooze", "recur", "recurring", "early alert"),
        "body": (
            "The Reminders tab groups items into Overdue / Today / Upcoming / "
            "Done. To add, make or set a reminder, go to the top of the Reminders tab: type it in plain words on the "
            'Magic add line and press the sparkle (hedges such as "probably '
            'around 7pm" are read as the time, and a place like "when I get '
            'home" is left out of the title), or fill in Remind me to, the '
            "date and the time, then Add. Set a priority, snooze, edit inline, or make one recurring: "
            '"every weekday", "every 2 weeks", "the last Friday of the month", '
            'with an early alert such as "1 day before". '
            "The date and time fields open a month and the day's times, and "
            'read a typed day such as "next friday". '
            'You can also just say "call mum tomorrow evening" in a note and '
            'let the AI schedule it. In the chat, "remind me two hours before '
            'midnight" works too: Atlas passes your words and the app works '
            "out the time on your own clock. Notifications fire on the minute "
            "while a tab is open, even in the background, with Done and Snooze "
            "on them; the desktop app notifies with its window closed. If the "
            "browser blocks them, the list and the "
            "Notifications group in Settings say so, and their ? says how to allow them. "
            "Remind me is on a note's, a document's and a board's ⋯ "
            "menu too (and in a document, the / menu's Remind me about this), and the reminder's row opens what it is about. "
            "Select words in a note and Set a reminder in the selection menu "
            "reads a reminder out of them, linked to that note. When you tell "
            'the chat you need to do something on a day ("I need to call the '
            'dentist on Friday"), a Make this a reminder chip appears under '
            "the reply; nothing is made until you press it, and a question or "
            "something already done gets no chip."
        ),
        "badge": {"label": "Reminders", "tab": "reminders"},
    },
    {
        "id": "dashboard",
        "keywords": (
            "dashboard",
            "widget",
            "streak",
            "digest",
            "my day",
            "what changed today",
            "quiet topics",
        ),
        "body": (
            "The Dashboard is the at-a-glance home: a greeting with a line "
            "composed from your notes (what you wrote today or last, worded a "
            "little differently each visit and every few minutes), what is due and a pattern your notes show (a subject you "
            "keep writing about, a busy week; Tidy lists them), a search box, the Quick access tiles "
            "and widgets. Widgets include reminders, recent notes, stats, your streak, "
            "Most opened this month and Filings to check. The Digest widget is your day "
            "with no AI: what is due, open questions, what changed since "
            "yesterday and topics gone quiet, each line a count or a quote that "
            "opens its note. The Digest's week, on request, is written by Atlas or, with no model, composed from your notes: what you made, edited and binned, what is overdue and coming. Customise, beside the search box, has Edit "
            "layout and Widgets to show, hide and rearrange them; the layout is "
            "remembered per user."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        "id": "library",
        "keywords": (
            "library",
            "bookmark",
            "link shelf",
            "contents",
            "outline",
            "search",
            "find",
            "filter",
            "look for",
            "browse",
        ),
        "body": (
            "The Library is everything already made, in one searchable, "
            "filterable place: notes, documents, chats, files and tags, plus "
            "Bookmarks (a shelf for websites you visit often), Contents (a "
            "hyperlinked outline of the whole notebook) and Skills. "
            "The other sub-tabs are Documents, Boards & maps (whiteboards "
            "and mind maps), Images and Files. Each sub-tab's top bar ends "
            "with a ? that says what it holds. The Highlights chip lists every "
            "passage you marked in a note, each with its note. The Activity chip "
            "lists everything you and Atlas did, and its Export activity button "
            "saves that log as a spreadsheet (when, who, what, which item) to "
            "hand over. Events about private notes are left out of it. The "
            "Library's search reads the same filters as the Graph's: "
            '"connected to Harbor", "untouched since June", "tagged '
            'work", "pinned", "filed under Cooking". Drop files anywhere in '
            "the app to add them: pictures and PDFs go to Images, anything "
            "else becomes a document. On the Notes tab, .md and .txt "
            "files become notes instead, with Undo."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "documents",
        "keywords": (
            "document",
            "editor",
            "markdown",
            "code file",
            "live view",
            "source view",
            "word count",
            "character count",
            "search documents",
        ),
        "body": (
            "The document editor (opened from Library, Documents) has four "
            "views: Live (renders as you write), Source, Split and Read. Enter "
            "in the title moves to the body. The Library list's ... menu has Suggest a name. Code "
            "files get line numbers, Tab/Shift+Tab indenting and Ctrl+/ "
            "commenting, in a monospace face. Insert opens the / menu (Image opens a "
            'file picker). Unsaved words are kept per document for two weeks. "Check with AI" reviews a document for wording issues '
            "a spellchecker can't catch. The menu's Map the headings turns its "
            'headings into a new mind map. A mermaid code block (the "/" menu\'s '
            "Flowchart, or any Mermaid diagram: sequence, class, state, entity relationship, Gantt, pie, "
            "mind map, timeline and the rest) draws as a picture in Read and Live, in chat and Ask replies, "
            "in a print and in the HTML export; press "
            "it in Live to edit its text, and a block Mermaid cannot read stays as code with the reason under it. Print or "
            "save as PDF first asks for the page size, orientation, margins and "
            "page numbers, and a plain Ctrl+P uses the last choice; a code file prints "
            "as monospaced code with line numbers. In Live, in a note's edit box "
            "and in the graph popup, drag the corner of a picture to resize it (or "
            "Tab to the corner and use the arrow keys), and its align button puts it "
            "left, centre or right. A note card and the timeline's note view have "
            "the same align button (and the corner, apart from a card's small "
            "thumbnails); a picture set in one place looks the same in all. "
            "The status bar counts characters, words, lines and reading time as "
            "the note composer does (an emoji is one character); a code file "
            "shows lines, characters and the language instead. The type button (and New's arrow) lists file types; Markdown is rich text, "
            "a .mmd diagram opens beside its picture (Library, Diagrams). Search "
            'documents reads a window: "harbor last week" finds the harbor '
            "ones edited last week."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "whiteboard",
        "keywords": (
            "whiteboard",
            "sketch pad",
            "canvas",
            "freehand",
            "arrange as a grid",
            "grid of",
            "stack them",
            "sticky date",
            "date on a sticky",
            "export as jpg",
            "export as webp",
            "copy as an image",
            "copy the board as a picture",
        ),
        "body": (
            "The whiteboard (Library, Boards & maps) is a pannable canvas for "
            "freehand sketches and note cards together. Hover (or focus) a Library tile to see a larger preview beside the sidebar; Escape or starting a drag hides it. Freehand sketches also "
            "appear in the Library's Images sub-tab. A board's background colour "
            "and image are kept with the board. Board, Share and save, Export saves a PNG (1x, 2x "
            "or 3x, with a transparent background if you like), JPG, WebP, SVG or PDF named "
            "after the board, or Copy image puts the picture on the clipboard (also Copy as an image in Ctrl+K), or Copy as SVG in Ctrl+K puts the SVG on the clipboard as text (right-click a selection for Export selection, Copy as image and Copy as SVG). Paste text from another app onto a board: a link "
            "becomes a link box, one line a text box, a list a grid of stickies. "
            "In the command palette over a board, say what to do with the "
            'selection (or the whole board): "arrange as a grid of 3", '
            '"put them in a row", "stack them", "align left", "space '
            'them evenly", "same width"; Undo takes it back. A sticky that '
            "names a day shows it as a chip at its foot; press it to set a "
            "reminder for a day still to come. Fit (Shift+1) goes into the canvas you "
            "can see, clear of an open sidebar, Format panel, top bar and tools "
            "dock, and refits when one opens or closes until you pan or zoom "
            "yourself. Touch and pen erase. Drag an item to move it, or type its X and Y in the "
            "Format panel; the context bar over a selection, or the Format "
            "panel, changes its colour, line and words; on a narrow window "
            "the bar keeps one row and moves its order, dash and arrange "
            "buttons into its More menu. Draw a link between "
            "cards with the connector (C), from one card to the other; it "
            "ends in an arrow, and the bar over the rail sets its ends while "
            "the tool is held. Strokes and cards stack in one order; a new one "
            "goes on top, frames under all."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "files-images",
        "keywords": ("image", "photo", "caption", "ocr", "vision", "scan", "pdf", "file upload"),
        "body": (
            "Every image is read automatically, up to three ways: an AI caption "
            "of what it shows, a vision-model transcription of any text in it, "
            "and Tesseract OCR (or RapidOCR) if that's installed: all editable and searchable. "
            "A scanned PDF is rasterised page-by-page and read by an OCR model "
            "(no Tesseract needed); you can pick the model or leave it automatic. A "
            "picture placed on a board or map is the exception: it stays on the board, "
            "unlisted, unsearched and unread, until you select it and press Save to Library "
            "in Format (then it is filed and read like any other). Captions, in the row "
            "below it, draws a saved picture's caption as one muted line under it: on a "
            "board, under the pictures in a note's popup in the Graph and its timeline "
            "view, and the popup's menu has the same Show picture captions switch. A "
            "file attached to a note says nothing."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "timeline",
        "keywords": ("timeline",),
        "body": (
            "The Timeline tab lists what you wrote newest first, grouped by day, "
            "week, month or year (Auto picks the finest that reads well); the feed "
            "opens on today with the week ahead above it, and an empty day ahead has "
            "an Add for a reminder or an event. It shows as a "
            "feed, as a sortable table or as a calendar of a month, a week or a "
            "day. Kinds chooses notes, boards and maps, documents "
            "and reminders; Options sets the grouping, Group by (category, tag "
            "or thread) and Show group, and the Time range, where On this day "
            "shows today's date in earlier months and years. In the feed, Ctrl and "
            "the mouse wheel, or a pinch, makes the date groups finer or coarser, "
            "as do + and - on a row. The thin strip at the feed's right edge shows how "
            "much you wrote over the whole range, labelled by month or year (Options, "
            "Dates beside the strip, hides the labels and remembers it); click or "
            "drag it to jump; Shift and drag reads a span, what you wrote in those days with the notes beside it; Options, Review some days asks for the two days, by keyboard or on a phone. The strip under the bar walks your daily pages, and the "
            "chip under it offers On this day, and the year menu beside the month narrows the list to one year. A note that names a "
            'day ("on Friday") sits on that day and says All day; one that '
            'names a time too ("on Friday at 3pm") shows that time. '
            'A range ("away 3 to 7 March") sits on its first day and runs through the last in the calendar. '
            "A daily note is an ordinary note whose title is its day, such as 2026-09-13; "
            "the strip under the bar opens or starts one, and its head steps to the day before and after. "
            "A week or more with nothing written shows a line between the dates; its What happened here? "
            "starts a page for the first empty day."
        ),
        "badge": {"label": "Timeline", "tab": "timeline"},
    },
    {
        "id": "memory",
        "keywords": ("remember", "passive capture", "auto capture", "learn about me"),
        "body": (
            "Tessellate can pick up small facts and preferences as you write and "
            "chat, always asking first, never assumed. Accept or decline each "
            "suggestion right in the chat, and review or forget anything it has "
            "learned in Settings, What it remembers, which also lists the "
            "patterns you confirmed, to edit, remove or mark not right."
        ),
        "badge": {"label": "What it remembers", "section": "memory"},
    },
    {
        "id": "spaces",
        "keywords": ("space", "workspace", "separate notebook"),
        "body": (
            "A space is a separate notebook inside the same app: notes, "
            "documents, chats and tags kept apart from other spaces. Switch or "
            'create one from the picker at the top of the sidebar; "All '
            'spaces" shows everything together. Deleting a space asks what '
            "happens to its contents: move everything to another space (the "
            "default choice, with a count of what is inside), or delete everything in it "
            "(this skips the bin and cannot be undone, so you type the space's name to confirm); "
            "a category both spaces have is merged. Switching space swaps what you "
            "see in place, with no reload, so the tray and Undo carry across: an Undo made in another space "
            "(from the list or the toast's own button) takes you back to it first. A second window of the app follows a "
            "switch made in the first, and an answer still on its way from the old space is dropped. "
            "A space can be private: Private in New space or Edit space seals everything in it."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "appearance",
        "keywords": (
            "theme",
            "dark mode",
            "light mode",
            "accent colour",
            "accent color",
            "font",
            "density",
            "glass",
            "performance",
            "performance mode",
            "animation",
            "animations",
            "slow",
            "laggy",
            "blur",
            "appearance panel",
            "pop out",
            "peek",
        ),
        "body": (
            "Settings, Appearance controls theme (light/dark/system), accent "
            "colour, fonts, density, glass effects and the animated background. "
            "High-contrast and motion options are there for comfort and "
            "accessibility: Motion is Follow the system (the default, which "
            "still Atlas, the background art, the graph and the whiteboard when "
            "your browser asks for reduced motion), Always on (it moves "
            "whatever the browser asks) or Off, and Interface animations (on by "
            "default) keeps the short fades and slides of menus, dialogs and "
            "tabs and a button's press even then (a menu's spring and its "
            "rows arriving in turn stop with Motion off); turn it off and "
            "they are instant. "
            "Font and Density (Typography & layout) are lists you pick from. "
            "Font's Readable is Atkinson Hyperlegible, a face drawn so that "
            "letters easily mistaken for each other (l, I and 1; O and 0) "
            "look different; it ships with the app and works offline. "
            "Density's Auto, the default, is Compact on a window "
            "700px tall or less and the look's own spacing on a taller one. "
            "Glass controls, beside the frosted-glass blur, puts icon buttons in "
            "the same glass; it does nothing while the blur is off. "
            "Performance mode (Effects & accessibility) turns off "
            "the frosted-glass blur, the large animations and the animated "
            "background and slows the graph physics, for a slow or small machine; Auto "
            "switches it on by itself on a machine with 2 cores or 4 GB or fewer, "
            "and On or Off overrides that. The Appearance panel (Pop out at the top, "
            "or Ctrl+K, Appearance) holds the same settings beside the app, with "
            "a strip of sections and a Peek button. The sliders' numbers (Zoom, "
            "Corner rounding, Glass blur) type in too."
        ),
        "badge": {"label": "Appearance", "section": "appearance"},
    },
    {
        #: **The strip along the bottom had no entry at all** (INBOX 304). The
        #: app offers "What is the status bar telling me?" under the status
        #: bar's own '?', and the guide had nothing to answer it from: a
        #: suggestion the corpus cannot reach. Written from `STATUS_SLOTS` in
        #: `frontend/js/app.js` and the copy in `#statusbar-help`, which are the
        #: two places that decide what the bar actually shows.
        "id": "statusbar",
        "keywords": ("status bar", "statusbar", "bottom bar", "bottom strip", "the strip"),
        "body": (
            "The status bar is the strip along the bottom of every screen. It "
            "shows what the local model is doing (a grey sparkle with a slash "
            "means no model is connected and the notebook works without one), "
            "your note count, open and due "
            "reminders, back and forward (the small arrow beside them, or a "
            "right-click on either, lists the places you have been: an icon, the "
            "note's or document's title, a thumbnail when a note opens with a "
            "picture, and the tab in muted text under it; the X beside a row or "
            "Delete takes it off, and Clear this list keeps only where you are), "
            "undo and redo, "
            "Commands with its Ctrl/Cmd+K hint, and three icons: the agent's "
            "mark (crosses, a circle and an arrow, a play drawn up) for the popup agent, the "
            "compass for Atlas the guide, and the magnifying glass for Find "
            "anything (hover one for its name and keys). On this computer a wifi "
            "icon says whether other devices on your network can open the app: "
            "green open, amber closed on this network, plain off; press it (or "
            "Alt+L) for the switch, the address and the trusted networks. The offline "
            "badge, the power-saver badge and the running-job slot appear only "
            "when there is something to say. Settings, Appearance, Status "
            "bar chooses which of the rest to show."
        ),
        "badge": {"label": "Appearance", "section": "appearance"},
    },
    {
        "id": "shortcuts",
        "keywords": ("shortcut", "keyboard", "hotkey", "command palette"),
        #: Every chord in `DEFAULT_SHORTCUTS` (frontend/js/app.js) is named here,
        #: which `tests/test_help_controls.py` checks against the table, so a
        #: new shortcut fails the build until the guide can answer for it. It
        #: said "g then a letter" until INBOX 410: the chord had been "m" for
        #: months, and the guide was the one place still teaching the old key.
        "body": (
            "The first Tab offers Skip to the list. The category list is one Tab stop: "
            "arrows, Home and End walk it, the right arrow reaches a row's menu. "
            "Press ? for the full list; Settings, Keyboard shortcuts rebinds any of "
            "them (press a shortcut's keys, marked with a pencil, then the keys you want; type in the "
            "field above the list to find one), and on a Mac "
            "Cmd works in place of Ctrl. A button with a "
            "shortcut shows it in its tooltip, in your own binding. Everywhere: Ctrl+K "
            "the command palette, Ctrl+P find anything, Ctrl+F find on this "
            "page, / jump to search (the chat box on Chat), Ctrl+Z undo, "
            "Ctrl+Shift+Z redo (on a phone, More then Commands opens the "
            "palette), Alt+Left and Alt+Right back and forward, a double-click "
            "on Notes or Library in the top bar back to its first sub-tab, Ctrl+, "
            "settings, Ctrl+Shift+L light or dark, Ctrl+Shift+Y show or hide the "
            "companion, Ctrl+Alt+R reload clearing "
            "cached files. Make: Ctrl+Shift+N a new note, Alt+N a quick note saved "
            "without leaving the page, Ctrl+Shift+D a new "
            "document, Ctrl+D today's note, Ctrl+Shift+V paste what you copied as a "
            "new note, Ctrl+Shift+R record a meeting, Alt+L the other devices panel, "
            "Ctrl+Shift+K the quick sketch pad, Ctrl+Shift+B the whiteboard. "
            "Writing: Ctrl+S save, Ctrl+/ the blocks and commands menu (in a "
            "document it comments the line instead), Ctrl+J Atlas writes at the "
            "cursor, Ctrl+Shift+E actions for the selected text (a right-click on the selection brings its popup back). AI: "
            "Ctrl+Shift+A the popup agent, Ctrl+Shift+H ask Atlas about the app, "
            "Ctrl+Shift+O a new chat, Ctrl+Shift+G agent mode on or off, Ctrl+. "
            "stop the answer, Ctrl+Shift+P clip a note to your next question. "
            "Press t then a letter to jump to a tab (m works too); the panel that appears lists "
            "Go to and Do with each letter beside its name, marks the tab you are "
            "on, and takes a click as well."
        ),
        "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
    },
    {
        "id": "models",
        "keywords": (
            "model",
            "ollama",
            "lm studio",
            "vllm",
            "llama.cpp",
            "utility model",
            "chat model",
            "sampling",
            "temperature",
            "no model connected",
            "no model notice",
            "hide notice",
            "banner",
            "popup",
            "chatgpt",
            "openai",
            "gpt",
            "api key",
            "hosted model",
            "cloud model",
            "gemini",
        ),
        "body": (
            "Connect a model in Settings, Models, which picks the chat model and an optional smaller "
            "utility model for background jobs. Any OpenAI-compatible server "
            "works, not just Ollama, LM Studio, llama-server, Jan, vLLM. "
            "A hosted model, such as ChatGPT through the OpenAI API with its API "
            "key, works once Keep Atlas on this machine is turned off, since your "
            "notes then leave this computer. "
            "Sampling parameters (temperature, top-p, top-k, min-p, repeat "
            "penalty) are exposed there too, starting at what the model itself "
            "recommends. The No model connected banner above Ask, Chat and "
            'the writing desk can be hidden for good with Hide the "No model '
            'connected" notices under Model backend (saved on this device), '
            "or from the banner itself: the caret beside Connect a model has "
            "Hide these popups, and the toast that follows offers Show them "
            "again; "
            "Atlas still answers from your notes without a model. Until one "
            "is connected, the top of that page says so: its built-in composer, "
            "no AI."
        ),
        "badge": {"label": "Models", "section": "models"},
    },
    {
        "id": "storage",
        "keywords": (
            "backup",
            "storage",
            "data dir",
            "where is my",
            "export",
            "data folder",
            "import",
            "obsidian",
            "vault",
            "migrate",
            "restore",
        ),
        "body": (
            "Everything lives in a data folder you control: the notebook "
            "database, uploads, and daily local backups. Settings, Import & export shows "
            "exactly where it is on disk, and lets you export as JSON, CSV or "
            "Markdown, export the whole notebook as a folder (Export notebook "
            "folder: each note as markdown with its attachments and a .json file of "
            "every field, plus documents and boards, which From a Tessellate folder "
            "reads back), save a full backup (sealed with a password if you like) and "
            "restore one from a file, and manage or restore backups."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "studyhelp",
        "keywords": (
            "quiz me",
            "outline a note",
            "what did i write about",
            "flashcards",
            "flash cards",
            "key terms",
            "summarise a note",
            "study help",
            "what is due",
            "plan my week",
            "revise",
            "study without a model",
        ),
        "body": (
            "With no model running, Ask and Chat still help you study from your own notes. "
            "Say “quiz me on lecture 5” for questions built from its definitions, bold terms and lists (a request that is not an answer, or the Stop the quiz chip, ends it): "
            "answer in your own words, and “hint”, “skip” or “stop” work at any time; the score is kept in the "
            "conversation. “Make flashcards from this note” (or from a category such as “Uni”) writes question and answer cards and offers to save "
            "them as a note. “What are the key terms in lecture 5” lists them with the note's own definitions, and "
            "“summarise lecture 5” gives a short section-by-section version (say “more” or “shorter”). "
            "“What's due this week”, “what's left to do”, “plan my week”, “when is my exam” and “how long until the exam” read your reminders, the dates "
            "your notes give and your open checklist items. It also works out percentages, marks needed, dates "
            "(“what day is 3 weeks from friday”, “how many days since 1 october”) and word counts, and defines common study terms your notes "
            "do not cover. Small answers need no model: “pick one of pizza, sushi, tacos”, “what week is it”, “is 2028 a leap year”, “unix time now”, “5 factorial”, “round 3.14159 to 2 places”, “log 100” and “2(3+4)”. "
            "“Uppercase: hello”, “sort these lines: ...”, “join lines with commas: ...” and “count characters: ...” work on pasted text as an unsaved draft. After a due or plan list, “the second one” and “why” explain a line and where it came from; "
            "“What did I write about databases this week” lists that time's notes on a topic, dated, and “outline lecture 5” shows a note's headings with a word count each; "
            "after a reply that says a tool is off, “turn it on” links its switch (it never flips it for you). "
            "Every answer about a note is that note's own words."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "websearch",
        "keywords": (
            "web search",
            "websearch",
            "internet search",
            "searxng",
            "search the web",
            "search online",
            "look it up online",
        ),
        "body": (
            "Web search is opt-in. Turn it on in Settings, Web "
            "search, or with the Web button in Chat (it asks first; with web on, a click "
            "opens the panel, or turns web off if it is open): only your search words are sent out, "
            "never your notes, and never a question about your own notes or records. "
            "It runs in Agent mode: there the assistant looks something up online "
            "when asked, and a Chat question your notes do not answer is answered "
            "from the pages found, one line a "
            "page under its title, cited by its address. In Ask and in Chat's Ask "
            "mode answers come from your notes only, and the Web button says so; the "
            "Web panel still searches by hand. The pages are in the "
            "Web results fold under the answer; press a title to read one there, "
            "as text, or the arrow to open it outside. "
            "Paste a link and ask to read it: with web search on and no model "
            "the page is fetched and told back as its main points, key terms "
            "and sections; with it off you are told so and given the setting. "
            "If a web search cannot run because SearXNG is down, the reply and the Web panel offer "
            '"Start SearXNG" ("Install SearXNG" when absent; the reply also has "Set it up in '
            'Settings", "Open the web panel" and "Use another provider"), and the panel '
            "searches again once it answers; where this app cannot start it, it says why "
            "and links Web search settings. Banter, slang or a single word is never sent to the web: "
            "you are asked, with a chip for your notes and one for the web (also for a question both fit). To start it "
            "yourself with Docker, run: docker run -d --name searxng -p 8888:8080 "
            "-v searxng:/etc/searxng searxng/searxng, then press Auto-detect there. "
            "With SearXNG chosen and no address saved, the reply says it is not "
            "set up and links the setting. In the "
            "reader, Analyse this page lists the page's key points, marks its "
            "key terms in the text and lists its sections, each a link to its "
            "heading; it runs on this device and sends nothing out."
        ),
        "badge": {"label": "Web search", "section": "websearch"},
    },
    {
        "id": "privacy",
        "keywords": (
            "private note",
            "encrypt",
            "password",
            "lock",
            "security",
            "offline",
            "online",
            "internet",
            "cloud",
            "telemetry",
            "tracking",
            "local chip",
        ),
        "body": (
            "Yes, it works offline: Tessellate runs on this computer and needs no account or "
            "internet, and with no model connected it still answers from your notes. "
            "Private notes are encrypted at rest with a key derived from your "
            "unlock password. The app binds to localhost, has no account or "
            "telemetry, and nothing leaves your machine unless you explicitly "
            "turn on web search. Settings, Privacy, Where your data went lists "
            "every connection the app made, recorded as it happened, Since "
            "launch or All time, one row per place with what it was for (the "
            "file downloaded, the search words); its addresses are under "
            'Addresses. "Nothing left this computer." means none. The '
            "Local chip in the top bar says the same for this launch (Local, "
            "Local network or Online) and opens that record; on a phone it "
            "is a row in the top bar's More menu."
        ),
        "badge": {"label": "Privacy", "section": "privacy"},
    },
    {
        "id": "archive",
        "keywords": ("archive", "archived", "shelved", "out of the way"),
        "body": (
            "Archiving keeps a note, chat or document but gets it out of your "
            "everyday lists: different from the bin, since nothing archived "
            "is ever auto-cleared or at risk of being deleted. The action is "
            "in each item's own menu (next to Delete, not grouped with it); "
            "everything archived is still reachable from the Library's "
            "Archived filter, where Unarchive brings it straight back."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "undo-bin",
        "keywords": ("undo", "redo", "recycle bin", "restore", "deleted", "trash"),
        "body": (
            "Undo and Redo cover everything you change in your notebook. A deleted "
            "note, board, document, reminder, recording or OCR reading goes to the bin, not gone "
            "for good: restore it from the Library (Filter, Include the bin, or Open "
            "the bin from Ctrl+K), or press Undo in the toast right after, which also "
            "has a Go to bin button for a note. Empty the bin, in the bin's strip, clears "
            "everything in it for good, after asking. A deleted picture or file, a past "
            "question, what the notebook learned (even Forget everything), a board "
            "library and a space are kept for two weeks, so Undo brings them back. "
            "Ctrl/Cmd+Z undoes and Ctrl+Shift+Z or Ctrl+Y redoes; the status bar's "
            "Undo and Redo buttons do the same by click, and every step has a "
            "working Redo. Which history they walk depends on where you are: an "
            "open board or mind map has its own, an open document has its own, and "
            "both are kept while you switch away and back; everywhere else it is the "
            "app's (notes, tags, categories, links, files, bookmarks, renames, "
            "settings, chats, pins and the rest). Four things have no Undo, "
            "on purpose: Delete for good and Empty bin, which ask first; sending a "
            "chat message (the chat keeps its own history); asking the model "
            "something (it changes nothing until you accept); and sign-in, lock and "
            "background work. Inside a text box Ctrl+Z undoes your typing."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "voice",
        "keywords": (
            "dictate",
            "dictation",
            "voice",
            "voice note",
            "microphone",
            "meeting",
            "transcribe",
            "recording",
            "recordings",
            "speaker",
            "speakers",
            "who spoke",
            "trim",
            "marker",
            "read aloud",
        ),
        "body": (
            "The microphone icon on the note composer dictates a note using "
            'local Whisper: nothing sent anywhere. "Record a meeting or '
            "lecture\" (the command palette, Ctrl+Shift+R, or a meeting's Record "
            'into it) and "Voice note" keep the audio as a recording, saved '
            "every 10 seconds, even with no add-on; closing the recorder keeps "
            "it recording in a bar with Pause and Stop. The recorder's "
            "Microphone fold (and Settings, General, Microphone) chooses the "
            "input, noise suppression, echo cancellation and automatic gain; "
            "Enhance on save there cuts rumble and "
            "evens the loudness, keeping the original until the transcript is "
            "saved. With Live captions installed the words appear as you speak. "
            "With the Voice notes add-on it transcribes in the background (a "
            "notification says when it is done; Stop ends it) and the "
            "transcript is offered to save; saved, the recorder shows its "
            "first lines with Open. "
            "Library, Recordings searches names and transcripts (a hit plays from its line) and plays them "
            "at 0.5 to 2x with a playhead and the time; drag the waveform to "
            "seek, press M to mark a moment with a comment, Trim, and Download audio (in the more menu); a "
            "transcribed one lists its lines with their times (press one to "
            "play from it; a line's copy button copies it, Shift-click picks a run of "
            "lines, and the transcript's more menu copies the picked lines or all of "
            "them, with or without times) and downloads them as SRT or VTT subtitles; with "
            "the Speakers bundle (Settings, Packages) a transcript labels who speaks by voice, as Speaker 1, 2 and so on (Label speakers by voice in the menu does an old one); "
            "with only the AI on, turns are labelled from what is said. Rename a speaker names a label for good. "
            "In a document, ![[a recording's name]] plays it there. "
            "Read aloud plays an answer back to you; its item turns to Stop "
            "reading while it speaks, and Settings, General, Read aloud sets the speed (0.75x to 1.5x)."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    #: INBOX 644: meetings are one shape of note with a sheet of their own.
    {
        "id": "meetings",
        "keywords": (
            "meeting",
            "meetings",
            "meeting notes",
            "new meeting",
            "agenda",
            "action item",
            "action items",
            "attendees",
            "minutes",
            "standup",
            "decisions",
            "summarise meeting",
        ),
        "body": (
            "New meeting (the Dashboard's Quick access, the command palette, "
            "Library's Create, Tools and features) asks for a title, when and "
            'who (a title like "Sync with Ana friday 2pm" fills When and '
            "Who from its chips), then opens the meeting as a note with Agenda, Notes, Decisions "
            "and Action items; Start and open recorder does the same and opens the "
            'recorder, writing into its Notes; press Record there (Ctrl+Shift+R opens it too). Write an action item as "- [ ] Send the deck '
            '@Sam by Friday": @Name is its owner, the plain words its due. '
            "The meeting chip on the note (or its ... menu, Meeting) opens the "
            "meeting sheet: Remind me makes an action item a reminder, asking "
            "when if the line does not say; Summarise finds the decisions and "
            "action items in your notes, each with the words it came from, and "
            "adds them only when you press Add (Undo takes them back); Record "
            "into it transcribes on this machine and adds the transcript under "
            "Notes; Date and people changes when and who. All of it works "
            "with no AI: Summarise then reads lines saying decided, agreed, "
            "Action or TODO, or a name taking a task, and says so; with the AI "
            "on it rewords the same list. Every meeting is under Notes, "
            "Meetings, and sits on the Timeline at its own date. Its card shows the first agenda item, "
            "the decisions and the open action items; Show the whole note opens the text."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "autonomous",
        #: The last three are the words a person uses for this rather than the
        #: name the feature has: "what can it change on its own" is the
        #: question, and it used to reach the entry about Atlas instead,
        #: because it names Atlas and nothing else matched (INBOX 304).
        "keywords": (
            "background librarian",
            "auto tag",
            "auto-tag",
            "auto link",
            "auto-link",
            "dedupe",
            "duplicate",
            "autonomous",
            "on its own",
            "by itself",
            "without me",
        ),
        "body": (
            "Autonomous background AI is turned on in Settings, Background "
            "tasks. The background librarian then tags, links and flags "
            "duplicate notes on an interval you choose. It is off by default, "
            "since it writes to your notebook without being asked each time. "
            "It never deletes anything and skips itself on battery power. It "
            "also gives a second opinion on notes that were filed by your "
            "notebook's own words while no model was available, moving the "
            "ones the model files elsewhere."
        ),
        "badge": {"label": "Background tasks", "section": "tasks"},
    },
    {
        #: **The guide's entry about itself** (INBOX 204: "improve its
        #: capabillity and knowledge"). The one question every chat is asked
        #: first, "what are you, and what can you do", was the one question
        #: this one had no reference note for: with no topic matched the
        #: prompt tells the model to say it is not sure, so the guide
        #: answered "I'm not sure" when asked what it was. Its own name is a
        #: keyword because a person who has just read "Atlas" at the top of
        #: the sheet will type it.
        "id": "guide",
        "keywords": (
            "atlas",
            "guide",
            "who are you",
            "what are you",
            "your name",
            "yourself",
            "what can you do",
            "what do you do",
            #: The exact words under this panel's own '?' (`ATLAS_PROMPTS`,
            #: "help-chat-help"). A suggestion the corpus cannot answer is the
            #: worst kind of dead end, which is why
            #: `test_every_question_the_app_offers_to_ask_atlas_is_answerable`
            #: now reads that table against this one (INBOX 304).
            "what can you help",
            "help me with",
        ),
        "body": (
            "Atlas is this app's in-app guide, named for a book of maps. It "
            "answers how-to questions about Tessellate itself from the app's "
            "own help: where a feature lives, what a setting does, which tab "
            "to be on. It answers on the utility model in Settings, Models "
            "while smart model routing is on, on the chat model while that is "
            "off, and Settings, Models can give the guide a model of its "
            "own. With no model running it still answers from the help: "
            "Atlas's answer is put together for your question, and the From "
            "the help tab above it shows the topic word for word. "
            "It cannot read your notes or documents (ask the "
            "Chat or Ask tab for those), and nothing said to it is saved: the "
            'conversation is gone on reload, and "New chat" clears it now. '
            "It is reachable from the status bar on every tab, from the head "
            "of every Settings pane, from the command palette (Ask the Guide), "
            "from the Help pane in Settings and, on a phone, from More. An answer's "
            "open button lands on the control it is about, ringed. A question "
            "an answer suggests is a button under it: one press asks it, here "
            "and in Chat and Ask."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "command-palette",
        "keywords": ("command palette", "jump anywhere", "quick actions", "jump to"),
        "body": (
            "Ctrl/Cmd+K opens the command palette: jump to any tab or "
            "setting, or run a quick action (new note, new "
            "chat, back up now, toggle the theme, and more) without leaving "
            "the keyboard. Type a note's name and the top three matching "
            "notes are listed under the commands (Enter opens one); its "
            "last row, Search everything "
            "for, opens Find anything (Ctrl/Cmd+P) with the words already "
            "searched, for documents, files and the rest. Typed words also find every feature in Tools and "
            "features, every act Chat does (it opens Chat with the words "
            "started) and the matching settings, by what the words mean too "
            '("trash" finds the bin, "keybord" the shortcuts); a word a '
            "letter out offers the nearest, and what you ran for the same words comes first "
            "next time (hover a row to see why it is where it is). "
            "It's a different box from the popup agent "
            "(Ctrl/Cmd+Shift+A): this one runs fixed commands, that one "
            "answers and acts on an open-ended request. Typed as a "
            'reminder ("remind me friday 9 dentist"), its first row is '
            "that reminder, with its chips under the box."
        ),
        "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
    },
    {
        "id": "extract-notes",
        "keywords": ("extract notes", "rough thoughts", "writing room", "draft"),
        "body": (
            "Split into notes, in the More menu of the Writing room (Notes "
            "tab), turns a block of pasted free text into several notes "
            "instead of one long one: with no model it cuts at the text's "
            "headings, paragraphs and subjects and links the parts, with one it splits by "
            "meaning and links with reasons. A preview comes first either way. "
            "The Writing room is for turning rough, unstructured thoughts into "
            "a proper note before it's saved: Suggest a title there takes the "
            "title from your own words with no model, while Draft and Refine "
            "need one and say so when pressed. A document's menu, a selection of "
            "text, a note under review and a selection of cards on a board have "
            "Extract notes, which does the same for a document, the text or those cards."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "favourites",
        "keywords": ("favourite", "favorite", "star", "starred", "pin", "pinned"),
        "body": (
            "Starring (pinning) a note makes it a favourite and floats it to the top of the list, a parallel way to keep "
            "important notes close, separate from categories or tags. "
            "Favourites show in the sidebar, filter in the Library, and can "
            "sit in their own Dashboard widget."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    #: **Five topics added after an audit against what the app can actually
    #: do.** Asked for directly: "did you make sure full usage guides exist in
    #: the docs for the help ai to use??" The answer was mostly yes, every tab
    #: had an entry: but the checker found five features the help AI could not
    #: describe at all, which means it would have guessed. A help assistant that
    #: guesses is worse than one that says it does not know, so anything it can
    #: be asked about needs an entry here.
    {
        "id": "ocr-workspace",
        "keywords": (
            "ocr",
            "read text",
            "scan",
            "scanned",
            "extract text",
            "transcribe",
            "tesseract",
            "vision model",
            "page read",
            "pdf text",
        ),
        "body": (
            "OCR workspace: open any image or PDF from the Library or a note and "
            'choose "Read text", or open it from Commands, Find anything or '
            "Quick access (search ocr). A pinch, two fingers on a touch screen "
            "or Ctrl and the wheel zooms the page about the pointer. Where "
            "Tesseract or RapidOCR read it, drag across the words on the page "
            "to select them; Ctrl+C copies them in reading order. Find in what "
            "was read marks every match, and Enter or its arrows step through them. Saving an "
            "edit, deleting, cleaning up and reading again all undo with Ctrl+Z, "
            "and a deleted reading goes to the bin. The reader button in the tool row (its dot is "
            "green when it can read) picks the AI document "
            "reader (a model built to transcribe a page), the general vision "
            "model where you have a different one installed, Tesseract, or "
            "RapidOCR (English and Chinese, nothing else to install; chosen, it "
            "reads even when Tesseract is ready). The two local ones "
            "need no model, are about ten times faster and are the only readers "
            "that tell you where on the page each block sits; Tesseract first "
            "enlarges small text and evens out a dark page, and reads a "
            "region you draw as one block; the workspace "
            "remembers your choice. Read this page "
            "reads what is on screen; its menu reads every page or a range like "
            "1-5. Ask sends the page to the chat as a chip on your next "
            "message. A read keeps running if you "
            "close the window: it shows in Settings, Background tasks and can "
            "be stopped from there or from the workspace, and every page that "
            "has been read is remembered, so reopening the document shows the "
            "text again rather than starting over."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "document-history",
        "keywords": (
            "history",
            "version",
            "revision",
            "restore",
            "undo edit",
            "previous version",
            "git log",
            "rollback",
            "ai edit log",
            "old version",
            "earlier version",
            "what it used to say",
            "roll back",
            "named version",
            "name this version",
            "compare versions",
            "side by side",
        ),
        "body": (
            "Documents keep a history. The ... menu, History, lists every "
            "version the document has had, newest first, with who changed it "
            "(you, an AI edit, or a restore), how many words it gained or lost, "
            "and the opening of that version. Name this version keeps the text as "
            "it stands under a name (Named shows only those; a row's ... menu "
            'renames one). "Changes" shows a version side by side with the one '
            'after it on a wide window. "View" reads an old version '
            'without changing anything; "Restore" puts it back at once and keeps '
            "the version it replaced: Ctrl+Z or the toast's Undo returns the text "
            "you had. Rename, archive, a detached note or link and a dictionary "
            "word undo the same way. A stretch of "
            "editing counts as one entry rather than one per autosave. The AI "
            'panel has a separate "AI edits" log for reverting one specific '
            "suggestion the model made."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "writing-checks",
        "keywords": (
            "spelling",
            "spellcheck",
            "suggestion",
            "proofread",
            "grammar",
            "dictionary",
            "rephrase",
            "wording",
            "autocorrect",
            "flagged",
        ),
        "body": (
            "The document editor checks spelling, spacing and sentence length as "
            "you write, and grammar (agreement, a or an, its or it's) with Harper, "
            "a checker that runs on this computer; note boxes get the "
            "grammar check too, and the dictionary dialog turns it off. Code, "
            "addresses, file paths, emails, units after a number "
            "(10 min, 5 km) and the words of a link are skipped; Check link "
            "text (Settings, General, Writing; or the dictionary dialog) turns the "
            "link words back on. List items, headings and table cells are "
            "never judged as long sentences. It also "
            "checks accessibility: a skipped heading level, an image with no "
            'description, link text like "click here". Where the text names '
            "another note or document, a thin underline offers to turn the first "
            'mention into a [[Note title]] link (under "Links to your notes"; Fix never '
            "applies these). In Live "
            "view a flagged word is underlined: click or "
            'right-click it for corrections, "Add to dictionary" or "Ignore '
            'this for now". A very long document is checked near the view '
            'only (the count says "nearby"). The Suggestions panel lists every finding; clicking '
            "one scrolls to it and opens its answers, the check on a row accepts "
            "its one clear fix and the crossed eye ignores it, and the arrow keys "
            "walk the rows. Fix applies every clear fix at once; the ... in the "
            "panel's head holds Check with AI, Hide all suggestions (quiets every "
            "underline and the list until shown), Dismissed (the "
            "suggestions put away in this document, each with a Restore), the "
            "Dictionary and which side the panel docks on. For an awkward "
            'sentence with no mechanical fix, "Ask the AI for wordings" offers '
            "two or three alternatives; nothing changes until you choose. "
            "Manage the dictionary and the spelling preference (American, "
            "British, Australian, Canadian or Indian) from the editor's own "
            "dictionary dialog. LanguageTool, an optional second grammar "
            "checker, is in Settings, Packages."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "notebook-questions",
        "keywords": (
            "how many",
            "most common",
            "statistics",
            "stats",
            "count",
            "top tags",
            "busiest",
            "untagged",
            "orphan",
            "most linked",
            "abbreviation",
            "acronym",
            "stand for",
            "short for",
            "summarise this",
            "summarize this",
            "tl;dr",
            "what's in",
        ),
        "body": (
            "You can ask about the notebook itself, not just what is in it: "
            '"what are my most common tags", "which categories have the most '
            'notes", "how many notes do I have", "how many notes have no '
            'tags", "how many pinned notes", "how many open tasks", "how many '
            'reminders this week", "which are my most linked notes", "when do I write '
            'most", notes from a season, which follows your hemisphere ("last summer" is December to February in en-AU, en-NZ and en-ZA; Settings, General, Seasons overrides it), or part of a month ("the first week of '
            'October", "the second half of March"), a weekend ("last weekend"), and notes by the order you made them: "the first note I ever wrote", "my 5th note", "my newest note". "What is new" and "my longest streak" too. These are counted from your data, so '
            "they are exact with no AI model; a model says the counted answer "
            "in its own words, never a new figure or date. Private and binned notes are never "
            "counted. Your abbreviations are learned the same way: when a "
            "note names Cloud Computing beside CC, asking about CC finds both, "
            'and "what does CC stand for?" says which note told it. '
            '"Summarise this" sums up the document, board or note you have open, or the '
            'category the sidebar is filtered to; "summarise Travel" reads '
            "every note in that category. With a note open, \"what's left to "
            'do?", "when is the deadline?" and "who is involved?" are '
            "answered from that note alone. "
            'A request with no direction ("do something cool", "open a note") '
            "gets a question back with choices you can press; an instruction "
            "the app does not understand is matched to the closest things it can do. "
            "With no model running, an answer ends with a line pointing at what to do next, "
            "from your newest note; the Length picker applies (Quick keeps the first line only, "
            "Detailed keeps everything). A persona is an instruction for a model, so with no "
            "model it changes nothing: the app answers in its own voice."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "contradictions",
        "keywords": (
            "contradict",
            "contradiction",
            "tension",
            "disagree",
            "conflict",
            "inconsistent",
            "changed my mind",
            "out of date",
        ),
        "body": (
            "Tessellate can look for places where two of your notes disagree, a "
            "decision you reversed, a fact you later corrected, and show them "
            "side by side with the dates, so you can see which is current. It "
            "runs on demand rather than constantly, because it is a real pass "
            "over the notebook with the local model. It never edits anything: "
            "the point is to show you the pair and let you decide. Open "
            "Suggestions (the Tensions widget's Review disagreements, or the "
            "command palette), choose Tensions and press Start the review. "
            "What a review or the overnight pass already found stays found: "
            "the Tensions widget lists the pairs still to decide, each with "
            "what it is about and which model found it when, and its buttons "
            "open either note, link the two as contradicting, or dismiss the "
            "pair for good. A review only reads pairs it has not read before."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
]

#: **The vocabulary people actually use, and the topics they asked about that
#: had none** (INBOX 406, measured on `tests/fixtures/help_questions.json`).
#: Kept as edits beside the table rather than rewritten into it, so each
#: entry above still reads as it was written and this block says what the
#: question bank taught: words moved to the topic they name (a note's tags
#: are filing, not capturing), generic words taken off topics they pulled
#: every question towards ("note", "atlas"), and the ways people phrase a
#: thing ("talk to the ai", "pictures", "journal") added where they belong.
_KEYWORDS_ADD: dict[str, tuple[str, ...]] = {
    "capture": (
        "take notes",
        "take a note",
        "make notes",
        "write notes",
        "new note",
        "quick note",
        "quick thought",
        "write a note",
        "make a note",
        "jot",
        "without filing",
        "save a note",
        "create a note",
        "create a new note",
        "add a note",
    ),
    "ask-chat": (
        "talk to",
        "citation",
        "cite",
        "sources",
        "answer from my notes",
        "ask atlas",
        "chat with",
    ),
    "skills": (
        "automate",
        "automation",
        "reorganise",
        "reorganize",
        "reorganising",
        "reorganizing",
        "workflow",
        "routine",
    ),
    "graph": ("see how", "visualise", "visualize", "unlinked", "dotted line", "connections map"),
    "reminders": ("remind", "remind me", "due", "alarm"),
    "dashboard": (
        "home",
        "home page",
        "start page",
        "compact",
        "rearrange",
        "numbers on the dashboard",
    ),
    "library": ("all my files", "old chat", "chats", "everything i have", "my files"),
    "whiteboard": ("board", "draw", "drawing", "sticky", "sticky note", "pen", "infinite canvas"),
    "files-images": ("picture", "pic", "attach", "attachment", "upload"),
    "timeline": (
        "journal",
        "diary",
        "daily note",
        "today's note",
        "last month",
        "last week",
        "what i wrote",
    ),
    "memory": ("forget", "remembers", "about me"),
    "spaces": ("separate", "work and personal", "personal notes", "different notebooks"),
    "statusbar": ("dot", "bottom corner", "at the bottom"),
    "models": (
        "ai model",
        "llm",
        "connect a model",
        "turn off the ai",
        "without the ai",
        "no ai",
        "local model",
        "which model",
    ),
    "storage": (
        "where is my data kept",
        "back up",
        "disk space",
        "disk",
        "where is my data",
        "data stored",
        "export everything",
        "move my notes",
    ),
    "websearch": (
        "internet",
        "web",
        "google",
        "browse the web",
        "search the internet",
        "search online",
    ),
    "privacy": (
        "private",
        "leave my computer",
        "left my computer",
        "left this computer",
        "where your data went",
        "data leave",
        "sent anywhere",
        "privacy",
        "spy",
    ),
    "undo-bin": ("delete", "by mistake", "bin", "get back", "recover"),
    "voice": ("speak", "speech", "record", "transcribe a recording"),
    "autonomous": ("background", "automatically", "overnight"),
    "command-palette": ("ctrl k", "commands"),
    "extract-notes": ("pull notes out", "split into notes", "from a chat", "out of a chat"),
    "document-history": ("older version",),
    "ocr-workspace": ("scan a document", "scan a page", "read a scan"),
    "writing-checks": ("spell",),
    "guide": ("what is atlas", "who is atlas"),
}

_KEYWORDS_REMOVE: dict[str, tuple[str, ...]] = {
    "capture": ("note", "tag", "category", "categorise", "template", "dictate", "write"),
    "graph": ("mind map", "mindmap"),
    "library": ("search", "find", "filter", "look for", "bookmark", "contents"),
    "privacy": ("password", "lock", "private note", "encrypt", "security"),
    "appearance": ("slow", "laggy"),
    "guide": ("atlas",),
    "storage": ("where is my",),
}

for _topic in HELP_TOPICS:
    _drop = set(_KEYWORDS_REMOVE.get(_topic["id"], ()))
    _topic["keywords"] = tuple(k for k in _topic["keywords"] if k not in _drop) + tuple(
        k for k in _KEYWORDS_ADD.get(_topic["id"], ()) if k not in _topic["keywords"]
    )

HELP_TOPICS.extend(
    [
        {
            "id": "write-with-atlas",
            "keywords": (
                "write for me",
                "write with atlas",
                "writing room",
                "draft a note",
                "rewrite",
                "continue the draft",
                "bullets to prose",
                "prose to bullets",
                "write an essay",
                "write an email",
                "draft",
                "make a diagram",
                "make a flowchart",
                "mind map from text",
                "writing without a model",
                "tidy and spellcheck",
                "make it formal",
            ),
            "body": (
                "Notes tab, Writing room: pick what to write (draft a note, "
                "continue or rewrite the draft, bullets to prose, prose to bullets, "
                "a diagram, or translate), add notes as sources if you want it grounded in "
                "them (a note dropped or pasted from the Tray into Your thoughts is added "
                "as one), and press Draft. The draft stays in the box to edit; save it "
                "as a note when it reads right. Which model writes is set on the "
                "same row, or in Settings, Models. With no model Atlas does it by "
                "rule, marked From your words, and offers only what that does well: tidy and "
                "spellcheck, write up your notes by date, plain or formal words, bullets "
                "either way and a diagram. Refine takes shorter, add a summary, as bullets, "
                "as a list, formal or tidy up; Carry on and Translate come back with a model."
            ),
            "badge": {"label": "Writing room", "tab": "notes"},
        },
        {
            "id": "security",
            "keywords": (
                "password",
                "lock",
                "locked",
                "lock screen",
                "security",
                "sign in",
                "log in",
                "private note",
                "encrypt",
                "forgot password",
                "recovery key",
                "idle",
                "pin code",
                "set a pin",
                "unlock pin",
                "my pin",
                "quick unlock",
                "windows hello",
                "where you left off",
                "unsaved words after lock",
            ),
            "body": (
                "Settings, Account & security: set a password and the notebook "
                "asks for it when it opens. The lock button in the top bar locks it "
                "now, and it locks itself after the idle time you choose there. "
                "After a few wrong passwords the lock screen says how long to wait and "
                "Unlock counts it down. "
                "While it is locked, an open dialog or popover is put away, and "
                "it comes back as it was after you unlock, and the lock screen takes focus. "
                "Words you typed and had not saved are sealed with your password when it locks, "
                "emptied from the page, and put back after you unlock; Where you left off, in the "
                "toast that follows and in the Ctrl+K palette, lists each box that holds them and jumps to it. "
                "To make a note private, open its ... menu and press Make private; Make readable undoes it. "
                "Private notes are encrypted with that password and are never sent "
                "to the AI, so a private note's menu has no Tag and file, Improve writing or title acts. Forgot it? "
                "Press Forgot your password? on the lock screen, on this computer: "
                "with a recovery key (made at setup or in Account & security) you "
                "set a new one and keep private notes; without it, a reset keeps "
                "everything else and leaves private notes sealed. PIN for this "
                "computer: Set up a PIN for this computer (your password, then a "
                "PIN of 4 to 12 digits twice) lets the lock screen take the PIN "
                "or your password, on this computer only; phones always need the "
                "password. The computer's own protected store keeps it, never the "
                "notebook or a backup. Five wrong PINs, a password change or "
                "Forget PIN remove it. Unlock with Windows Hello, under the PIN, "
                "lets the lock screen and private spaces take your face, finger "
                "or Windows PIN on this computer only, with Unlock with Windows "
                "Hello on the lock card; a password change, re-encrypting or a "
                "restore turns it off, and your password always works."
            ),
            "badge": {"label": "Account & security", "section": "account"},
        },
        {
            "id": "search",
            "keywords": (
                "search",
                "find",
                "find anything",
                "look for",
                "filter",
                "where did",
                "locate",
                "ctrl p",
                "operator",
                "search my notes",
                "saved search",
                "search chats",
            ),
            "body": (
                "Find anything (Ctrl+P, or the search box on the dashboard) looks "
                "through notes, documents, boards, mind maps, files, links, reminders, "
                "chats and recordings (by title and by what was said) at once, by your words and by meaning; each result wears "
                "its kind, and the chips narrow it to one. Operators: tag:work, "
                "in:work for a space or category, cat:work (or -cat:work), tags:<2 for how many tags, kind:chat, before:tuesday, after:2025-06-30, "
                "has:image, is:pinned, title:budget for titles only, is:deleted to look in the bin "
                '(otherwise left out), a "quoted phrase", and -word or -tag:work (also -kind:, -is:, -title:) to leave something '
                "out. A filter it does not know is named under the box. Numbers match as typed. The star saves a search as a row in the Notes sidebar. A small typo that "
                "finds nothing is searched as the nearest word your notes use, "
                'and the line says "showing results for" it. When nothing matches, '
                "it says what was searched and offers one way on: every kind, a "
                "spelling, or the nearest feature. To narrow only the "
                "notes list, use Filter notes on the Your notes tab. Every search box "
                "suggests as you type: your recent searches first, then note titles, "
                "tags and categories that start with your words (a Library list's box: "
                "that list's own titles), with the best match in grey (Tab or Right takes it, Down and Up walk the list; Esc or a click outside closes it). "
                'Chat answers "notes mentioning test" or "notes with test in them" from every note the search finds, one line each with a link, '
                'and says the same count the greeting offers. A language named as a property of a note ("japanese note", "notes written in French") '
                "finds notes by their script or everyday words, with no web search. "
                "A recent search has its own x, the list's foot clears them, Settings, "
                "Import & export, Clear and forget clears every box's at once, and Settings, "
                "General, Search turns the suggestions off."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "links",
            "keywords": (
                "link",
                "linked",
                "linking",
                "connect",
                "connection",
                "backlink",
                "wiki link",
                "link two notes",
                "related notes",
                "find links",
                "suggested links",
                "why suggested",
                "suggestions",
                "merge names",
                "same person",
                "link type",
                "kind of link",
                "part of",
                "link properties",
            ),
            "body": (
                "Link one note to another by typing [[ and the start of its title, "
                "then picking it from the list. The link shows on both notes as a "
                "connection, with a menu to add a reason, open or remove it. Atlas "
                "also suggests links as you write, and every note's menu has Link "
                "to. The Graph draws all of them. A note's menu also has Copy wiki "
                "link (a [[link]] for another note) and Copy app link (an address "
                "that opens the note in the app). Delete the [[name]] and its link "
                "goes with it; rename a note and a toast offers to rename the "
                "[[links]] other notes have to it. A note's Connections show the "
                'sentence each linking note says it in, and "Mentioned, not '
                'linked" with a Link button (greyed out, with the reason, for a '
                "note whose opening line has a square bracket in it, which a "
                "[[link]] cannot hold). Suggestions (Find links to add on the "
                "Dashboard's Loose ends, Suggest links in the Graph's options, or "
                "the command palette) is one sheet of four kinds: Links lists pairs "
                "worth connecting with every reason (similar wording, people or "
                "things both name, a note both link with, a rare tag both carry) "
                "and how sure it is (Link all above 70% over the list links every pair at "
                "least that sure, after asking, and the More menu beside it has Suggest reasons "
                "and Explain your existing links); Tensions, notes that may disagree; Names, one "
                "person or thing named two ways, with Merge; and Link types, a link whose own "
                'sentence says "for example" or "continues". Accepting or '
                "dismissing any of them teaches it which reasons to trust in your "
                "notebook, and a dismissed one does not come back. A link's ⋮ has "
                "Kind and properties: a kind says what the link is (Supports, Part "
                "of, your own) and reads from the other note by its other name "
                "(Supported by, Has part); Kinds of link in the command palette "
                "adds, renames and deletes your own. The assistant can link two "
                "notes with any of these kinds too, yours included."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "troubleshooting",
            "keywords": (
                "not working",
                "isnt working",
                "doesnt work",
                "broken",
                "error",
                "no model",
                "cant connect",
                "cannot connect",
                "stuck",
                "crash",
                "fails",
                "logs",
                "not answering",
                "isnt answering",
                "not replying",
                "doesnt answer",
                "get an error",
                "out of date",
                "looks wrong",
                "clear cache",
                "clear the cache",
                "app cache",
                "stale",
                "after an update",
            ),
            "body": (
                "If Atlas does not answer, the message says why and has Try again and "
                "Settings, Models beside it: Models says whether a "
                "model is connected. Start Ollama (or LM Studio, or a llama.cpp "
                "server), pick a model and press Connect. Everything except Chat, "
                "drafting and skills works without one, and Notes, Ask answers from "
                "your notes. Settings, Logs shows the last errors (a finished task's "
                "Logs, in Background tasks, opens them filtered to it), which is what to "
                "send if you report a problem. If something looks out of date or "
                "broken after an update, open Settings, Import & export and press "
                "Clear app cache: it reloads the app with fresh files and touches "
                "nothing in your notebook. Just below it, Clear and forget removes "
                "the recent searches in every search box, the saved previews, the "
                "Guide's conversation and the suggestions you dismissed, each with "
                "an Undo for ten seconds. Under the dismissed suggestions, Review them "
                "one by one lists each with its own Restore, which offers just that one again. Every setting you change is undoable too, from "
                "the toast and from Recent changes in the same section (the last twenty)."
            ),
            "badge": {"label": "Models", "section": "models"},
        },
        {
            "id": "performance",
            "keywords": (
                "slow",
                "laggy",
                "lag",
                "memory usage",
                "ram",
                "cpu",
                "speed up",
                "freeze",
                "freezes",
            ),
            "body": (
                "If the app feels slow, turn on Performance mode in Settings, "
                "Appearance: it switches off the glass, the background art and most "
                "animation. If the AI is slow, the model is the cause, not the app: it runs on "
                "this computer, so a smaller model answers faster (Settings, Models, Test my models times yours). "
                "The built-in search engine uses about 300 MB of memory "
                "while the app is open; choosing Ollama's nomic-embed-text for "
                "embeddings in Settings, Search and index keeps Tessellate itself near 100 MB."
            ),
            "badge": {"label": "Appearance", "section": "appearance"},
        },
        {
            "id": "tour",
            "keywords": (
                "tour",
                "guided tour",
                "walkthrough",
                "onboarding",
                "tutorial",
                "show me around",
                "getting started",
                "learn the app",
                "new here",
                "search help",
            ),
            "body": (
                "The guided tour walks through the whole app a section at a time, "
                "pointing at the real controls. Start it from Settings, Help and "
                "guide: Start the tour for all of it, or a part's row, its name over "
                "what it covers, to start there and carry on to the "
                "next; Back and Next move through it, and Finish ends it whenever you "
                "like. The search box under Welcome and tours in Settings, Help keeps "
                "only the topics that hold every word you type, with the words marked; Esc "
                "clears it."
            ),
            "badge": {"label": "Help", "section": "help"},
        },
        {
            "id": "personas",
            "keywords": (
                "persona",
                "personality",
                "sound like",
                "sounds like",
                "character",
                "coach",
                "analyst",
                "voice of atlas",
                "change atlas",
            ),
            "body": (
                "A persona changes how Atlas talks, not what it knows: answers stay "
                "grounded in your notes whichever one is active. Pick one in the "
                "Chat tab; edit the built-ins or write your own in Settings, "
                "Personas (New persona in the pane's bar), where {ai_name} in "
                "your text becomes Atlas's name."
            ),
            "badge": {"label": "Personas", "section": "personas"},
        },
        {
            "id": "translate",
            "keywords": (
                "translate",
                "translation",
                "translator",
                "language",
                "another language",
                "spanish",
                "french",
                "german",
                "chinese",
                "japanese",
            ),
            "body": (
                "The Writing room translates: put the text in the box and press "
                "Translate, or pick a language under Translate into in the menu "
                "beside Draft. The local model keeps every fact, name, number and "
                "the markdown, and leaves code and links alone. It needs a model "
                "connected. With no model, Translate this in the command palette "
                "turns a selected passage from English into Spanish on this "
                "computer once Translate offline is installed in Settings, Packages."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "templates",
            "keywords": (
                "template",
                "templates",
                "preset",
                "layout",
                "meeting template",
                "journal template",
                "reuse",
                "code template",
                "starter",
            ),
            "body": (
                "Capture has templates: pick one from No template above the box and "
                "the note starts with its outline. Save your own from Settings, "
                "Templates (New template in the pane's bar), where Draft with Atlas writes a template from its name "
                "and one line (press it again for another version; nothing is saved "
                "until you add it). The picker's Manage templates opens that page. A "
                "new document offers its own gallery of templates too: writing ones (a "
                "letter, report, essay, CV and one-page proposal), planning ones, "
                "and code ones that open in the code view (a Python script, a command "
                "line tool, a FastAPI endpoint, JavaScript with tests, an HTML page, a "
                "SQL schema, a README, a notebook of cells and a p5.js sketch). In a "
                'document, the "/" menu\'s Templates group inserts the writing and planning ones.'
            ),
            "badge": {"label": "Templates", "section": "templates"},
        },
        {
            "id": "tags-categories",
            "keywords": (
                "tag",
                "tagging",
                "hashtag",
                "add a tag",
                "tag a note",
                "category",
                "categories",
                "categorise",
                "categorize",
                "filing",
                "file a note",
                "file my notes",
                "files my notes",
                "refile",
                "move to category",
                "rename category",
                "organise",
            ),
            "body": (
                "Atlas files each note into a category and suggests tags. Type "
                "#word anywhere in a note to tag it as you write, and the tags "
                "field completes from the tags you use (the arrows, then Enter or "
                "Tab, take one). Change "
                "either from the note's own row (press the category or Add tags), or "
                "choose a category yourself in Capture's Filing menu; while you type, "
                "Capture offers File under a category (with the reason on hover) "
                "beside the suggested tags, and pressing it sets the Filing menu. Move a note to "
                "another category from its ... menu (Move to category) or its category chip, "
                "and to another space from the selection bar's ... menu (Move to space). The categories "
                "are the sidebar of Your notes: the arrow beside Categories, Most used "
                "or Saved searches folds that section (it stays folded), and "
                "Show empty reveals categories with no notes. Settings, Skills has Reorganise my "
                "categories and Clean up my tags for a bigger tidy."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "updates",
            "keywords": (
                "update",
                "updates",
                "upgrade",
                "new version",
                "latest version",
                "release",
                "changelog",
                "auto update",
                "version",
                "port",
                "address",
            ),
            "body": (
                "Settings, About says which version you have, the address and port "
                "the app runs at, and checks for a newer one. When a check finds one, a bar appears at the top with an "
                "Update button and a close; the Windows app installs it when you "
                "press Update, and nothing installs before that. Closing the bar "
                "hides it for that version, and Show the update bar turns it off. "
                "Choose Stable (releases only) or Main. The first start asks once "
                "whether to check for updates, and nothing is checked until you "
                "answer. A copy started with start.sh or start.bat pulls the "
                "latest code when it starts only if you turn on Pull the latest "
                "code in Settings, About. The Check for updates "
                "button checks once, whatever the switch says. Also tell me about "
                "beta versions (off by default) makes a check offer a beta or "
                "release candidate when it is the highest version."
            ),
            "badge": {"label": "About", "section": "about"},
        },
        {
            "id": "name",
            "keywords": (
                "memorymap",
                "memory map",
                "old name",
                "former name",
                "new name",
                "why the name changed",
                "tessellate",
                "called before",
            ),
            "body": (
                "Tessellate, formerly MemoryMap AI, is the same app under a new "
                "name. Only the name changed: your notes, settings, password and "
                "the folder they are kept in stay where they were, and an update "
                "keeps all of it. Settings, About shows the name and the version."
            ),
            "badge": {"label": "About", "section": "about"},
        },
        {
            "id": "notifications",
            "keywords": ("notification", "bell", "alert", "unread", "pop up", "popup", "dismiss"),
            "body": (
                "The bell in the top bar collects what happened while you were "
                "busy: reminders coming due, background jobs you started that finished, and "
                "Atlas's suggestions. The number on it is what you have not seen; "
                "the app's own jobs (a backup, housekeeping, reading a picture) stay in "
                "Settings, Background tasks unless one fails. "
                "A pop-up with a button (Undo, Open it, Show it) is kept here with "
                "the same button: an opener still works after a restart, an Undo "
                "only while it can still be undone, then its line says Undo expired. "
                "Each row has two controls at its right edge: the circle "
                "marks it read or unread, the cross removes just that one; the bin at the bottom "
                "clears them all. "
                "A reminder's row also has Done, which completes it here (a repeating "
                "one moves to its next time). "
                "Reminders also pop up on their own while a tab or the "
                "desktop app is open."
            ),
            "badge": {"label": "Dashboard", "tab": "dashboard"},
        },
        {
            "id": "code-files",
            "keywords": (
                "code",
                "coding",
                "programming",
                "python",
                "javascript",
                "syntax",
                "format code",
                "comment out",
                "emmet",
                "html",
                "css",
                "json",
                "script",
            ),
            #: The code editor's controls reference as well as its description
            #: (INBOX 410): one entry, not two, because a question about a code
            #: document is nearly always about what it can do. Written from
            #: `DOC_COMMANDS` (documents.js) and `docCodeEditing`'s keymap
            #: (documents-code.js); the chords are checked against the first.
            "body": (
                "A document can be code: give it the extension (fix.py, index.html). "
                "You get syntax colours, error underlines listed in the Problems "
                "panel, hover notes, colour swatches, indent guides and brackets "
                "that close themselves. Spelling covers comments and strings only. Completions and snippets open as you type "
                "(the Code completions topic). HTML and CSS have Emmet: type ! or ul>li*3 "
                "and press Enter or Tab; the command palette (Ctrl+K) has Emmet "
                "wrap and balance inward or outward. Keys: Shift+Alt+F formats, "
                "Ctrl+/ toggles a line comment, Shift+Alt+A a block comment, Alt+Z "
                "wraps long lines, Ctrl+G goes to a line (on a phone the bar at the foot "
                "has Tab, Undo and the brackets), F8 and Shift+F8 step through problems, "
                "Alt+Enter offers quick fixes, F12 goes to a definition, Shift+F12 "
                "lists every use, Ctrl+Shift+F finds in every document, and Go to "
                "a symbol is in the palette. Ctrl+Shift+Enter runs the file (the "
                "Running code topic) in a sandbox, its "
                "output in a panel under the editor; F5 debugs it (the Debugging "
                "code topic: F9 a breakpoint, F10 steps over, F11 while debugging "
                "steps in (Focus mode otherwise), Shift+F11 steps out, Shift+F5 "
                "stops); Stop ends it, and the panel's top edge drags its height "
                "(kept for each tab). Blocks fold from the "
                "gutter (Ctrl+Shift+[ and Ctrl+Shift+] fold and unfold, Ctrl+Alt+[ "
                "and Ctrl+Alt+] all of them). "
                "Its tabs: Output, Problems, Tests, Console (Python or JavaScript, "
                "in what the run left) and Debug. Ctrl+J shows it, Ctrl+Shift+M "
                "Problems, Ctrl+Shift+Y the Console, Ctrl+Shift+D Debug; "
                "Ctrl+Shift+P or F1 runs a command by name (words that match none offer Search notes for), Ctrl+\\ splits the "
                "editor, Ctrl+K Ctrl+S lists every key, and Outline follows the "
                "caret. Minimap (Editor and layout, "
                "off at first) maps the whole file; Compare with a saved version "
                "(palette) shows the changes inline, with Reject to put a hunk back."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "code-tabs",
            "keywords": (
                "code tabs",
                "file tabs",
                "open files",
                "open code files",
                "close file",
                "switch file",
                "several files",
                "more than one file",
            ),
            #: Written from `documents-tabs.js` (audit 1028 D52).
            "body": (
                "Code files you open stay as tabs above the editor once two are open "
                "(up to eight, kept in this browser only). Click a tab, or use the "
                "left and right arrows on one, to switch; the file you leave is saved "
                "first and reopens where you were. Close file ends the open tab and "
                "shows its neighbour, and a middle-click closes any tab. A prose "
                "document never shows the strip."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "code-completions",
            "keywords": (
                "completion",
                "completions",
                "autocomplete",
                "auto complete",
                "intellisense",
                "snippet",
                "snippets",
                "ghost text",
                "standard library",
                "stdlib",
                "signature",
                "p5 completions",
            ),
            #: Split from `code-files` when that entry passed the Guide's reply
            #: cap; written from `docCodeEditing`'s sources (documents-code.js).
            "body": (
                "Completions open as you type in a code document: Enter or Tab "
                "takes one, and the grey ghost text is taken with Tab. Snippets "
                "expand short words such as for, if, try, class, main or sout, and "
                "Tab walks their stops. In Python, a standard library module the "
                "file imports offers its names after the dot (math., os.path.), "
                "each with its signature, and pointing at one shows it. In "
                "JavaScript, a dot after console, Math, JSON or an object the file "
                "declares offers its members. In a p5.js "
                "sketch (a file with setup or draw), p5's own names are offered "
                "with their arguments."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-maps",
            "keywords": (
                "mind map",
                "mindmap",
                "mind-map",
                "branch",
                "child topic",
                "brainstorm",
                "drag to reorder",
                "reorder by dragging",
                "branch colours",
                "branch colors",
                "map font",
                "map theme",
                "palette",
                "from the library",
                "point a topic at a note",
                "link a note to a topic",
                "reference node",
                "make a mind map",
                "map from a note",
            ),
            "body": (
                "Mind maps live in the Library, under Boards & maps; New's arrow, then Mind "
                "map, opens Untitled map N with its central topic ready to type over "
                "(what you type names the map too). A note's ⋮ menu, under AI actions, Make a mind map, "
                "builds one from that note: its title in the centre, its headings and "
                "lists as branches. In Chat, an answer's Mind map this and the chat menu's "
                "Make a mind map of this chat do the same for the answer or the whole "
                "conversation. Tab adds a child, Enter a sibling, and dragging a topic "
                "onto another moves its whole branch (onto Drop here to delete, at "
                "the foot, deletes the topic and its branch); let go between two of "
                "its siblings, at the line that shows, and it takes that place. Right-click a topic for the "
                "ring of actions, where Cross-link joins any two topics. View, How this "
                "map looks sets its branch colours (eight palettes, classic first), its "
                "font, its spacing (Compact, Normal or Roomy) and the look every topic follows "
                "unless it was given its own; a "
                "topic's pickers can still pull it back to the app's own default. "
                "A topic's Add, From the library… points a new topic at a note, "
                "document, file or bookmark: a tab for each with its count (the "
                "arrows move between them; it opens on the one you used last), "
                "type to narrow the list, Down and Enter to choose. A map template "
                "(Library, Templates) dropped on a map with no central topic gets "
                "one: a template with several top-level topics goes under a new "
                "central topic named after it, and one with a single top-level "
                "topic makes that topic the centre."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
    ]
)

HELP_TOPICS.extend(TAIL_TOPICS)


#: **Every Settings section, the companion, the faces and the app's layout**
#: (INBOX 430): the second half of the reference, in its own module
#: (help_topics_more.py) so this one stays about how an answer is found.
HELP_TOPICS.extend(MORE_TOPICS)
# The speller reads the help text for the app's own vocabulary (see spelling.set_topic_source).
spelling.set_topic_source(lambda: [*HELP_TOPICS, *MORE_TOPICS])
