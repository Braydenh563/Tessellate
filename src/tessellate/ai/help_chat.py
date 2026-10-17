"""In-app guidance chat: "how do I..." answers about Tessellate itself.

ROADMAP.md item 40's "mini AI chat half", deliberately its own path,
separate from `librarian.converse`/`librarian.answer`, because those two
answer from the user's notes or hold a general conversation, and this one
must do neither: it only explains the app. Uses the utility model (not the
main chat model), its own system prompt, and a preset that is Quick's shape
(low temperature) with two differences: thinking is left to
the model rather than turned off, because the panel draws the thinking while
it happens and Quick's `think: False` made that box dead markup
(`presets.GUIDE_MODE`, which is off the user-facing picker on purpose), and
the reply cap is 640 tokens rather than 256, so a controls reference listed
in full is not cut off mid-list (INBOX 410).

**The model is the utility model, and it is the utility model's own
fallbacks that decide what that means.** `ModelManager.utility_model()`
answers the chat model in two cases: smart model routing turned off, and no
utility model chosen. Both are the documented behaviour and neither is a bug
here, but together they are why the Guide can be seen running the chat model
while every line of copy around it says "your utility model", so
`tests/test_help_chat.py` pins which model a real request takes in each of
the three cases rather than leaving it to be read off this sentence.

**Grounded, not just instructed.** A first version of this module told the
model "don't invent a feature you're not sure exists" and gave it nothing
else to go on, for a small local model that has never heard of Tessellate,
that is an instruction with no way to follow it: refusing to guess and
guessing wrong look identical from inside the prompt. `HELP_TOPICS` below is
the fix: a short, factual reference entry per feature area, and what
Settings, Help lists (drawn from this table since INBOX 448). The question is
matched against it by keyword, and whichever entries match get attached to
the prompt as the only material the model is allowed to answer from. Keeping
`HELP_TOPICS` in step with the app is what "the chatbot's information is up
to date" means in practice, and it is why this module, not the docs alone, is the thing
future sessions should re-check first when a feature's behaviour changes.

No persistence: nothing here writes to the database. The caller (the
frontend) is the one holding the running transcript, in memory only, for
exactly as long as the spec allows, this module only ever sees what it's
handed on each call.
"""

from __future__ import annotations

import functools
import math
from datetime import datetime
import re
from collections.abc import Iterator

from tessellate import SUPPORT_EMAIL
from tessellate.ai import AI_NAME
from tessellate.ai import act_registry, presets, spelling
from tessellate.ai.help_topics_more import HELP_GROUPS, MORE_TOPICS, TOPIC_META
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only: the speller reads this module's topics,
    # and importing the model manager drew in SQLAlchemy for a typed question.
    from tessellate.ai.model_manager import ModelManager
    from tessellate.ai.provider import Provider

#: **The guide's name, in one place** (INBOX 204, the owner: "give the help ai
#: a name fitting for the application like a persona and improve its
#: capabillity and knowledge"; CHAT_PLAN.md section 4 decision 15, which
#: supersedes decision 13's naming half). An atlas is a book of maps, the thing
#: you open to find your way around a place you are already standing in, which
#: is exactly what this chat is for an app called Tessellate. It is a name for a
#: reference work rather than for a person, so decision 13's actual objection
#: still holds: nothing here claims a personality, or to know the reader, or to
#: have read a word of their notebook.
#:
#: Every surface that says the name reads it from here or from
#: `GUIDE_NAME` in the frontend, because a persona whose name is typed out in
#: nine places is a persona with nine chances to be renamed in eight.
GUIDE_NAME = AI_NAME  # one name for the notebook's AI (INBOX 225), spelt once in ai/__init__

SYSTEM_PROMPT = (
    f"You are {GUIDE_NAME}, the in-app guide to Tessellate (formerly MemoryMap AI), a local-first "
    "notebook. Your name is the name of a book of maps: you are a reference "
    "the person opens to find their way around the app, and you say so if "
    "asked who you are. You answer ONLY questions "
    "about how to use the Tessellate app itself: its features, tabs, and "
    "settings. You have no access to the user's notes or documents, so if "
    "asked a question about their notebook's own content, say plainly that "
    "this chat is for app guidance only and point them to the Chat or Ask "
    "tab instead of guessing. Base your answer only on the reference notes "
    "given to you below the question, if any are given, never invent a "
    "button, setting, or feature that isn't in them. If no reference notes "
    "are given, or they don't cover the question, say plainly that you're "
    "not sure and suggest checking the Help topics above this chat instead "
    "of guessing. Keep answers short: a few sentences or a short numbered "
    "list of steps: and name the exact tab or settings section involved. "
    "Write plainly, in sentence case, with no exclamation marks and no "
    "greeting before the answer. If the person describes an error, a crash "
    "or something that does not work, add one line at the end: open "
    "Settings, then Logs, press Email it under the support bundle, and the "
    f"report goes to {SUPPORT_EMAIL} with the bundle to attach."
)

#: Kept only for anything still importing the name. The Guide no longer
#: answers with an apology when the model is off: see `offline_answer`, which
#: hands over the help text this sentence used to point at.
OFFLINE_MESSAGE = (
    f"{GUIDE_NAME} isn't available right now (the local model doesn't seem "
    "to be running): the Help topics above still work without it."
)

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
        "keywords": ("capture", "note", "template", "dictate", "sketch", "improve", "proofread", "generate title", "generate a title", "title from its words", "draft", "tag", "category", "categorise", "write", "compose"),
        "body": (
            "Notes tab: type into \"Capture a thought\" and Save. A local AI files "
            "it into a category and suggests tags; you can re-file or edit anytime. "
            "Use a template, dictate with the microphone icon, sketch with the "
            "palette icon, or run \"Improve\" to proofread first, which needs no model (rewording does). "
            "A note's ... menu has Generate title, which with no model takes the title from the "
            "note's first sentence and is named Title from its words. The Writing room has "
            "\"Split into notes\", which turns a block of pasted text into several "
            "AI-drafted, auto-linked notes."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "ask-chat",
        "keywords": ("ask", "chat", "agent", "conversation", "tool", "question", "popup agent", "everywhere", "calculate", "convert", "conversion", "units", "currency"),
        "body": (
            "\"Ask your notebook\" (Notes tab) and the Chat tab both answer from "
            "saved notes, with the raw notes shown beside the answer; in Ask, "
            "Enter asks and Escape clears the question, and the clock button "
            "answers from your notes as they were on a day you pick. Its Use AI switch "
            "picks who answers: off, the answer is From your notes, quoted from your "
            "notes' own sentences with no AI, and it is the answer when no model runs, "
            "in Ask and in Chat. "
            "Sums, conversions (at the dated rates named), the time and days "
            "until a date are worked out, model or not; \"what did I do last "
            "week\" lists that week's notes; short follow-ups (and last week?, "
            "why?, shorter, no, the gym one) read against the question before; "
            "a cited board, map or document opens in its own place. With no "
            "model, Chat also acts (remind me to..., pin or delete the X note), with Undo. "
            "A counting "
            "question in Ask (how many notes per category this month) also gets "
            "a chart from your notes, with its numbers and Save as PNG. A note's "
            "... menu has Explain this note: read aloud, then what it links to "
            "and why. Agent mode "
            "(a toggle in Chat) lets the assistant use its tools to search, link, "
            "tag, organise and create, destructive actions always ask first, "
            "and after it reads a web page or a clipped or imported note, so "
            "does every change and web request. "
            "Conversations save and rename in the sidebar; the same agent pops "
            "open over any tab with Ctrl/Cmd+Shift+A (from More on a phone), "
            "runs with no model, and Ctrl+Z takes back its last write. "
            "While an answer is coming, "
            "the line under it says what is happening: Reaching Atlas, Reading "
            "your notes, Waking the model, Atlas is thinking, Atlas is writing, "
            "or Atlas followed by the tool's name, or with no model Working it out without a model; with "
            "Progress indicators set to Still, without the dots."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "skills",
        "keywords": ("skill",),
        "body": (
            "Skills are one-click requests shown above the chat box (e.g. "
            "\"Summarise my week\"). Built-in skills ship with the app; add your "
            "own in Settings, Skills (New skill in the pane's bar opens the form). A skill can use the AI's tools, so it "
            "does the work rather than just describing it. A skill can also be "
            "a Markdown file saved in the skills folder that Settings, Skills "
            "names; it is listed without a restart. With no model running, nine built-in skills "
            "still run, read straight off your notes with no AI and labelled as such: Summarise my week, "
            "Daily review, Catch up on a topic, Find loose ends, Auto-tag my notes, Link related notes, "
            "Tidy suggestions, Notebook health check and Find notes worth combining. "
            "The others are marked (needs a model) in the Skills menu."
        ),
        "badge": {"label": "Skills", "section": "skills"},
    },
    {
        "id": "graph",
        "keywords": ("graph", "concept map", "mind map", "mindmap", "network", "connected to", "untouched since", "filter the graph"),
        "body": (
            "The Graph tab shows notes as a force-directed map, links and threads "
            "drawn between them, plus optional AI similarity lines. Search "
            "highlights matches, dragging rearranges, and the legend toggles "
            "categories on and off. Mind maps (drawn by you, not the "
            "automatic graph) are made and managed from the Library. A mind "
            "map's topics are notes, kept out of Notes and Recently added; a "
            "search finds them. After Enter names a topic, typing renames it. "
            "The Graph's search box reads filters as well as words: "
            "\"connected to Harbor\", \"untouched since June\", \"tagged work\", "
            "\"pinned\", \"with pictures\", \"edited last week\"; any other "
            "words still have to match."
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
            "Done. Add a reminder at the top of the Reminders tab: type it in plain words on the "
            "Magic add line and press the sparkle, or fill in Remind me to, the "
            "date and the time, then Add. Set a priority, snooze, edit inline, or make one recurring: "
            "\"every weekday\", \"every 2 weeks\", \"the last Friday of the month\", "
            "with an early alert such as \"1 day before\". "
            "The date and time fields open a month and the day's times, and "
            "read a typed day such as \"next friday\". "
            "You can also just say \"call mum tomorrow evening\" in a note and "
            "let the AI schedule it. In the chat, \"remind me two hours before "
            "midnight\" works too: Atlas passes your words and the app works "
            "out the time on your own clock. Notifications fire on the minute "
            "while a tab is open, even in the background, with Done and Snooze "
            "on them; the desktop app notifies with its window closed. If the "
            "browser blocks them, the list and the "
            "Notifications group in Settings say so, and their ? says how to allow them. "
            "Remind me is on a note's, a document's and a board's ⋯ "
            "menu too, and the reminder's row opens what it is about."
        ),
        "badge": {"label": "Reminders", "tab": "reminders"},
    },
    {
        "id": "dashboard",
        "keywords": ("dashboard", "widget", "streak", "digest", "my day", "what changed today", "quiet topics"),
        "body": (
            "The Dashboard is the at-a-glance home: a greeting with your note "
            "count, what is due and a pattern your notes show (a subject you "
            "keep writing about, a busy week; Tidy lists them), a search box, the Quick access tiles, "
            "and widgets such as reminders, recent notes, the Digest (your day "
            "with no AI: what is due, open questions, what changed since "
            "yesterday and topics gone quiet, each line a count or a quote that "
            "opens its note; Atlas writes the week on request), "
            "stats, your streak, Most opened this month and Filings to check. Customise, beside the search box, has Edit "
            "layout and Widgets to show, hide and rearrange them; the layout is "
            "remembered per user."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        "id": "library",
        "keywords": ("library", "bookmark", "link shelf", "contents", "outline", "search", "find", "filter", "look for", "browse"),
        "body": (
            "The Library is everything already made, in one searchable, "
            "filterable place: notes, documents, chats, files and tags, plus "
            "Bookmarks (a shelf for websites you visit often), Contents (a "
            "hyperlinked outline of the whole notebook) and AI skills. "
            "The other sub-tabs are Documents, Boards & maps (whiteboards "
            "and mind maps), Images and Files. Each sub-tab's top bar ends "
            "with a ? that says what it holds. The Highlights chip lists every "
            "passage you marked in a note, each with its note. The Activity chip "
            "lists everything you and Atlas did, and its Export activity button "
            "saves that log as a spreadsheet (when, who, what, which item) to "
            "hand over. Events about private notes are left out of it. The "
            "Library's search reads the same filters as the Graph's: "
            "\"connected to Harbor\", \"untouched since June\", \"tagged "
            "work\", \"pinned\", \"filed under Cooking\". Drop files anywhere in "
            "the app to add them: pictures and PDFs go to Images, anything "
            "else becomes a document."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "documents",
        "keywords": ("document", "editor", "markdown", "code file", "live view", "source view", "word count", "character count", "search documents"),
        "body": (
            "The document editor (opened from Library -> Documents) has four "
            "views: Live (renders as you write), Source, Split and Read. Enter "
            "in the title moves to the body. Code "
            "files get line numbers, Tab/Shift+Tab indenting and Ctrl+/ "
            "commenting. \"Check with AI\" reviews a document for wording issues "
            "a spellchecker can't catch. The menu's Map the headings turns its "
            "headings into a new mind map. A mermaid code block (flowchart TD, "
            "A --> B, or the \"/\" menu's Flowchart) draws as a diagram in Read and Live and in a print; press "
            "it to edit its text, and any other Mermaid stays as code. Print or "
            "save as PDF first asks for the page size, orientation, margins and "
            "page numbers, and a plain Ctrl+P uses the last choice. In Live, drag "
            "the corner of a picture to resize it (or focus the corner and use the "
            "arrow keys), and its align button puts it left, centre or right. "
            "The status bar counts characters, words, lines and reading time the way "
            "the note composer does (an emoji is one character). Search "
            "documents reads a window: \"harbor last week\" finds the ones "
            "about the harbor edited in the last week."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "whiteboard",
        "keywords": ("whiteboard", "sketch pad", "canvas", "freehand", "arrange as a grid", "grid of", "stack them", "sticky date", "date on a sticky"),
        "body": (
            "The whiteboard (Library, Boards & maps) is a pannable canvas for "
            "freehand sketches and note cards together. Freehand sketches also "
            "appear in the Library's Images sub-tab. A board's background colour "
            "and image are kept with the board. Board, Export saves a PNG (1x, 2x "
            "or 3x, with a transparent background if you like), SVG or PDF named "
            "after the board. Paste text from another app onto a board: a link "
            "becomes a link box, one line a text box, a list a grid of stickies. "
            "In the command palette over a board, say what to do with the "
            "selection (or the whole board): \"arrange as a grid of 3\", "
            "\"put them in a row\", \"stack them\", \"align left\", \"space "
            "them evenly\", \"same width\"; Undo takes it back. A sticky that "
            "names a day shows it as a chip at its foot; press it to set a "
            "reminder for a day still to come. Fit (Shift+1) goes into the canvas you "
            "can see, clear of an open sidebar, Format panel, top bar and tools "
            "dock, and refits when one opens or closes until you pan or zoom "
            "yourself. Drag an item to move it, or type its X and Y in the "
            "Format panel; the context bar over a selection, or the Format "
            "panel, changes its colour, line and words. Draw a link between "
            "cards with the connector (C), from one card to the other."
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
            "(no Tesseract needed); you can pick the model or leave it automatic."
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
            "as do + and - on a row. The strip under the bar walks your daily pages, and the "
            "chip under it offers On this day, and the year menu beside the month narrows the list to one year. A note that names a "
            "day (\"on Friday\") sits on that day and says All day; one that "
            "names a time too (\"on Friday at 3pm\") shows that time."
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
            "learned in Settings, What it remembers."
        ),
        "badge": {"label": "What it remembers", "section": "memory"},
    },
    {
        "id": "spaces",
        "keywords": ("space", "workspace", "separate notebook"),
        "body": (
            "A space is a separate notebook inside the same app: notes, "
            "documents, chats and tags kept apart from other spaces. Switch or "
            "create one from the picker at the top of the sidebar; \"All "
            "spaces\" shows everything together. Deleting a space asks what "
            "happens to its contents: delete everything in it, or move "
            "everything to another space (a category both have is merged)."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "appearance",
        "keywords": (
            "theme", "dark mode", "light mode", "accent colour", "accent color", "font",
            "density", "glass", "performance", "performance mode", "animation", "animations",
            "slow", "laggy", "blur",
        ),
        "body": (
            "Settings, Appearance controls theme (light/dark/system), accent "
            "colour, fonts, density, glass effects and the animated background. "
            "High-contrast and reduce-motion options are there for comfort and "
            "accessibility: Reduce motion stills Atlas, the background art, the "
            "graph and the whiteboard, and Interface animations (on by default) "
            "keeps the short fades and slides of menus, dialogs and tabs and a "
            "button's press even then; turn it off and they are instant. "
            "Font and Density (Typography & layout) are lists you pick from. "
            "Font's Readable is Atkinson Hyperlegible, a face drawn so that "
            "letters easily mistaken for each other (l, I and 1; O and 0) "
            "look different; it ships with the app and works offline. "
            "Density's Auto, the default, is Compact on a window "
            "700px tall or less and the look's own spacing on a taller one. "
            "Performance mode (Effects & accessibility) turns off "
            "the frosted-glass blur, the large animations and the animated "
            "background and slows the graph physics, for a slow or small machine; Auto "
            "switches it on by itself on a machine with 2 cores or 4 GB or fewer, "
            "and On or Off overrides that."
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
            "Press ? for the full list; Settings, Keyboard shortcuts rebinds any of "
            "them (press a shortcut's keys, then the keys you want; type in the "
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
            "Press m then a letter to jump to a tab; the panel that appears lists "
            "Go to and Do with each letter beside its name, marks the tab you are "
            "on, and takes a click as well."
        ),
        "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
    },
    {
        "id": "models",
        "keywords": ("model", "ollama", "lm studio", "vllm", "llama.cpp", "utility model", "chat model", "sampling", "temperature", "no model connected", "no model notice", "hide notice", "banner", "popup"),
        "body": (
            "Connect a model in Settings, Models, which picks the chat model and an optional smaller "
            "utility model for background jobs. Any OpenAI-compatible server "
            "works, not just Ollama, LM Studio, llama-server, Jan, vLLM. "
            "Sampling parameters (temperature, top-p, top-k, min-p, repeat "
            "penalty) are exposed there too, starting at what the model itself "
            "recommends. The No model connected banner above Ask, Chat and "
            "the writing desk can be hidden for good with Hide the \"No model "
            "connected\" notices under Model backend (saved on this device), "
            "or from the banner itself: the caret beside Connect a model has "
            "Hide these popups, and the toast that follows offers Show them "
            "again; "
            "Atlas still answers from your notes without a model."
        ),
        "badge": {"label": "Models", "section": "models"},
    },
    {
        "id": "storage",
        "keywords": ("backup", "storage", "data dir", "where is my", "export", "data folder", "import", "obsidian", "vault", "migrate", "restore"),
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
        "id": "websearch",
        "keywords": ("web search", "websearch", "internet search", "searxng", "search the web", "search online", "look it up online"),
        "body": (
            "Web search is opt-in and off by default. Turn it on in Settings, Web "
            "search: only your search words are sent out, "
            "never your notes, so the assistant can look something up online "
            "when asked. With it on and no model running, a Chat question your "
            "notes do not answer is answered from the pages found, one line a "
            "page under its title, cited by its address. The pages are in the "
            "Web results fold under the answer: each with its site and one "
            "line; press a title to read the page there, as text, with Back to "
            "results, or the arrow beside it to open it in your browser."
        ),
        "badge": {"label": "Web search", "section": "websearch"},
    },
    {
        "id": "privacy",
        "keywords": ("private note", "encrypt", "password", "lock", "security", "offline", "online", "internet", "cloud", "telemetry", "tracking", "local chip"),
        "body": (
            "Private notes are encrypted at rest with a key derived from your "
            "unlock password. The app binds to localhost, has no account or "
            "telemetry, and nothing leaves your machine unless you explicitly "
            "turn on web search. Settings, Privacy, Where your data went lists "
            "every connection the app made, recorded as it happened, Since "
            "launch or All time, one row per place with what it was for (the "
            "file downloaded, the search words); its addresses are under "
            "Addresses. \"Nothing left this computer.\" means none. The "
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
            "note, board, document, reminder or OCR reading goes to the bin, not gone "
            "for good: restore it from the Library (Filter, Include the bin, or Open "
            "the bin from Ctrl+K), or press Undo in the toast right after, which also "
            "has a Go to bin button for a note. A deleted picture or file, a past "
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
            "dictate", "dictation", "voice", "voice note", "microphone", "meeting",
            "transcribe", "recording", "recordings", "trim", "marker", "read aloud",
        ),
        "body": (
            "The microphone icon on the note composer dictates a note using "
            "local Whisper: nothing sent anywhere. \"Record a meeting or "
            "lecture\" (the command palette, Ctrl+Shift+R, or a meeting's Record "
            "into it) and \"Voice note\" keep the audio as a recording, saved "
            "every 10 seconds, even with no add-on; closing the recorder keeps "
            "it recording in a bar with Pause and Stop. The recorder's "
            "Microphone fold (and Settings, General, Microphone) chooses the "
            "input, noise suppression, echo cancellation and automatic gain, "
            "with a three-second test; Enhance on save there cuts rumble and "
            "evens the loudness, keeping the original until the transcript is "
            "saved. With the captions helper the words appear as you speak. "
            "With the Voice notes add-on it transcribes in the background (a "
            "notification says when it is done; Stop ends it) and the "
            "transcript is offered to save; saved, the recorder shows its "
            "first lines with Open. "
            "Library, Recordings plays them "
            "at 0.5 to 2x with a playhead and the time; drag the waveform to "
            "seek, press M to mark a moment with a comment, and Trim; a "
            "transcribed one lists its lines with their times (press one to "
            "play from it) and downloads them as SRT or VTT subtitles; with "
            "the AI on, each turn is labelled with who spoke, and a recording's menu has Rename a speaker to correct a name everywhere. "
            "Read-aloud plays a note or answer back to you."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    #: INBOX 644: meetings are one shape of note with a sheet of their own.
    {
        "id": "meetings",
        "keywords": (
            "meeting", "meetings", "meeting notes", "new meeting", "agenda",
            "action item", "action items", "attendees", "minutes", "standup",
            "decisions", "summarise meeting",
        ),
        "body": (
            "New meeting (the Dashboard's Quick access, the command palette, "
            "Library's Create, Tools and features) asks for a title, when and "
            "who (a title like \"Sync with Ana friday 2pm\" fills When and "
            "Who from its chips), then opens the meeting as a note with Agenda, Notes, Decisions "
            "and Action items; Start and record does the same and starts "
            "transcribing straight into its Notes (Ctrl+Shift+R records too). Write an action item as \"- [ ] Send the deck "
            "@Sam by Friday\": @Name is its owner, the plain words its due. "
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
            "background librarian", "auto tag", "auto-tag", "auto link",
            "auto-link", "dedupe", "duplicate", "autonomous",
            "on its own", "by itself", "without me",
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
            "atlas", "guide", "who are you", "what are you", "your name",
            "yourself", "what can you do", "what do you do",
            #: The exact words under this panel's own '?' (`ATLAS_PROMPTS`,
            #: "help-chat-help"). A suggestion the corpus cannot answer is the
            #: worst kind of dead end, which is why
            #: `test_every_question_the_app_offers_to_ask_atlas_is_answerable`
            #: now reads that table against this one (INBOX 304).
            "what can you help", "help me with",
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
            "conversation is gone on reload, and \"New chat\" clears it now. "
            "It is reachable from the status bar on every tab, from the head "
            "of every Settings pane, from the command palette (Ask the Guide), "
            "from the Help pane in Settings and, on a phone, from More. An answer's "
            "open button lands on the control it is about, ringed."
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
            "the keyboard. It does not list your notes or documents: type "
            "what you are looking for and its last row, Search everything "
            "for, opens Find anything (Ctrl/Cmd+P) with the words already "
            "searched. Typed words also find every feature in Tools and "
            "features, every act Chat does (it opens Chat with the words "
            "started) and the matching settings, by what the words mean too "
            "(\"trash\" finds the bin, \"keybord\" the shortcuts); a word a "
            "letter out offers the nearest, and what you ran for the same words comes first "
            "next time (hover a row to see why it is where it is). "
            "It's a different box from the popup agent "
            "(Ctrl/Cmd+Shift+A): this one runs fixed commands, that one "
            "answers and acts on an open-ended request. Typed as a "
            "reminder (\"remind me friday 9 dentist\"), its first row is "
            "that reminder, with its chips under the box."
        ),
        "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
    },
    {
        "id": "extract-notes",
        "keywords": ("extract notes", "rough thoughts", "writing room", "draft"),
        "body": (
            "Split into notes, in the More menu of the Writing room (Notes "
            "tab), turns a block of pasted free text into several AI-drafted, "
            "auto-linked notes instead of one long one. The Writing room is "
            "for turning rough, unstructured thoughts into a proper note "
            "before it's saved. A document's menu and a selection of cards on "
            "a board have Extract notes, which does the same for a document "
            "or for those cards."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "favourites",
        "keywords": ("favourite", "favorite", "star", "starred", "pin", "pinned"),
        "body": (
            "Starring a note makes it a favourite, a parallel way to keep "
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
            "ocr", "read text", "scan", "scanned", "extract text", "transcribe",
            "tesseract", "vision model", "page read", "pdf text",
        ),
        "body": (
            "OCR workspace: open any image or PDF from the Library or a note and "
            "choose \"Read text\", or open it from Commands, Find anything or "
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
            "that tell you where on the page each block sits; the workspace "
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
            "history", "version", "revision", "restore", "undo edit", "previous version",
            "git log", "rollback", "ai edit log", "old version", "earlier version",
            "what it used to say", "roll back", "named version", "name this version",
            "compare versions", "side by side",
        ),
        "body": (
            "Documents keep a history. The ... menu -> History lists every "
            "version the document has had, newest first, with who changed it "
            "(you, an AI edit, or a restore), how many words it gained or lost, "
            "and the opening of that version. Name this version keeps the text as "
            "it stands under a name (Named shows only those; a row's ... menu "
            "renames one). \"Changes\" shows a version side by side with the one "
            "after it on a wide window. \"View\" reads an old version "
            "without changing anything; \"Restore\" puts it back at once and keeps "
            "the version it replaced: Ctrl+Z or the toast's Undo returns the text "
            "you had. Rename, archive, a detached note or link and a dictionary "
            "word undo the same way. A stretch of "
            "editing counts as one entry rather than one per autosave. The AI "
            "panel has a separate \"AI edits\" log for reverting one specific "
            "suggestion the model made."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "writing-checks",
        "keywords": (
            "spelling", "spellcheck", "suggestion", "proofread", "grammar",
            "dictionary", "rephrase", "wording", "autocorrect", "flagged",
        ),
        "body": (
            "The document editor checks spelling, spacing and sentence length as "
            "you write, and grammar (agreement, a or an, its or it's) with Harper, "
            "a grammar checker that runs on this computer; note boxes get the "
            "grammar check too, and the dictionary dialog turns it off. It also "
            "checks accessibility: a skipped heading level, an image with no "
            "description, link text like \"click here\". In Live "
            "view a flagged word is underlined: click or "
            "right-click it for corrections, \"Add to dictionary\" or \"Ignore "
            "this for now\". The Suggestions panel lists every finding; clicking "
            "one scrolls to it and opens its answers, the check on a row accepts "
            "its one clear fix and the crossed eye ignores it, and the arrow keys "
            "walk the rows. Fix applies every clear fix at once; the ... in the "
            "panel's head holds Check with AI, the Dictionary and which side the "
            "panel docks on. Where there is no "
            "mechanical fix, an awkward sentence, \"Ask the AI for wordings\" "
            "has the local model offer two or three alternatives to pick from. "
            "Nothing is changed until you choose it. Manage the dictionary and "
            "the British/American spelling preference from the editor's own "
            "dictionary dialog."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "notebook-questions",
        "keywords": (
            "how many", "most common", "statistics", "stats", "count", "top tags",
            "busiest", "untagged", "orphan", "most linked",
            "abbreviation", "acronym", "stand for", "short for",
            "summarise this", "summarize this", "tl;dr", "what's in",
        ),
        "body": (
            "You can ask about the notebook itself, not just what is in it: "
            "\"what are my most common tags\", \"which categories have the most "
            "notes\", \"how many notes do I have\", \"how many notes have no "
            "tags\", \"which are my most linked notes\", \"when do I write "
            "most\". These are counted from your data rather than generated, so "
            "the numbers are exact, the answer is instant, and it works even "
            "with no AI model running at all. Private and binned notes are never "
            "counted. Your own abbreviations are learned the same way: when a "
            "note names Cloud Computing beside CC, asking about CC finds both, "
            "and \"what does CC stand for?\" says which note told it. "
            "\"Summarise this\" sums up the note you have open, or the "
            "category the sidebar is filtered to; \"summarise Travel\" reads "
            "every note in that category."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "contradictions",
        "keywords": (
            "contradict", "contradiction", "tension", "disagree", "conflict",
            "inconsistent", "changed my mind", "out of date",
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
    "capture": ("take notes", "take a note", "make notes", "write notes", "new note", "quick note", "quick thought", "write a note", "make a note", "jot", "without filing", "save a note", "create a note", "create a new note", "add a note"),
    "ask-chat": ("talk to", "citation", "cite", "sources", "answer from my notes", "ask atlas", "chat with"),
    "skills": ("automate", "automation", "reorganise", "reorganize", "reorganising", "reorganizing", "workflow", "routine"),
    "graph": ("see how", "visualise", "visualize", "unlinked", "dotted line", "connections map"),
    "reminders": ("remind", "remind me", "due", "alarm"),
    "dashboard": ("home", "home page", "start page", "compact", "rearrange", "numbers on the dashboard"),
    "library": ("all my files", "old chat", "chats", "everything i have", "my files"),
    "whiteboard": ("board", "draw", "drawing", "sticky", "sticky note", "pen", "infinite canvas"),
    "files-images": ("picture", "pic", "attach", "attachment", "upload"),
    "timeline": ("journal", "diary", "daily note", "today's note", "last month", "last week", "what i wrote"),
    "memory": ("forget", "remembers", "about me"),
    "spaces": ("separate", "work and personal", "personal notes", "different notebooks"),
    "statusbar": ("dot", "bottom corner", "at the bottom"),
    "models": ("ai model", "llm", "connect a model", "turn off the ai", "without the ai", "no ai", "local model", "which model"),
    "storage": ("where is my data kept", "back up", "disk space", "disk", "where is my data", "data stored", "export everything", "move my notes"),
    "websearch": ("internet", "web", "google", "browse the web", "search the internet", "search online"),
    "privacy": ("private", "leave my computer", "left my computer", "left this computer", "where your data went", "data leave", "sent anywhere", "privacy", "spy"),
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
                "write for me", "write with atlas", "writing room", "draft a note",
                "rewrite", "continue the draft", "bullets to prose", "prose to bullets",
                "write an essay", "write an email", "draft",
            ),
            "body": (
                "Notes tab, Writing room: pick what to write (draft a note, "
                "continue or rewrite the draft, bullets to prose, prose to bullets, "
                "or translate), add notes as sources if you want it grounded in "
                "them, and press Write. The draft stays in the box to edit; save it "
                "as a note when it reads right. Which model writes is set on the "
                "same row, or in Settings, Models."
            ),
            "badge": {"label": "Writing room", "tab": "notes"},
        },
        {
            "id": "security",
            "keywords": ("password", "lock", "locked", "lock screen", "security", "sign in", "log in", "private note", "encrypt", "forgot password", "recovery key", "idle", "pin", "quick unlock", "windows hello"),
            "body": (
                "Settings, Account & security: set a password and the notebook "
                "asks for it when it opens. The lock button in the top bar locks it "
                "now, and it locks itself after the idle time you choose there. "
                "While it is locked, an open dialog or popover is put away, and "
                "it comes back as it was after you unlock. "
                "Private notes are encrypted with that password and are never sent "
                "to the AI, so a private note's menu has no AI actions. Forgot it? "
                "Press Forgot your password? on the lock screen, on this computer: "
                "with a recovery key (made at setup or in Account & security) you "
                "set a new one and keep private notes; without it, a reset keeps "
                "everything else and leaves private notes sealed. PIN for this "
                "computer: Set up a PIN for this computer (your password, then a "
                "PIN of 4 to 12 digits twice) lets the lock screen take the PIN "
                "or your password, on this computer only; phones always need the "
                "password. The computer's own protected store keeps it, never the "
                "notebook or a backup. Five wrong PINs, a password change or "
                "Forget PIN remove it."
            ),
            "badge": {"label": "Account & security", "section": "account"},
        },
        {
            "id": "search",
            "keywords": ("search", "find", "find anything", "look for", "filter", "where did", "locate", "ctrl p", "operator", "search my notes", "saved search", "search chats"),
            "body": (
                "Find anything (Ctrl+P, or the search box on the dashboard) looks "
                "through notes, documents, boards, mind maps, files, links, reminders, "
                "chats and recordings (by title and by what was said) at once, by your words and by meaning; each result wears "
                "its kind, and the chips narrow it to one. Operators: tag:work, "
                "in:work for a space, kind:chat, before:2026-01, after:2025-06-30, "
                "has:image, is:pinned, a \"quoted phrase\", and -word to leave something "
                "out. The star saves a search as a row in the Notes sidebar. A small typo that "
                "finds nothing is searched as the nearest word your notes use, "
                "and the line says \"showing results for\" it. When nothing matches, "
                "it says what was searched and offers one way on: every kind, a "
                "spelling, or the nearest feature. To narrow only the "
                "notes list, use Filter notes on the Your notes tab. Every search box "
                "suggests as you type: your recent searches first, then note titles, "
                "tags and categories that start with your words (a Library list's box: "
                "that list's own titles), with the best match in grey (Tab or Right takes it, Down and Up walk the list, Esc closes it). "
                "A recent search has its own x, the list's foot clears them, Settings, "
                "Import & export, Clear and forget clears every box's at once, and Settings, "
                "General, Search turns the suggestions off."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "links",
            "keywords": ("link", "linked", "linking", "connect", "connection", "backlink", "wiki link", "link two notes", "related notes", "find links", "suggested links", "why suggested", "suggestions", "merge names", "same person", "link type", "kind of link", "part of", "link properties"),
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
                "sentence each linking note says it in, and \"Mentioned, not "
                "linked\" with a Link button (greyed out, with the reason, for a "
                "note whose opening line has a square bracket in it, which a "
                "[[link]] cannot hold). Suggestions (Find links to add on the "
                "Dashboard's Loose ends, Suggest links in the Graph's options, or "
                "the command palette) is one sheet of four kinds: Links lists pairs "
                "worth connecting with every reason (similar wording, people or "
                "things both name, a note both link with, a rare tag both carry) "
                "and how sure it is (Link all above 70% in the head links every pair at "
                "least that sure, after asking); Tensions, notes that may disagree; Names, one "
                "person or thing named two ways, with Merge; and Link types, a link whose own "
                "sentence says \"for example\" or \"continues\". Accepting or "
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
            "keywords": ("not working", "isnt working", "doesnt work", "broken", "error", "no model", "cant connect", "cannot connect", "stuck", "crash", "fails", "logs", "not answering", "isnt answering", "not replying", "doesnt answer", "get an error", "out of date", "looks wrong", "clear cache", "clear the cache", "app cache", "stale", "after an update"),
            "body": (
                "If Atlas does not answer, open Settings, Models: it says whether a "
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
                "an Undo for ten seconds. Every setting you change is undoable too, from "
                "the toast and from Recent changes in the same section (the last twenty)."
            ),
            "badge": {"label": "Models", "section": "models"},
        },
        {
            "id": "performance",
            "keywords": ("slow", "laggy", "lag", "memory usage", "ram", "cpu", "speed up", "freeze", "freezes"),
            "body": (
                "If the app feels slow, turn on Performance mode in Settings, "
                "Appearance: it switches off the glass, the background art and most "
                "animation. The built-in search engine uses about 650 MB of memory "
                "while the app is open; choosing Ollama's nomic-embed-text for "
                "embeddings in Settings, Search and index keeps Tessellate itself near 100 MB."
            ),
            "badge": {"label": "Appearance", "section": "appearance"},
        },
        {
            "id": "tour",
            "keywords": ("tour", "guided tour", "walkthrough", "onboarding", "tutorial", "show me around", "getting started", "learn the app", "new here", "search help"),
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
            "keywords": ("persona", "personality", "sound like", "sounds like", "character", "coach", "analyst", "voice of atlas", "change atlas"),
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
            "keywords": ("translate", "translation", "translator", "language", "another language", "spanish", "french", "german", "chinese", "japanese"),
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
            "keywords": ("template", "templates", "preset", "layout", "meeting template", "journal template", "reuse", "code template", "starter"),
            "body": (
                "Capture has templates: pick one from No template above the box and "
                "the note starts with its outline. Save your own from Settings, "
                "Templates (New template in the pane's bar), where Draft with Atlas writes a template from its name "
                "and one line (press it again for another version; nothing is saved "
                "until you add it). The picker's Manage templates opens that page. A "
                "new document offers its own gallery of templates too: writing ones, "
                "and code ones that open in the code view (a Python script, a command "
                "line tool, a FastAPI endpoint, JavaScript with tests, an HTML page, a "
                "SQL schema, a README, a notebook of cells and a p5.js sketch)."
            ),
            "badge": {"label": "Templates", "section": "templates"},
        },
        {
            "id": "tags-categories",
            "keywords": ("tag", "tagging", "hashtag", "add a tag", "tag a note", "category", "categories", "categorise", "categorize", "filing", "file a note", "file my notes", "files my notes", "refile", "move to category", "rename category", "organise"),
            "body": (
                "Atlas files each note into a category and suggests tags. Type "
                "#word anywhere in a note to tag it as you write, and the tags "
                "field completes from the tags you use (the arrows, then Enter or "
                "Tab, take one). Change "
                "either from the note's own row (press the category or Add tags), or "
                "choose a category yourself in Capture's Filing menu; while you type, "
                "Capture offers File under a category (with the reason on hover) "
                "beside the suggested tags, and pressing it sets the Filing menu. The categories "
                "are the sidebar of Your notes. Settings, Skills has Reorganise my "
                "categories and Clean up my tags for a bigger tidy."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "updates",
            "keywords": ("update", "updates", "upgrade", "new version", "latest version", "release", "changelog", "auto update", "version"),
            "body": (
                "Settings, About says which version you have and checks for a newer "
                "one; the Windows app can download and install it for you. Choose "
                "Stable (releases only) or Main. The first start asks once whether "
                "to check for updates automatically, and nothing is checked until "
                "you answer. A copy started with start.sh or start.bat then "
                "updates itself when it starts, following the same setting, and "
                "turning automatic updates off stops it. The Check for updates "
                "button checks once, whatever the switch says. Also tell me about "
                "beta versions (off by default) makes a check offer a beta or "
                "release candidate when it is the highest version."
            ),
            "badge": {"label": "About", "section": "about"},
        },
        {
            "id": "name",
            "keywords": ("memorymap", "memory map", "old name", "former name", "new name", "why the name changed", "tessellate", "called before"),
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
                "busy: reminders coming due, background jobs that finished, and "
                "Atlas's suggestions. The number on it is what you have not seen. "
                "A pop-up with a button (Undo, Open it, Show it) is kept here with "
                "the same button: an opener still works after a restart, an Undo "
                "only while it can still be undone, then its line says Undo expired. "
                "Each row has two controls at its right edge: the circle "
                "marks it read or unread, the cross removes just that one; the bin at the bottom "
                "clears them all. "
                "Reminders also pop up on their own while a tab or the "
                "desktop app is open."
            ),
            "badge": {"label": "Dashboard", "tab": "dashboard"},
        },
        {
            "id": "code-files",
            "keywords": ("code", "coding", "programming", "python", "javascript", "syntax", "format code", "comment out", "emmet", "html", "css", "json", "script"),
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
                "wraps long lines, F8 and Shift+F8 step through problems, "
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
                "Ctrl+Shift+P or F1 runs a command by name, Ctrl+\\ splits the "
                "editor, Ctrl+K Ctrl+S lists every key, and Outline follows the "
                "caret. Minimap (Editor and layout, "
                "off at first) maps the whole file; Compare with a saved version "
                "(palette) shows the changes inline, with Reject to put a hunk back."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "code-completions",
            "keywords": (
                "completion", "completions", "autocomplete", "auto complete", "intellisense", "snippet",
                "snippets", "ghost text", "standard library", "stdlib", "signature", "p5 completions",
            ),
            #: Split from `code-files` when that entry passed the Guide's reply
            #: cap; written from `docCodeEditing`'s sources (documents-code.js).
            "body": (
                "Completions open as you type in a code document: Enter or Tab "
                "takes one, and the grey ghost text is taken with Tab. Snippets "
                "expand short words such as for, if, try, class, main or sout, and "
                "Tab walks their stops. In Python, a standard library module the "
                "file imports offers its names after the dot (math., os.path.), "
                "each with its signature, and pointing at one shows it. In a p5.js "
                "sketch (a file with setup or draw), p5's own names are offered "
                "with their arguments."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-maps",
            "keywords": (
                "mind map", "mindmap", "mind-map", "branch", "child topic", "brainstorm",
                "branch colours", "branch colors", "map font", "map theme", "palette",
                "from the library", "point a topic at a note", "link a note to a topic", "reference node",
                "make a mind map", "map from a note",
            ),
            "body": (
                "Mind maps live in the Library, under Boards & maps; New, then Mind "
                "map, opens Untitled map N with its central topic ready to type over "
                "(what you type names the map too). A note's ⋮ menu, Make a mind map, "
                "builds one from that note: its title in the centre, its headings and "
                "lists as branches. Tab adds a child, Enter a sibling, and dragging a topic "
                "onto another moves its whole branch (onto Drop here to delete, at "
                "the foot, deletes the topic and its branch). Right-click a topic for the "
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

#: **A controls reference per surface** (INBOX 410, the owner: "what if the
#: user asks the guide for all the hidden features, keybinds, controls,
#: utility and more for features like the whiteboard, mindmap and documents
#: editor etc. can it answer those??"). It could not: the entries above say
#: what each surface is, in a paragraph, and a question about its keys found
#: that paragraph or the generic shortcuts entry. Each entry below is written
#: from the surface's own code, not from memory of it: its keydown handlers
#: and shortcut tables (`WB_TOOL_KEYS` and the board's keydown handler in
#: whiteboard.js, `DOC_COMMANDS` in documents.js, the graph box's keydown in
#: graph.js), the menus' own labels in index.html, and the help panels the
#: surfaces already show. Dense on purpose: offline, the entry *is* the
#: answer, and a list of keys cut short is a list that is wrong.
#:
#: Their keywords are the words only a controls question uses ("lasso",
#: "emmet", "cross-link", the chords themselves). The surface's own name is
#: deliberately not among them, so "what is the whiteboard" still reaches the
#: one-paragraph entry; `_CONTROLS_FOR` and `_CONTROL_INTENT` below are what
#: send "what are the whiteboard shortcuts" here instead.
HELP_TOPICS.extend(
    [
        {
            "id": "whiteboard-controls",
            "keywords": (
                "lasso", "highlighter", "eraser", "connector", "snap to grid",
                "snap", "grid", "pan", "zoom", "zoom to fit",
                "board overview", "find a card", "find and replace", "replace all", "tool",
            ),
            "body": (
                "Whiteboard keys (Library, Boards & maps; Ctrl+Shift+B opens it). "
                "Tools: V or S select, H hand, K lasso, P pen, M highlighter, E "
                "eraser, B fill, L line, A arrow, R rectangle, O circle, G "
                "triangle, D diamond, T text, N sticky note, F frame, C connector (Shift+C "
                "curved), I image, X delete. The Shapes button's flyout also has a rounded "
                "rectangle, ellipse, hexagon, parallelogram, star, cylinder, cloud, speech "
                "bubble and block arrow. Moving around: the wheel or two "
                "fingers pan, Shift+wheel pans sideways, Ctrl+wheel or a pinch "
                "zooms, Space and drag pans, a drag to an edge pans, Ctrl+= and Ctrl+- zoom, "
                "Ctrl+0 is 100%, Shift+1 fits all, Shift+N shows the "
                "overview, / or Ctrl+F finds, Ctrl+H replaces, and Tab walks the board's "
                "items. Selection, menus and presenting are in Whiteboard selection and menus."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "whiteboard-selection",
            "keywords": (
                "nudge", "align", "align shapes", "align on the whiteboard", "distribute", "bring forward", "send backward", "group",
                "ungroup", "copy style", "paste style", "text in a shape", "label a shape",
                "frame", "frames", "section", "region", "lock a shape", "lock an item", "unlock all", "locked item",
                "comment on a card", "comment on an item", "comments on the board", "comment thread",
                "present", "presentation", "slides", "slideshow", "laser", "laser pointer",
                "drag to delete", "drop to delete", "drag onto delete", "trash an item",
                "alignment guides", "smart guides", "size while drawing",
                "board on a phone", "more board commands", "whiteboard keys", "whiteboard shortcuts",
            ),
            "body": (
                (
                    "Whiteboard selection and menus. Selection: Shift+click adds, Ctrl+A selects all, Ctrl+D "
                    "duplicates, Alt and drag copies as you drag, Ctrl+V pastes at the pointer, the arrows "
                    "nudge (Shift for further), Shift and drag keeps to one axis, Shift and a corner keeps "
                    "proportions, Alt resizes from the centre; a move, resize or box drawn out shows guides "
                    "and its size (Alt: none), [ and ] move one step back or forward, Ctrl+[ and Ctrl+] to "
                    "the back or front, Ctrl+G groups, Ctrl+Shift+G ungroups, Ctrl+Alt+C and Ctrl+Alt+V copy "
                    "and paste a style, Delete (or a drop on the bin) removes, Esc cancels a drag or goes to "
                    "Select. Double-click empty board for a text box, double-click a closed shape (or select "
                    "it and press Enter) to write in it, right-click (or hold on touch) for the menu, double-"
                    "click a line to bend it, and select a connector and press Label in its bar (or Enter) to"
                    " label it. A frame's title drags it and what is inside it (Ctrl: the frame alone); its "
                    "menu exports it or fits it to its contents, and a double-click on one of its resize "
                    "handles fits that edge (a corner, two) to what it holds, with a margin. Ctrl+Shift+L "
                    "locks the selection; Unlock is on the board's right-click menu. Right-click an item, "
                    "Comment…, starts a thread; its count reopens it. View, Present frames: one frame at a "
                    "time; ? shows every key; Ctrl+K finds any board action by name. Menus: Insert, Edit, "
                    "Arrange (align, distribute, size, order, group, lock), View (panels, background, grid, "
                    "snap, zoom; full screen on a phone) and Board (rename, new, export, kind, clear, delete,"
                    " keys)."
                )
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-history",
            "keywords": (
                "board history", "history of the board", "time machine", "earlier version of the board",
                "go back in time", "put the board back", "restore the board", "what did the board look like",
                "snapshot", "snapshots", "named version", "save a version of the board",
            ),
            "body": (
                "Board, History… (or Ctrl+K, History) puts a slider at the foot of the board. Drag it "
                "back, or press Left, Home and End, and the board is drawn as it was at each moment, a "
                "moment being a run of changes up to two minutes long; the bar says when and what it "
                "added, changed and removed. Nothing can be changed while the past is shown. Put back "
                "restores the whole board as it was then, and the second button only what was selected "
                "when History opened; either is one Undo step and is in the history too. Esc, or the "
                "slider's right end, comes back to now. Changes older than ninety days may be kept only "
                "in summary, and such a moment cannot be shown. Board, Snapshots… names the board as it is "
                "now (Snapshot and the time unless you type a name); each one shows its picture, and "
                "Restore puts the board back as one Undo step."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-templates",
            "keywords": (
                "new board", "board templates", "map templates", "start from a template", "template picker",
                "kanban", "weekly planner", "roadmap", "project brief", "okr", "okrs", "swot", "eisenhower",
                "pros and cons", "lean canvas", "five whys", "5 whys", "fishbone", "meeting notes",
                "retrospective", "cornell", "study notes", "mood board", "journey map", "brainstorm",
                "project plan", "goal breakdown", "weekly review", "essay outline",
            ),
            "body": (
                "New, Whiteboard (the Boards and maps dock) opens Untitled board N, its name ready to type "
                "over in the top bar (Enter keeps it, Escape the old one). New, From a template (or Board, "
                "New board) opens one dialog: Board or Mind map in the tab "
                "strip under its title, the name, then the templates grouped by purpose (Plan and track, "
                "Weigh and decide, Find the cause, Meet and review, Study and create, then your own), each "
                "with its picture, and the chosen one drawn larger beside the list. A click chooses; Create, "
                "Enter or a double click makes it. A board's seventeen: Kanban, Weekly planner, Roadmap, "
                "Project brief, OKRs, SWOT analysis, Eisenhower matrix, Pros and cons, Lean canvas, 5 whys, "
                "Fishbone, Flowchart, Meeting notes, Retrospective, Study notes (Cornell), Mood board and User "
                "journey map. Each frame is a tinted panel with its title and a hint inside its top; drag the "
                "title to move the frame and what is in it, double-click it to rename. A map's fifteen, "
                "among them Brainstorm, Decision, Project plan, Cause and effect, Pros and cons, SWOT map, "
                "Goal breakdown, Weekly review, Study topic, Book notes and Meeting, each drawn in its own "
                "shape; the new map's central topic is its name, laid out the way the picture shows (a "
                "brainstorm round its centre, pros and cons both ways, a fishbone to the left). A new map "
                "that is still just its root offers the same templates as pictures, Start from a template; "
                "the X hides it for that map."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-library",
            "keywords": (
                "object library", "shape library", "shapes", "flowchart", "flow chart", "icons", "stencil",
                "draw.io shapes", "bpmn", "network shapes", "cloud shapes", "connection points",
                "preset", "template", "favourite shapes", "recent shapes", "sidebar", "layers", "pages", "named layer", "hide a layer", "lock a layer",
                "page order", "presentation order", "reorder frames", "order of frames", "frame order",
                "frames in the presentation", "locked item", "unlock",
                "drag a template", "map templates", "this map tab", "map stats",
            ),
            "body": (
                "A board's sidebar (the Library button in its top bar, or the rail on its left edge) has "
                "four tabs: Library, Notes, Layers and Pages; a mind map's has Library, This map (its "
                "facts, its look, open every fold, lay it out again) and Outline. The Library starts with "
                "Templates (17 for boards, 15 for maps; see Board and map templates). Pages lists the "
                "board's frames in presentation order: drag a row or press Alt+Up and Alt+Down to reorder, "
                "Enter goes to the frame, P presents from it, double-click or F2 renames it, and its ⋯ menu has more. "
                "Layers starts with named layers: + adds one "
                "holding the selection; its eye and lock act on all of it. Tinted rows are selected on the board "
                "(the head counts them; Clear drops them), and a frame lists what it holds under its row. A locked item shows a lock when the pointer "
                "is on it; right-click it to unlock it. The Library holds "
                "built-in sets (General shapes, Flowchart, Arrows, Frames (a frame, a timeline lane and swimlanes in rows or columns) "
                "and 1,530 icons drawn as shapes), five draw.io sets (196 shapes "
                "with their own connection points), then Favourites, Recent and your own "
                "libraries; the search field finds any of them by name or tag. Click a tile or press Enter "
                "to place it in the middle of the view, drag it and it lands held where you grabbed it, or Shift+Enter to place "
                "it joined to what is selected; F stars it, and Shift+F10 or a right-click opens its menu "
                "(rename, tags, duplicate, move, delete). Saving your own is in Saving to the library."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-library-saving",
            "keywords": (
                "save to library", "save to the library", "my shapes", "custom shape", "saved style", "palette",
                "saved branch", "import library", "export library", "save as template", "board template",
                "templates in the library", "save my own shape", "save a shape to the library",
                "save a board as a template", "board as a template",
            ),
            "body": (
                "Saving to the library. To save your own: select things and press "
                "Ctrl+Shift+S, or right-click, Library, for a selection, a drawn shape, a style, a sticky "
                "or text preset, a palette of the selection's colours, or on a mind map a branch; Board, "
                "Save this board as a template keeps the whole board. New board then offers your templates "
                "beside the built-in ones. The library's ⋮ makes a new library, imports a library file and "
                "exports one. A placed item is an ordinary copy: changing the library later never changes "
                "a board. In Agent mode the assistant can search the library and place from it, draw "
                "shapes and frames, and move, edit or delete what is on a board, asking first."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-format",
            "keywords": (
                "format panel", "format", "exact position", "position", "x and y", "width and height",
                "angle", "rotate by", "flip", "mirror", "opacity", "transparency", "see through", "shadow",
                "text size in a shape", "align text",
                "line shape", "line end", "line ends", "arrowhead", "arrow end", "diamond end", "label position",
                "arrow size", "end size", "bigger arrowhead", "stealth arrow", "memorymap arrow", "signature arrow",
                "reset style", "default style", "reset an object", "back to default",
                "line jumps", "line jump", "crossing lines", "lines cross", "hop over",
            ),
            "body": (
                "Ctrl+Shift+P on a board (or Format panel in the selection's More menu, or View) opens "
                "the Format panel on the right, with three tabs. Style: line colour, width and pattern, "
                "fill, opacity, shadow, and for a connector its line shape (curved, straight or elbow), "
                "its line jumps (where it crosses a line under it, it hops over with an arc, a gap or a "
                "sharp peak), its two ends (twenty-one marks, from the Tessellate end, the mark's node dot ahead of a chevron, through open, "
                "filled, stealth, half and double arrows, circles and diamonds to a cross, a bar and a crow's foot, each drawn in its "
                "list, each small, medium or large in the menu beside it; a plain line takes them too) and where its label sits along it. Text: the size, colour, weight, "
                "alignment and vertical place (top, middle, bottom) of a text box or a shape's words. Arrange: X, Y, width, height and "
                "angle as numbers, flip, and the order, align, spacing, group and lock buttons. With "
                "several items selected it shows what they all share, and a value they differ on reads Mixed. Every "
                "change is one undo step, across the whole selection. Reset style (the item's right-click menu, its ... menu "
                "or Ctrl+K) puts colour, fill, line and text back to the defaults, its words, place and ends kept. "
                "Colours are in Fill, border and recent colours. Bends, connection points and imports are in Connector bends and importing."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-connectors",
            "keywords": (
                "elbow", "right angle", "orthogonal", "connector shape", "bend", "waypoint",
                "crow's foot", "crows foot", "er diagram", "connection point", "connection points", "port", "ports",
                "anchor point", "entity relationship", "mermaid", "subgraph", "sequence diagram", "class diagram",
                "state diagram", "drawio", "draw.io file", "open a drawio file", "import a flowchart",
                "clone and connect", "copy and connect", "next shape", "copy a shape",
                "connect it to the copy", "connect the copy", "new note next to", "arrows round a card",
            ),
            "body": (
                "Connector bends and importing. Every connector takes bends: drag the small ring in the middle "
                "of a run (or double-click the line) to add one, drag a bend to move it, double-click it to "
                "take it out. A straight line runs through its bends, a curved one curves smoothly through "
                "them, and an elbow turns at right angles and goes round the shapes it joins; changing the "
                "line shape keeps the bends; moving both things a connector joins moves its bends too. "
                "With Select, pointing at a shape, card or text box shows its connection points (a "
                "diamond's tips and side middles, an ellipse's compass points); drag from one to draw an "
                "elbow connector to whatever you let go on, or to a free end. "
                "Drag the square on a connector's label to slide "
                "it along the line. The ends include the entity-relationship marks (one, zero or one, many, "
                "one or many, zero or many). With one shape or text box selected, the four arrows round it "
                "(or Alt+Shift and an arrow key) copy it that way and join facing sides with an elbow; "
                "a note card's arrows make a new note there instead, joined and ready to type. "
                "Insert, Mermaid, draw.io or board SVG brings in a Mermaid flowchart, state, class or "
                "sequence diagram, a .drawio file (pages and swimlanes as frames) or an SVG a board "
                "here exported, as shapes and connectors; Export writes an Outline and a Mermaid flowchart."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-controls",
            "keywords": (
                "cross-link", "cross link", "outdent", "fold", "unfold", "radial",
                "ring", "opml", "freemind", "colour by", "color by", "focus on a branch",
                "tidy", "layout of the map", "duplicate a topic", "copy a topic",
                "undo steps", "how many undo", "topic before", "topic after",
                "move a topic", "reorder topics", "checkbox on a topic", "topic a task",
                "tick a topic", "number the branches", "numbered topics", "outline numbers", "note on a topic", "note behind a topic", "comment on a topic", "boundary", "summary topic", "summarise topics",
                "resize a topic", "topic size", "bigger topic", "text size on a topic", "topic bar", "topic toolbar",
                "several topics", "select several topics", "many topics at once", "bold several topics", "fold several branches",
                "show levels", "fold to a level", "only the first levels", "collapse to level",
                "summarise this branch", "summarize this branch", "summary of a branch",
            ),
            "body": (
                "Mind map keys (a map lives in the Library under Boards and "
                "maps). With a topic selected: Tab adds a child, Enter adds a "
                "topic right after it and Shift+Enter right before it (what you "
                "type next is the new topic's words), Ctrl+D copies it as the "
                "next sibling, Ctrl+Shift and the arrows move it among its "
                "siblings, Shift+Tab outdents it, the arrow keys walk the tree, "
                "F2 or double-click renames (while typing, Enter breaks the line, Esc "
                "keeps the name, Tab or Ctrl+Enter adds the next topic, / and [[ add "
                "links), Delete removes the topic and "
                "everything under it, C folds or unfolds its branch (or click the "
                "chevron), Alt+1 to Alt+9 show that many levels of the whole map "
                "(Alt+1: the trunks alone), Shift+C draws a cross-link to another topic, F shows "
                "only this branch and its neighbours (F again: all), Shift+F10 "
                "opens every action. Ctrl+Z undoes (100 steps, kept across a "
                "reload; a deleted branch comes back whole), Ctrl+Shift+Z redoes. "
                "Right-click a topic for the ring: Add child, Add beside, Fold, "
                "Delete, Cross-link and More; hold Alt on the ring to remove "
                "instead of add. Dragging a topic onto another moves its whole "
                "branch; double-click a line to label it. A selected topic has "
                "its bar above it: the colour, the text size (minus and plus "
                "round the size it reads, S to XL), and Text, Shape and Branch "
                "line, each a panel of rows: a small preview of each look you "
                "press once, and a reset arrow that puts the topic back to "
                "following the map. Drag the square on its bottom right corner to resize it; "
                "hold Shift as you drag to scale its text with it. Pick several "
                "topics (drag a box round them, or Shift-click) and the bar and "
                "the right-click menu act on all of them: colour, bold, tasks, "
                "fold, and a summary when they share a parent. A topic's menu "
                "has Summarise this branch: a few sentences about everything "
                "under it go into the topic's note, yours to change or keep."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-features",
            "keywords": (
                "radial", "logic chart", "timeline layout", "fishbone", "tree table", "colour by", "color by", "tidy", "layout of the map",
                "checkbox on a topic", "topic a task", "tick a topic", "number the branches",
                "numbered topics", "outline numbers", "note on a topic", "note behind a topic",
                "comment on a topic", "boundary", "summary topic", "summarise topics",
                "mind map features", "layout picker", "present branches", "marker", "markers", "priority on a topic",
                "flag a topic", "filter by marker", "map outline", "outline of the map",
            ),
            "body": (
                "Mind map features. The layout picker: tree, radial, logic chart, "
                "timeline, fishbone, tree table or free; Tidy lays every unpinned topic out again. "
                "The View menu sets Colour by (branch, category, age, or whether "
                "a note is behind it) and opens every folded branch; View, "
                "Present branches shows it branch by branch. A topic's menu, "
                "Content, Markers sets a priority (1 to 5), how far along it is, a "
                "flag, a due day and up to six icons; View, Filter by marker dims every topic "
                "without the one you pick. The sidebar's Outline tab (View, "
                "Outline) lists the map as an indented outline: F2 renames, "
                "Shift+Enter adds a topic, Tab and Shift+Tab move it in and out a level. "
                "A topic's menu makes "
                "it a task: press its box to tick it, and every topic above "
                "counts the done ones (1/2); Markdown exports write tasks as - [ "
                "] and - [x]. View, Number the branches numbers every topic by "
                "its place (1, 1.1, 1.2), and the Markdown and OPML exports keep "
                "the numbers. A topic's menu adds a note behind it: its mark on "
                "the topic opens it. "
                "Comment… starts a thread, counted on its corner; its Branch group draws a boundary "
                "round the branch or summarises topics side by side. Templates, import and export are in Mind map import and export."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-import-export",
            "keywords": (
                "opml", "an opml outline", "import an opml", "freemind", "xmind", "import a map", "export a map", "map template", "map as a document",
                "map the headings", "suggest branches", "branches from my notes", "grow the map",
                "expand from my notes", "children from notes", "write a map as a document",
                "import a mind map", "export a mind map",
            ),
            "body": (
                "Mind map import and export. Start from a "
                "template, import an OPML, FreeMind, XMind, Markdown or text outline "
                "(it opens as a tree), paste an indented "
                "list onto a topic to add it as that topic's branch, let the "
                "local AI propose a map from notes you pick, or on a topic choose "
                "Add, Branches from my notes… for up to five children found in your "
                "notes, each saying which note it came from; export it as "
                "OPML, FreeMind, XMind, Markdown or text as well as a picture, or write it as "
                "a document (the board menu's Write as a document: branches "
                "become headings, deeper topics lists, notes paragraphs); a "
                "document's menu, Map the headings, goes the other way. With a "
                "map open, the command palette (Ctrl+K) lists the map's commands: "
                "add, rename, fold, focus, tidy, layout, look, numbering, present "
                "and export."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-controls",
            "keywords": (
                "outline", "split view", "live view", "source view", "read view",
                "suggest changes", "suggestion mode", "track changes", "tracked changes",
                "read aloud", "accessibility check", "grammar", "word goal",
                "typewriter", "focus mode", "find and replace", "replace all",
                "docx", "word document", "microsoft word", "find in every document",
                "replace in every document", "replace across documents",
            ),
            "body": (
                "Document editor keys (Library, Documents; Ctrl+Shift+D starts "
                "one). While a document is open, Ctrl+K lists every document "
                "command and ? shows the ones with keys. Ctrl+S saves, Ctrl+B "
                "bold, Ctrl+I italic, Ctrl+E inline code, Ctrl+Shift+S strike "
                "through, Ctrl+1, Ctrl+2 and Ctrl+3 headings, Ctrl+Shift+8, "
                "Ctrl+Shift+7 and Ctrl+Shift+9 a bulleted, numbered and task list, "
                "Tab and Shift+Tab "
                "indent and outdent, Ctrl+/ comments the selection, Alt+Up / "
                "Alt+Down moves a section from the outline, and typing / opens "
                "the blocks menu. Ctrl+F finds and replaces (Enter next, "
                "Shift+Enter previous, Esc closes), Ctrl+Shift+F finds in every "
                "document, and Replace in every document (the ⋯ menu or Ctrl+K) replaces across "
                "them all, plain or a regular expression, as one undo step. Views: Edit, where Live renders as you write, Source "
                "is the markdown and Split puts a preview beside it, or Read. The "
                "sidebar's Outline lists the headings (with a filter when there "
                "are many), and headings fold. Focus mode (the corners button on "
                "the dock, or F11) hides everything but the page, with a small "
                "bar for the title, save state, a Sidebar button and Exit (Esc "
                "closes the sidebar, then Esc or F11 leaves). The formatting "
                "toolbar hides and comes back: while it is hidden, the Formatting "
                "button in the document's bar, Ctrl+Shift+X or the bar's More "
                "menu, Show formatting toolbar, brings it back. In a Live table "
                "the arrows keep the column, Enter goes to the cell below, and "
                "rows pasted from a spreadsheet fill the cells. Pasting from a "
                "web page, Word or Google Docs keeps headings, bold, italics, "
                "lists and links; Ctrl+Shift+V pastes plain text. With nothing "
                "selected, Ctrl+C and Ctrl+X copy and cut the whole line, and "
                "pasting that line puts it above the one you are on."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-features",
            "keywords": (
                "history of a document", "word goal", "typewriter", "footnote", "footnotes",
                "page break", "newpage", "docx", "word document", "microsoft word",
                "extract notes", "ai edit",
                "serif", "full width",
            ),
            "body": (
                "Document editor features. The document's menus hold History "
                "(every version, and a way back to any), Connections, Extract "
                "notes, AI edit, a word goal, typewriter scrolling, dim all but "
                "this paragraph, serif for reading and full width. With no model "
                "connected, AI edit and Extract notes say why when pressed and "
                "offer Set up a model. Footnotes show "
                "as numbered notes at the foot in Read view, in print and in the "
                "HTML download. A page break (the / menu's Page break, written "
                "\\newpage on its own line) starts what follows on a new page when "
                "the document is printed or saved as a PDF. Writing checks: "
                "spelling against your own dictionary, grammar checked on this "
                "machine, an accessibility check (a skipped heading level, an "
                "image with no description, link text like \"click here\"), Suggest "
                "changes (tracked changes to accept or reject one at a time or "
                "all at once), Read aloud (Esc stops), autocorrect, and word "
                "suggestions (Tab accepts). Word: Download as .docx is written in "
                "the app, nothing to install, and keeps headings, emphasis, "
                "links, nested lists, tables, code (with its language), pictures, "
                "and suggested changes as Word's tracked changes; a .docx added "
                "in the Library is read with its headings, nested lists, tables, "
                "code blocks and pictures kept, and one with tracked changes "
                "keeps them as suggestions to accept or reject; other downloads "
                "are .md, .html, a .zip "
                "with images, and print or save as PDF."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        #: INBOX 486, the owner on a callout: "I have no clue how to use these
        #: things". Its own entry: the documents entry is at the reply cap.
        {
            "id": "callouts",
            "keywords": (
                "callout", "callouts", "change the kind", "note box", "warning box",
                "tip box", "admonition", "collapsible callout",
            ),
            "body": (
                "Callouts: type / in a document or a note and pick Note, Tip, Warning "
                "or another kind. The box is tinted by its kind and its icon names "
                "it; click the icon to change the kind or to make the box fold. The "
                "first line, after the icon, is the title, written like any text, "
                "and the lines under it are the body (an empty body says what goes "
                "there). Source view shows the markdown: > [!tip] Title."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "graph-controls",
            "keywords": (
                "similarity", "strength slider", "gravity", "spread", "saved view",
                "save a view", "graph view", "graph options",
                "display options", "trace", "unpin", "pin a note", "cluster glow", "label background",
                "entities", "hide unlinked", "minimap", "export as png", "lasso",
                "zoom", "pan", "link reason", "why linked", "connection",
            ),
            "body": (
                (
                    "Graph keys and controls. Click the map, then the arrow keys move between notes, N steps "
                    "to the next connected note, Enter or Space opens one, + and - zoom, 0 fits the whole "
                    "map, Shift and the arrows pan, Esc leaves. Drag a note to move it (it settles near the "
                    "drop); double-click it to pin it, again to free it. Drop one note onto another to link "
                    "them, double-click empty space to add a note there, hover to spotlight a note's "
                    "connections, point at a line to light it and click it to see what it is, its reason and "
                    "how sure, the two notes, and for a link Edit reason, Two-way (no arrow) and Remove, and "
                    "click a legend colour to hide that category. Shift and drag on empty map lassos notes, "
                    "and the selection bar can Tag, Link together, Unlink (both undoable with Ctrl+Z) or make"
                    " a Mind map of them, built from their links round the picked or most connected note, "
                    "with Open on the notice that follows. Display options, the gear, opens with View: Layout"
                    " (Force, Tree, Radial or Arc; the dock names a fixed one), "
                    "Shape (Organic, Clusters or Galaxy; the Force layout's own, dimmed under the others), Colour, Size, Trace, which "
                    "finds how two notes connect, and Legend, which hides the key. Then Physics (Unpin all, "
                    "Reshuffle layout, Gravity, Spread, Link force, Length by similarity, Group by category),"
                    " the Show switches (Similarity, Entities, Documents, Boards, Tags, Attachments, "
                    "Unwritten links, Hide unlinked), Display (Labels, Label backgrounds, Curved links, "
                    "Cluster glow, Arrows), the similarity Strength slider (raise it to keep only the closest"
                    " matches), a Time filter you can play, Groups that paint notes matching some words one "
                    "colour, the minimap's position and size, and Reset, which puts the layout, colours, "
                    "physics, switches, time filter and minimap back and keeps groups and saved views. Saved "
                    "views keep the layout, filters and position under a name."
                )
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        #: GRAPH_PLAN 514, Obsidian's graph parity: its own entry, since
        #: graph-controls is near the reply cap.
        {
            "id": "graph-display",
            "keywords": (
                "local graph", "focus depth", "depth", "incoming", "outgoing",
                "neighbour links", "tags as nodes", "unwritten link", "unresolved link",
                "ghost node", "attachments on the graph", "arrows", "text fade",
                "link thickness", "link force", "label background",
                "topic", "topics", "subjects", "outline", "colour by topic",
                "rename a topic", "drag a topic", "move a topic", "topic chip",
                "filter links", "kind of link", "hide links", "property chips",
                "note type", "colour by type",
            ),
            "body": (
                "More graph controls, in the gear. Show adds Tags (a node per tag), "
                "Attachments (a node per file or picture) and Unwritten links: each "
                "[[name]] no note answers to is a faint node, and clicking it writes "
                "that note, named in its heading, linked from every note that named "
                "it. Display holds Labels, Label backgrounds (off draws names on a "
                "thin outline), Curved links, Cluster glow, Arrows (off at first: a "
                "spark on each link, its tail toward the note that made it, the "
                "line wider at that end; pointing at a note sends a spark along "
                "its links unless motion is reduced), Text fade (how far out names stay on a big "
                "map) and Link thickness. Physics adds Link force, Length by "
                "similarity and Group by category. In focus mode a Focus section sets "
                "Depth (1 to 5 links) and Incoming, Outgoing and Neighbour links; "
                "the Local map beside a note has the same four under Options. "
                "Colour: Topic outlines each subject inside a cluster, names it by "
                "the tag, person or word its notes share most, and its legend entry "
                "finds those notes and opens its card, where Summarise asks your "
                "local model for one sentence (with no model, what they share), "
                "File as a category files its notes under one category, "
                "and the pencil renames it (the arrow brings the found name back). "
                "On the map, drag a topic's name to move all its notes together "
                "(they stay put; Unpin all releases them), double-click it to rename, "
                "click it for its card. A note's card and its panel show its topic; "
                "pressing it opens the graph on that topic. "
                "No note's name is drawn over a topic's name. Filter holds a chip per "
                "kind of link on the map (press one to take those links off, again "
                "to bring them back) and per property value (press to light those "
                "notes). Colour: Note type paints each note its type's colour "
                "(Person, Project, Meeting, Book and Place come built in). "
                "In Trace, a step marked +2 has two more reasons "
                "its notes relate; point at it to read them."
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        #: GRAPH_PLAN KG4: note properties and note types.
        {
            "id": "properties",
            "keywords": (
                "property", "properties", "frontmatter", "yaml", "note type",
                "note types", "fields", "field", "status", "metadata",
                "query", "live query", "type:", "prop:", "table view",
                "rollup", "rollups", "roll up", "custom metadata", "find by property",
            ),
            "body": (
                "A note can carry properties (status: open, owner: Priya), kept "
                "at the top of its own text between two --- lines, the way "
                "Obsidian writes them, so an imported vault keeps them and an "
                "export carries them. They show as a small table under the "
                "note's title, where pressing a value finds every note with it; "
                "a note's panel on the graph shows them too, a value lighting "
                "those notes on the map, with a Properties button. A note's ⋯ has Properties: add, change or remove "
                "one, or pick a Type, and Save rewrites only those lines. Note "
                "types in the command palette makes a kind of note (Meeting: "
                "attendees, date) with fields that are text, a number, a date, a "
                "list, yes/no or another note (the magnifier beside a note field "
                "searches your notes for it); its New note starts with them. A "
                "document's properties panel does the same: with type: Meeting "
                "in its properties, the type's fields it has not written yet "
                "show as empty rows, and a value you enter is written as one "
                "line. The notes filter asks about them: type:meeting, prop:status=open "
                "(a value with a space in quotes: prop:status=\"in progress\") "
                "(or prop:effort>2), links:[[Kiln plan]], rel:supports, "
                "entity:\"Sam Lee\", with - before any of them to leave those out; "
                "a bar over the list then shows the same notes as a Table, with "
                "their properties as columns, or lit on the graph. The table's "
                "last row rolls each column up over every match: Count, and Sum, "
                "Min and Max for numbers, Earliest and Latest for dates. On the "
                "graph, View, Colour, Note type paints each note by its type; a "
                "type's ⋮ in Note types has Colour to choose which."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        #: GRAPH_PLAN KG5: the entity layer, its page and its list.
        {
            "id": "entities",
            "keywords": (
                "entity", "entities", "people", "person", "people and things",
                "place", "places", "organisation", "who is", "other names",
                "alias", "aliases", "merge names", "named together",
            ),
            "body": (
                "Atlas notes the people, places, projects, organisations and things "
                "your notes name, with a kind for each. Show, Entities on the Graph "
                "draws them; two named together in two notes or more are joined. "
                "Click one, or open People and things from the command palette, for "
                "its page: every note that names it with the sentence, what it is "
                "named with, and the dates its notes mention. Its ⋯ sets the Kind, "
                "Renames it, edits Other names (the names it also goes by) and "
                "Merges it into another, moving every mention; Undo in the toast, "
                "or Ctrl+Z, splits the two back as they were. Suggestions, Names "
                "offers the merges that look right (\"Sam\" and \"Sam Lee\")."
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        {
            "id": "chat-controls",
            "keywords": (
                "fork", "compress", "regenerate", "plan first", "attach a note", "checklist", "heads up",
                "attach panel", "attach a picture",
                "context window", "export the chat", "stop the answer", "stop an answer",
                "source mark", "numbers in an answer", "numbered", "citation number",
                "footnote", "evidence", "show the evidence", "square brackets", "note name in an answer", "supported", "unsupported",
                "from your notes", "why this source",
            ),
            "body": (
                "Chat keys and controls. Enter sends, Shift+Enter starts a new "
                "line; Escape or Ctrl+. stops the answer, Ctrl+Shift+O starts a new chat, "
                "Ctrl+Shift+G turns agent mode on or off, Ctrl+Shift+P clips a note "
                "to your next question, and Ctrl+Shift+A opens the same agent over "
                "any tab. Typing / in the box opens the chat menu: attach a note, a "
                "document, a file or an image, upload one, Web search, "
                "Plan first, Skills, Commands, "
                "and Agent or Ask mode. The note button beside the box opens Attach: "
                "a tab each for notes, documents, files, images and mind maps, with "
                "a search; the arrows move, Space "
                "ticks, Enter is Done. Each message's menu can copy it, edit your "
                "question, regenerate from here, save it as a note or read it "
                "aloud. The header can fork the conversation, compress the earlier "
                "messages (Undo goes back), show how full the model's context is "
                "(press it for what fills it, Compact earlier messages and Change "
                "the window, the size set in Settings, Models), "
                "switch the model, and export the chat as Markdown. A numbered "
                "source mark in an answer shows a preview of its note on hover or "
                "focus (the passage it came from, whether it supports the sentence "
                "or only partly, and three bars for why it was chosen: Words it "
                "shares, Meaning, Links), a press "
                "keeps it open, and Open note goes there. A note's name in square "
                "brackets shows it on hover; a press opens it. The button at the end of "
                "Grounded in says how many sentences came from your notes (\"9 of "
                "11 from your notes\"); it opens the evidence, each sentence beside "
                "the passage it came from, and No note says this beside the ones "
                "none backs. When an agent "
                "answer takes more than one step, a checklist above it ticks off "
                "each round, what it searched or read, then the answer. A number "
                "or a name in an answer that nothing it read contains gets a "
                "heads-up under the answer, so check it before relying on it."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "notes-controls",
            "keywords": (
                "search syntax", "search operator", "filter syntax", "is:favourite",
                "tag:", "cat:", "exact phrase", "select several", "batch",
                "move several", "several notes", "multiple notes", "bulk", "notes filter",
                "filter notes", "blocks menu", "slash menu", "several notes at once",
                "filter by date", "is:draft", "title:", "before:",
            ),
            "body": (
                "Notes keys and controls. In Capture a thought, Ctrl+Enter saves, "
                "/ (or Ctrl+/) opens the blocks and commands menu, Ctrl+J asks "
                "Atlas to write at the cursor, and selecting text shows an actions "
                "menu (Ctrl+Shift+E from the keyboard). From anywhere, Ctrl+Shift+N "
                "starts a note, Ctrl+D opens today's note and Ctrl+Shift+R records a "
                "meeting. In the list, Up and Down move note to note and Tab walks "
                "that note's buttons. The filter box understands, with no AI: two words (both, "
                "in any order), \"a quoted phrase\", tag:work, cat:recipes, "
                "#tag, title:, in:, before: and after: (a date such as 2026-09), "
                "is:favourite, is:pinned, is:private, is:linked, is:untagged, "
                "is:draft, tags:<2 (also <=, > and >=), has:link (also file, image or "
                "reminder), space:work and kind:note (asked of the search engine), and -word to leave a word "
                "out. is:review lists the filings to check (Atlas's estimate is under 50%, "
                "or it left the note in Uncategorised), each with Accept, Refile and "
                "Split; the Categories widget on the dashboard counts them. Select ticks several notes to move to a category, tag or "
                "delete together, and Select all ticks the whole page; the "
                "selection bar's Tags adds or removes tags on every selected note, "
                "and its ... menu adds to or removes from Favourites, archives, "
                "publishes drafts, removes a tag, moves them to another space or "
                "exports them as Markdown, each undoable. In Agent mode, Atlas can "
                "move chosen notes to a category or a space once you confirm, "
                "and Undo puts them back. Editing a note shows "
                "its words and reading time beside Save."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "library-controls",
            "keywords": ("sub-tab", "subtab", "sort the library", "select all", "boards and maps"),
            "body": (
                "Library controls. The sub-tabs are plain words with a line under the one you are on (Notes and the document sidebar draw theirs the same way): All (everything you have made), "
                "Documents, Boards & maps, Images, Files, AI skills, Bookmarks and "
                "Contents. Search, then sort newest first, oldest first, A to Z or "
                "biggest first, and set how many show per page. Tick a card's box "
                "to select it: the bar that appears has Select all, Open, Restore "
                "(for binned items), Delete and Done, and Documents and the gallery "
                "have bars of their own. New (a whiteboard or a mind map), Map from "
                "notes and Import outline sit on Boards & maps; Images takes "
                "uploads of pictures and PDFs."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "timeline-controls",
            "keywords": ("time bucket", "feed view", "table view", "calendar view", "month view", "week view", "reschedule", "jump to today", "density strip", "group by", "add an event"),
            "body": (
                (
                    "Timeline controls. Feed shows the newest first, grouped by date; Table shows every "
                    "column, sortable; Calendar shows a month, a week (hour rows) or a day: reminders and "
                    "meetings at their time, a day's page at the top of its day and a chip with its title for"
                    " each note (a dot each where a day is too short). Press a day to open it as a Day view; "
                    "a +n opens the day in the feed. Drag a reminder to another day or hour to move it, or "
                    "press Alt and an arrow on it (Undo puts it back); the arrows walk the days, Page Up and "
                    "Page Down the months, T is today, Enter or Space opens the day (from a Day view, in the "
                    "feed); double-click a day or an hour, or press Add or N, to add a reminder or an event (a "
                    "meeting note) there. Below a tablet's width the calendar is the month's "
                    "rows as a list. Pick the time bucket (Auto, Day, Week, Month or Year; Auto takes the "
                    "finest one that keeps the headers few and filled: days for a few weeks of notes, weeks "
                    "for a year, months for several years), what rows are grouped by (Category, Tag, Thread, "
                    "None or Everything) and show only one group, how far back (the last 3 months, the last "
                    "year, everything or a custom range), and which kinds of thing it shows; Jump to today "
                    'returns. A note that names a date ("the deadline is next Friday", "2026-10-25") sits on '
                    "that day, marked with a clock; a second date shows an arrow chip in the calendar. The "
                    "arrow keys walk the rows, Home and End jump to the ends, Enter opens a row where it sits"
                    " and Esc closes it; in Select mode Space ticks a row, and the bar moves, tags or deletes"
                    " them. The density strip beside the feed shows how much was written when: click or drag "
                    "it to go there. Above the feed, the calendar strip shows the last seven days with a dot "
                    "under each day that has a page: press a day to open its page or start it (the arrows "
                    "beside the month move a week, the month opens a calendar to jump to any earlier day)."
                )
            ),
            "badge": {"label": "Timeline", "tab": "timeline"},
        },
        {
            "id": "reminders-controls",
            "keywords": ("magic add", "quick set", "priority", "tonight", "this weekend", "every", "calendar", "ics", "outlook", "google calendar"),
            "body": (
                "Reminders controls. Magic add takes a sentence (\"Call mum "
                "tomorrow evening, high priority\"), then Enter or the sparkle button "
                "(Add from this sentence) works out the time and the "
                "priority. Times like \"tomorrow at 5pm\", \"next Friday\", "
                "\"tonight\", \"in 20 minutes\" or \"every Tuesday\" (saved as a weekly repeat) are read with no AI and shown as chips "
                "under the box before Enter (press one to leave it as words); with no "
                "day or time it asks for one rather than guessing, and the AI is asked only for a phrasing those rules miss. Or type the reminder, pick a priority (normal, low or "
                "high) and a repeat (once, daily, weekly or monthly), and use Quick "
                "set: in 30 min, in 1 hour, in 3 hours, tonight 7pm, tomorrow 9am, "
                "tomorrow 2pm, this weekend or next week. A due reminder can be "
                "snoozed one hour or to tomorrow 9am (ten minutes is on its menu; Undo in the toast puts the time back), "
                "edited in place (its early alert too), or ticked "
                "done; completed ones page at the foot. Add to calendar (.ics), on "
                "a reminder's menu, saves it as a calendar file, and Add all to "
                "calendar (.ics) in the More menu saves every upcoming one; Import a "
                "calendar (.ics) there reads a calendar file as reminders and names "
                "any event it skipped. Calendar beside List opens the Timeline's "
                "calendar with only reminders, where one drags to another day. Press m "
                "then r to jump here from anywhere."
            ),
            "badge": {"label": "Reminders", "tab": "reminders"},
        },
        {
            "id": "dashboard-controls",
            "keywords": ("quick access", "customise quick access", "highlight a tile", "tile colour", "quick start", "focused view", "full view", "due today", "today at a glance", "tools & features", "tools and features", "dashboard menu", "continue where i left off"),
            "body": (
                "Dashboard controls. Under the greeting is the search box (Ctrl+P), "
                "then Customise and a ... menu. The ... menu is for doing: "
                "Continue (the note you opened or edited last), your two most "
                "recent skills and All skills, Tools & features (a searchable "
                "list of everything the app can do) and Commands (the command "
                "palette). Customise arranges the page: View (Full, Compact or "
                "Focused), Widgets and Edit layout, which show, hide and "
                "rearrange widgets. The Focused view folds Quick access away and "
                "its greeting card holds New note and four tiles for today: what "
                "is due today, today's meetings, the notes to file and the note "
                "you were last in; press one to go there. Customise, and the "
                "... at the right of the Quick access title, have "
                "Edit quick access: Add or arrange opens "
                "a list of every command with the ones on your dashboard "
                "checked and first. Check or uncheck as many as you like (up to "
                "eight), drag a row or press Alt with Up or Down to reorder, "
                "search to narrow it, then Done saves them all at once; a tile's "
                "menu still has Move left, Move right, Highlight and Remove. "
                "The first tile is highlighted in the accent; Highlight gives "
                "any tile the accent, one of twelve colours or No highlight. "
                "Reset highlights clears the colours (the first tile is "
                "highlighted again); Reset quick access goes back to the "
                "defaults. Quick access "
                "starts as New note, Ask AI, Sketch, Remind me and New "
                "meeting. All of it is "
                "remembered per user. Press m then d to come back here from "
                "anywhere."
            ),
            "badge": {"label": "Dashboard", "tab": "dashboard"},
        },
        {
            "id": "hidden-features",
            "keywords": (
                "hidden feature", "hidden", "secret", "tips", "tricks", "tips and tricks",
                "power user", "easter egg", "things i might not know", "didn't know",
                "chord", "m then", "m chord", "every feature", "all the features",
            ),
            #: The "m" chord's two tables (`TAB_JUMP_KEYS` and `CHORD_ACTIONS`,
            #: app.js) are written out letter by label, and checked against the
            #: tables, so a letter added there has to be added here.
            "body": (
                "Hidden features and power keys. Ctrl+K is the command palette "
                "(jump anywhere, run an action), Ctrl+P is Find anything (notes, "
                "files and actions), and ? lists every shortcut, which Settings, "
                "Keyboard shortcuts rebinds. Press m then a letter to jump: d (Dashboard), n "
                "(Notes), c (Chat), g (Graph), l (Library), t (Timeline), r "
                "(Reminders), o (OCR workspace); or to act: s (Settings), q (Quick sketch), v (Record "
                "a meeting), a (Guide), p (Popup agent). A second m or Esc closes the panel. "
                "Ctrl+Shift+A opens the agent over any tab, Ctrl+Shift+H asks Atlas "
                "about the app, Ctrl+J writes at the cursor, Ctrl+Shift+E acts on "
                "selected text (so does a right-click on the selection), Ctrl+Shift+K opens the quick sketch pad, and "
                "Ctrl+Alt+R reloads the app clearing cached files. Every menu works "
                "from the keyboard: the arrows move, Home and End jump, Enter picks "
                "and Esc closes. Select in Notes, the Timeline and the Library acts "
                "on many items at once, the notes filter takes tag:, cat: and is: "
                "operators, the dashboard's ... menu has Tools & features, which lists everything the "
                "app can do, and each section's ? explains itself."
            ),
            "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
        },
    ]
)

#: **Every Settings section, the companion, the faces and the app's layout**
#: (INBOX 430): the second half of the reference, in its own module
#: (help_topics_more.py) so this one stays about how an answer is found.
HELP_TOPICS.extend(MORE_TOPICS)
# The speller reads the help text for the app's own vocabulary (see spelling.set_topic_source).
spelling.set_topic_source(lambda: [*HELP_TOPICS, *MORE_TOPICS])

#: **Which entry answers "the keys of" a surface.** A question that names a
#: surface and asks about its keys, controls or hidden corners is about that
#: surface's controls entry, and the ranking below cannot see that on words
#: alone: "whiteboard" belongs to the description and "shortcut" to the global
#: shortcuts entry, so without this the question landed on one of those two.
_CONTROLS_FOR: dict[str, str] = {
    "whiteboard": "whiteboard-controls",
    "mind-maps": "mind-map-controls",
    "documents": "documents-controls",
    "graph": "graph-controls",
    "ask-chat": "chat-controls",
    "capture": "notes-controls",
    "library": "library-controls",
    "timeline": "timeline-controls",
    "reminders": "reminders-controls",
    "dashboard": "dashboard-controls",
    #: The code editor's entry is its own controls reference (see its body).
    "code-files": "code-files",
}

#: The words that make a question about a surface a question about its
#: controls. Deliberately narrow: "how do I make a mind map" is not one, and
#: that is the question most people ask.
_CONTROL_INTENT = re.compile(
    r"\b(?:shortcuts?|keybinds?|keybindings?|key ?binds?|hotkeys?|keys|keyboard|"
    r"controls?|gestures?|chords?|hidden|secret|tips|tricks|power user|"
    r"everything (?:i|you) can do|what can i do|all the (?:features|tools|things))\b"
)

#: **The chords themselves are keywords.** "What does F12 do" names nothing
#: but a key, and the entry that documents F12 is the right answer; every
#: chord a controls entry's body names is added to its keywords, lowercased,
#: so the table and the prose cannot disagree about which keys an entry
#: covers. `_normalise_keys` below spells a question's chords the same way.
_CHORD = re.compile(
    r"(?<![\w+])(?:(?:Ctrl|Shift|Alt)\+)+(?:F\d{1,2}|Enter|Tab|Up|Down|Left|Right|"
    r"[A-Za-z0-9]\b|[/.,=\-\[\]])|(?<![\w+])Shift\+F\d{1,2}\b|(?<![\w+])F\d{1,2}\b"
)

#: A tight window: this is guidance, not a conversation to reminisce in.
MAX_HISTORY_TURNS = 6
MAX_MESSAGE_CHARS = 1000
#: **A history turn is the Guide's own answer handed back**, so its bound is
#: what the Guide writes, not what a person types (INBOX 410): an offline
#: controls answer runs past 1,600 characters, and the route refused any turn
#: over `MAX_MESSAGE_CHARS`, so the question after one failed with a 422.
#: The prompt still cuts each turn to `MAX_MESSAGE_CHARS` (`_prompt_for`):
#: this bound is what the route accepts, not what the model is sent.
MAX_HISTORY_TURN_CHARS = 4000
#: **Where the question was asked from** (INBOX 190: "maybe give it more
#: knowledge and capabilitie/function"). The Guide is reachable from every tab
#: now, so "how do I do this" is asked with something specific on screen, and
#: until this it answered as though the question had arrived from nowhere.
#: A tab pulls in its own topics whether or not the question names them, which
#: is what lets "how does this work?" on the Graph tab be a question about the
#: graph. The ids are `HELP_TOPICS` ids; a tab with no entry simply adds
#: nothing, which is the correct behaviour for a surface the topics do not
#: cover yet.
TAB_TOPICS: dict[str, tuple[str, ...]] = {
    "dashboard": ("dashboard",),
    "notes": ("capture", "memory"),
    "chat": ("ask-chat", "skills"),
    "graph": ("graph",),
    "library": ("library", "files-images", "whiteboard"),
    "documents": ("documents",),
    "timeline": ("timeline",),
    "reminders": ("reminders",),
}

#: How much of the surface's own help copy the client may send with a
#: question. The caller passes the `.help-body` text of whatever is on screen
#: (frontend/js/settings.js), which is the app's own wording for the thing being
#: asked about and therefore the best possible reference note: it is also
#: user-supplied input on the wire, so it is capped here rather than trusted
#: to have been capped there.
MAX_CONTEXT_CHARS = 1200

#: How many reference entries to hand the model for one question. Kept
#: small on purpose: item 40 asked for "a tight prompt/context budget",
#: and a guidance answer is about one or two features, not a syllabus.
MAX_TOPICS = 3


# Whole-word match, not a raw substring one, a plain `in` check let "ask"
# match inside "basket" and "task", and a wrongly-matched topic means the
# model gets handed reference notes about the wrong feature. Compiled once
# at import time rather than per call: this runs on every `/help/ask`
# request, and re-compiling ~100 small regexes (18 topics x ~6 keywords)
# on every one of them is wasted work an unbounded local model call already
# dwarfs, but costs nothing to avoid.
#
# **Whole word, but not one single form of the word** (INBOX 304, the owner:
# "the help bot is useless, or the suggested questions are bad or both"). He
# asked "Where do reminders live?" and was told the guide was not sure, with
# Notes and What it remembers named as its sources. The reminders entry was
# in this table the whole time: the keyword is "reminder", the pattern was
# `\breminder\b`, and the plural he typed does not match it. Nothing matched,
# so the tab's own topics filled in, and a question about reminders was
# answered from the notes and memory entries. Every plural in the app had the
# same hole: "documents", "notes", "spaces", "backups". The keyword table is
# written in the singular by anyone adding to it, and people ask in whichever
# number reads naturally, so the number is handled here once rather than by
# asking thirty entries to list both forms and catching the next one late.
#
# A fixed set of inflections, not a stemmer: "-s", "-es" and the possessive,
# plus "-y" to "-ies" for a keyword like "library". Anything less regular
# ("recur" to "recurring") is spelt out in the keyword tuple, where it can be
# read, rather than guessed at by a rule loose enough to match it.


#
# **Lookarounds rather than `\b`** (INBOX 410): a keyword can be a chord now
# ("ctrl+/", "tag:"), and `\b` after a "/" or a ":" asks for a word character
# to follow it, which "what does ctrl+/ do" does not have. The guards below are
# `\b` exactly where a keyword starts or ends with a word character, and no
# guard where it does not; a chord is also refused when it is only the tail
# of a longer one ("shift+k" inside "ctrl+shift+k").
def _keyword_pattern(keyword: str) -> re.Pattern[str]:
    if len(keyword) > 3 and keyword.endswith("y") and keyword[-2] not in "aeiou":
        stem = re.escape(keyword[:-1]) + "(?:y|ies)"
    else:
        stem = re.escape(keyword) + "(?:es|'s|s)?"
    start = r"(?<![\w+])" if "+" in keyword else (r"(?<!\w)" if keyword[0].isalnum() else "")
    end = r"(?!\w)" if keyword[-1].isalnum() else ""
    return re.compile(rf"{start}{stem}{end}")


#: A chord as people type it ("ctrl shift f", "Cmd-K", "control k") spelt the
#: way the entries spell it ("ctrl+shift+f"), so a chord keyword can match.
#: The lookahead insists on a key after the modifier, so "shift and drag" and
#: "the control panel" are left alone. The separator is one bounded choice
#: (CodeQL 426: `\s*(?:\+|-|\s)\s*` let a run of tabs split three ways).
_MODIFIER = re.compile(
    r"\b(ctrl|control|cmd|shift|alt|option)(?:\s{0,3}[+\-]\s{0,3}|\s{1,3})"
    r"(?=(?:ctrl|control|cmd|shift|alt|option)\b|f\d{1,2}\b|enter\b|tab\b|up\b|down\b|"
    r"left\b|right\b|[a-z0-9](?![a-z0-9])|[/.,=\-\[\]])"
)
_MODIFIER_NAMES = {"control": "ctrl", "cmd": "ctrl", "option": "alt"}


def _normalise_keys(lowered: str) -> str:
    return _MODIFIER.sub(lambda m: _MODIFIER_NAMES.get(m.group(1), m.group(1)) + "+", lowered)


#: The chord keywords, added here rather than beside `_CHORD` because they are
#: compared in `_normalise_keys`'s spelling. **A chord an entry already names
#: in its own keywords is that entry's**: "ctrl k" is the command palette's,
#: and the five controls entries that mention Ctrl+K in passing must not
#: outvote the entry about it.
_CLAIMED_KEYS = {_normalise_keys(k) for _topic in HELP_TOPICS for k in _topic["keywords"]}
for _topic in HELP_TOPICS:
    if _topic["id"] in set(_CONTROLS_FOR.values()) | {"shortcuts", "hidden-features"}:
        _chords = dict.fromkeys(c.lower() for c in _CHORD.findall(_topic["body"]))
        _topic["keywords"] = _topic["keywords"] + tuple(c for c in _chords if c not in _CLAIMED_KEYS)


#: **The Guide's gold, 2026-10-11** (`tests/fixtures/composer/guide_1011.json`,
#: 25 questions typed the way people ask): the words that took a question to
#: the wrong topic, edited on the topics added after the first table, which
#: that table cannot reach. "why is the chat so slow" is speed, not Chat;
#: "where did my deleted notes go" is the bin; "export everything to
#: markdown" is Import & export.
_KEYWORDS_ADD_GUIDE: dict[str, tuple[str, ...]] = {
    "performance": ("so slow", "is slow", "running slow", "takes ages", "sluggish"),
    "undo-bin": ("deleted", "deleted notes", "deleted note", "undo deleting", "undelete"),
    "import-export": ("export", "markdown", "to markdown", "as markdown", "backup", "back up my notes"),
    "meetings": ("record a meeting", "record meetings", "record the meeting"),
    "notes-controls": ("lots of notes", "many notes", "notes at once", "all at once"),
    "tag-manager": ("rename a tag", "rename tags", "merge tags", "delete a tag"),
}
_KEYWORDS_REMOVE_GUIDE: dict[str, tuple[str, ...]] = {
    "storage": ("export everything",),
}
for _topic in HELP_TOPICS:
    _drop = set(_KEYWORDS_REMOVE_GUIDE.get(_topic["id"], ()))
    _topic["keywords"] = tuple(k for k in _topic["keywords"] if k not in _drop) + tuple(
        k for k in _KEYWORDS_ADD_GUIDE.get(_topic["id"], ()) if k not in _topic["keywords"]
    )


@functools.lru_cache(maxsize=None)
def _keyword_regex(keyword: str) -> re.Pattern[str]:
    return _keyword_pattern(_normalise_keys(keyword))


def _keyword_in(keyword: str, lowered: str) -> bool:
    """`_keyword_pattern(keyword)` found in `lowered`, compiled only when it can
    match. All 2,200 patterns were compiled at import (about 0.5 s of the app's
    start, INBOX 1307); a pattern can only match where its literal stem occurs,
    so a substring test settles almost every keyword without a regex at all."""
    normal = _normalise_keys(keyword)
    stem = normal[:-1] if len(normal) > 3 and normal.endswith("y") and normal[-2] not in "aeiou" else normal
    return stem in lowered and _keyword_regex(keyword).search(lowered) is not None


def _edit_distance_at_most_one(a: str, b: str) -> bool:
    """True when `a` becomes `b` by one insertion, deletion, substitution or
    swap of two neighbours: the typos a person makes in a help box ("remnder",
    "serach", "chnage")."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [k for k in range(la) if a[k] != b[k]]
        if len(diff) == 1:
            return True
        return (
            len(diff) == 2
            and diff[1] == diff[0] + 1
            and a[diff[0]] == b[diff[1]]
            and a[diff[1]] == b[diff[0]]
        )
    if la > lb:
        a, b = b, a
    k = 0
    while k < len(a) and a[k] == b[k]:
        k += 1
    return a[k:] == b[k + 1 :]


_WORD = re.compile(r"[a-z0-9]+")

#: Single-word keywords long enough to forgive a typo in (a four-letter word
#: one letter off is usually a different word).
_TYPO_MIN = 5

#: How many topics each keyword belongs to, for the rarity weight below.
_KEYWORD_TOPICS: dict[str, int] = {}
for _topic in HELP_TOPICS:
    for _keyword in set(_topic["keywords"]):
        _KEYWORD_TOPICS[_keyword] = _KEYWORD_TOPICS.get(_keyword, 0) + 1

#: Body vocabulary per topic, for tie-breaking only (see `_matching_topics`).
_BODY_WORDS: dict[str, set[str]] = {
    topic["id"]: set(_WORD.findall(topic["body"].lower())) for topic in HELP_TOPICS
}

#: Words that say nothing about which feature is meant.
_STOP = frozenset(
    "a an the i me my you your it its is are am be to of in on at for and or "
    "how do does did can could would should what whats where which who why "
    "when this that there here with from into about any all some so if not "
    "no yes get got make use using used want need way".split()
)

#: A runner-up worth showing scores at least this share of the best: below
#: it, the second topic is noise the answer would be padded with.
_RUNNER_UP_SHARE = 0.4


#: The asking frame of a how-to, taken off before the rest is read as a
#: sentence ("how do I pin a note" reads "pin a note").
_HOW_FRAME = re.compile(r"^\s*(?:how (?:do|can|would|should) (?:i|you)|how to|can i|can you|where do i|is there a way to)\s+", re.I)


#: Words naming a surface other than a note: "rename a category" or "add a
#: branch to a mind map" is that surface's own how-to, not a note act.
_OTHER_SURFACE = re.compile(
    r"\b(?:graph|board|whiteboard|canvas|sticky|map|mind ?map|branch|document|chat|category|categories|timeline|"
    r"library|palette|tab|folder|space|file|photo|template|word)s?\b", re.I)


def _act_of(question: str) -> tuple[str, bool] | None:
    """The act a how-to names, read through the one reading (`ai/reading.py`,
    decision 59 step 4): the sentence after the asking frame, read as an act
    by `reading.read`, or by its first word when that is an act's verb (the
    slots a real request needs are not asked for in a how-to). With whether
    it was read whole (an act the reading itself gave). None for a how-to
    about another surface."""
    inner = _HOW_FRAME.sub("", question or "").strip(" ?.")
    if not inner or inner == (question or "").strip(" ?.") or _OTHER_SURFACE.search(inner):
        return None
    if act_registry.reader is None:
        return None
    got = act_registry.reader(inner, now=datetime.now())
    if got.intent in act_registry.ACTS and got.intent not in ("navigate", "open", "find"):
        return got.intent, True
    first = inner.split()[0].lower()
    for act in act_registry.ACTS.values():
        if act.writes and (act.intent == first or act.verb == first) and act.intent not in ("meeting", "new_note", "append"):
            return act.intent, False
    return None


def _reading_topics(question: str) -> list[dict]:
    """The reading band first (decision 59, step 4): a how-to that reads as
    a note act is answered from the act registry (`act_registry.act_topic`):
    first when the reading gave the act whole or the words reached no topic,
    else after the topic the words reached. The keyword rules are the
    fallback band (`_matching_topics`)."""
    topics = _matching_topics(question)
    read = _act_of(question)
    if read is None:
        return topics
    act, whole = read
    own = act_registry.act_topic(act)
    if topics and (not whole or topics[0]["id"] in act_registry.ACT_HELP_TOPICS.get(act, ())):
        return [topics[0], own, *topics[1:]][:MAX_TOPICS]
    return [own, *topics][:MAX_TOPICS]


def _repaired(question: str) -> str:
    """The question with its typos put right, once `question_noise` has
    registered its repair (`act_registry.repair`), else as typed."""
    return act_registry.repair(question) if act_registry.repair else question


#: "where do I find settings" asks where a place is, not for Find anything
#: (bug sweep 2026-10-12): the asking frame's "find" names no topic.
_WHERE_FIND = re.compile(r"\bwhere (?:do|can|would|should|will) (?:i|you|we) (?:find|locate|get to)\b")


def _matching_topics(question: str) -> list[dict]:
    """Which `HELP_TOPICS` entries this question is about, best first.

    **Rebuilt 2026-09-24 against a question bank** (INBOX 406,
    `tests/fixtures/help_questions.json`, 100 questions phrased the way people
    type them): the old rule, one point per matching keyword weighted by its
    word count, answered 49 of them first-time right and matched nothing for
    20 (a typo, "pictures" for image, "talk to the ai" for chat). Four rules
    now, each measured against the bank:

    * **A topic qualifies on its keywords, never on its body**, so a question
      about the weather still matches nothing: a keyword is matched as a whole
      phrase with its plural (`_keyword_pattern`), or, for a single keyword of
      five letters or more, as a word one typo away.
    * **A keyword is worth its word count times its rarity**: "web search"
      still outweighs "search", and a word three topics share ("restore")
      says less than one only this topic has.
    * **Body words break ties**: among qualifying topics, one whose own text
      uses more of the question's words ranks higher.
    * **A runner-up must earn its place**: under 40% of the best score it is
      dropped, so the answer is not padded with a topic that matched one
      incidental word.
    """
    #: The question as it was meant (Brief 90, INBOX 837: "noficiations
    #: panel", "thes ebuttons"): misspellings put right, split words joined,
    #: before the keywords are read. The keyword typo rule below stays, for a
    #: word the speller does not know.
    lowered = _WHERE_FIND.sub("where", _normalise_keys(_repaired(question).lower()))
    words = [w for w in _WORD.findall(lowered) if w not in _STOP]
    total = len(HELP_TOPICS)
    scores: dict[str, float] = {}
    for topic in HELP_TOPICS:
        score = 0.0
        for keyword in topic["keywords"]:
            rarity = 1.0 + math.log(total / _KEYWORD_TOPICS.get(keyword, 1))
            if _keyword_in(keyword, lowered):
                score += len(keyword.split()) * rarity
            elif (
                " " not in keyword
                and len(keyword) >= _TYPO_MIN
                and any(len(w) >= _TYPO_MIN - 1 and _edit_distance_at_most_one(w, keyword) for w in words)
            ):
                score += 0.8 * rarity
        if score > 0:
            scores[topic["id"]] = score
    if not scores:
        return _meaning_topics(question)
    #: **A surface's controls entry** (INBOX 410, see `_CONTROLS_FOR`). With
    #: a word asking for keys or controls, the named surface's controls entry
    #: goes above everything the words alone reached, the surface's own score
    #: ordering two named surfaces; without one, a controls entry that already
    #: qualified on its own keywords ("zoom", "lasso") takes the surface's
    #: score as well, which is what tells the graph's zoom from the board's.
    intent = bool(_CONTROL_INTENT.search(lowered))
    top = max(scores.values())
    for surface, controls in _CONTROLS_FOR.items():
        named = scores.get(surface)
        if not named:
            continue
        if intent:
            scores[controls] = max(scores.get(controls, 0.0), top) + named
        elif controls in scores and controls != surface:
            scores[controls] += named
        #: The description stays in the answer as a related entry, so the
        #: offline reply still names "graph" under the graph's controls.
        if controls != surface and controls in scores:
            scores[surface] = max(named, scores[controls] * _RUNNER_UP_SHARE)
    scored: list[tuple[float, int, dict]] = []
    for order, topic in enumerate(HELP_TOPICS):
        score = scores.get(topic["id"])
        if score is None:
            continue
        body = _BODY_WORDS[topic["id"]]
        score += 0.15 * sum(1 for w in words if w in body)
        scored.append((score, order, topic))
    scored.sort(key=lambda row: (-row[0], row[1]))
    best = scored[0][0]
    return [topic for score, _, topic in scored[:MAX_TOPICS] if score >= best * _RUNNER_UP_SHARE]


def _meaning_topics(question: str) -> list[dict]:
    """**By meaning, when no keyword matched** (Brief 94, INBOX 857): the
    words read as the things they name (`meaning.alts`: "too much moving
    stuff" is motion, "the robot" is the companion), held by a topic's title
    and keywords, the nearest first. A fallback only, so the question bank's
    keyword answers are unchanged."""
    from tessellate.ai import meaning

    things = meaning.alts(question)
    if not things or all(len(group) == 1 for group in things):
        return []
    scored = []
    for order, topic in enumerate(HELP_TOPICS):
        named = f"{topic_title(topic)} {' '.join(topic['keywords'])}"
        if meaning.holds(things, named):
            scored.append((meaning.closeness(things, named), order, topic))
    if not scored:
        return []
    scored.sort(key=lambda row: (-row[0], row[1]))
    best = scored[0][0]
    return [topic for score, _, topic in scored[:MAX_TOPICS] if score >= best * _RUNNER_UP_SHARE]


def topic_title(topic: dict) -> str:
    return TOPIC_META.get(topic["id"], {}).get("title") or topic.get("title") or topic["id"].replace("-", " ").capitalize()


#: **The system answer** (INBOX 430, the owner: "a toggle on each answer
#: between the AI's answer and the system-generated answer from the app's
#: help", with "clean formatting: headings, steps, the setting's path, and a
#: link that opens it"). The best-matching entry, laid out: its title as a
#: heading, where it lives, its text, its steps when it has some, and the
#: other entries worth reading named at the end. The link is the entry's
#: badge (`open`), which the client draws as a button that goes there; a
#: link inside the Markdown could only be a URL, and a URL cannot open a
#: settings row. The same text is the offline answer, so the Guide with no
#: model answers exactly as the toggle's other side does.
def system_answer(topics: list[dict]) -> dict:
    if not topics:
        return {"content": "", "open": None}
    first = topics[0]
    meta = TOPIC_META.get(first["id"], {})
    lines = [f"### {topic_title(first)}"]
    if meta.get("path"):
        lines.append(f"**Where:** {meta['path']}")
    lines.append(first["body"])
    steps = meta.get("steps") or ()
    if steps:
        lines.append("\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1)))
    related = [topic_title(topic) for topic in topics[1:]]
    if related:
        lines.append("**Related:** " + ", ".join(related))
    return {"content": "\n\n".join(lines), "open": first.get("badge")}


def source_names(topics: list[dict]) -> list[str]:
    return [topic["id"].replace("-", " ").capitalize() for topic in topics]


def help_listing() -> dict:
    """Every entry, in `HELP_GROUPS` order, for Settings, Help (INBOX 448).

    `find` is the entry's keywords, which the Settings search reads beside the
    title so a row is found by the words a person types ("percentage") and not
    only by its name; `link` is the entry's badge, the same tab or section an
    answer's chip opens."""
    by_id = {topic["id"]: topic for topic in HELP_TOPICS}
    groups = []
    for title, ids in HELP_GROUPS:
        topics = []
        for topic_id in ids:
            topic = by_id.get(topic_id)
            if topic is None:
                continue
            topics.append(
                {
                    "id": topic_id,
                    "title": topic_title(topic),
                    "path": TOPIC_META.get(topic_id, {}).get("path", ""),
                    "body": topic["body"],
                    "find": " ".join(topic["keywords"]),
                    "link": topic["badge"],
                }
            )
        groups.append({"title": title, "topics": topics})
    return {"groups": groups}


def badges_for(topics: list[dict]) -> list[dict]:
    """The quick-access chips for a set of matched topics, de-duplicated by
    label and capped: same cap as `MAX_TOPICS`, since each matched topic
    contributes at most one badge."""
    seen: set[str] = set()
    out: list[dict] = []
    for topic in topics:
        badge = topic["badge"]
        if badge["label"] not in seen:
            out.append(badge)
            seen.add(badge["label"])
    return out


def topics_for(question: str, tab: str | None = None) -> list[dict]:
    """The reference entries for one question, asked from one tab.

    What the question names wins outright. The tab's own topics are a
    fallback for a question that names nothing, and they are what makes "how
    does this work?" answerable at all: with no keyword in it, that question
    matched nothing and the model was told to say it was not sure.

    **A fallback, not a supplement** (INBOX 304). They used to be appended to
    whatever the question matched, up to `MAX_TOPICS`, so a question asked
    from the Notes tab was grounded in the notes and memory entries however
    clearly it named its own subject, and the answer printed Notes and What it
    remembers as its sources. Two thirds of the reference material was then
    about something the person had not asked about, on a small local model
    with a 256-token reply: the wrong entries do not sit there politely, they
    are what the model answers from. The tab is still on the prompt as a line
    of its own ("the person asking has the notes tab open"), which is the part
    of the context that was worth having.
    """
    if social_reply(question):
        #: A greeting names no feature, so the open tab's topics are not its
        #: answer either (INBOX 787: "hey" was answered with the Dashboard).
        return []
    #: What the words ask comes before what they share a keyword with (B11):
    #: "how do I use the app" is the overview from any tab, "what is this
    #: page for" the tab's own topic, never the board library's "page".
    from tessellate.ai import guide_intent

    read = guide_intent.topics(question, tab, {topic["id"]: topic for topic in HELP_TOPICS}, TAB_TOPICS)
    if read:
        return read
    topics = _reading_topics(question)
    if not tab or topics:
        return topics
    seen = {topic["id"] for topic in topics}
    by_id = {topic["id"]: topic for topic in HELP_TOPICS}
    for topic_id in TAB_TOPICS.get(tab, ()):
        if len(topics) >= MAX_TOPICS:
            break
        if topic_id in seen or topic_id not in by_id:
            continue
        topics.append(by_id[topic_id])
        seen.add(topic_id)
    return topics


def _prompt_for(
    question: str,
    history: list[dict] | None,
    tab: str | None,
    context: str | None,
) -> tuple[list[dict], list[dict]]:
    """The messages one turn sends, and the topics they were built from.

    Split out of `answer` so the streamed turn cannot build a different
    prompt from the one-shot turn: the two differ only in how the reply
    comes back, and a second copy of this is how a fix to one surface's
    grounding quietly misses the other.
    """
    topics = topics_for(question, tab)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if tab:
        messages.append(
            {
                "role": "system",
                "content": (
                    f"The person asking has the {tab} tab open. Prefer the answer "
                    "that applies to what is in front of them, and say which tab "
                    "or setting anything else is on."
                ),
            }
        )
    if topics:
        reference = "\n".join(f"- {topic['body']}" for topic in topics)
        messages.append(
            {"role": "system", "content": f"Reference notes for this question:\n{reference}"}
        )
    on_screen = (context or "").strip()[:MAX_CONTEXT_CHARS]
    if on_screen:
        messages.append(
            {
                "role": "system",
                "content": (
                    "The app's own help text for what is on screen right now, "
                    "which you may answer from as well:\n" + on_screen
                ),
            }
        )
    for turn in (history or [])[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    messages.append({"role": "user", "content": question})
    return messages, topics


#: **The Guide, with no model running.**
#:
#: Asked for directly: *"I want to maximise the ability and function of all
#: the application features without ai, the ai features should just be the
#: bonus"*, and then again for this surface by name.
#:
#: The Guide is the one AI feature that never needed a model to be useful. Its
#: entire knowledge of this app is `HELP_TOPICS` above: one hand-written
#: paragraph per feature area, which is also the model's *only* source of
#: facts when a model does answer. `topics_for` picks the right ones from the
#: question and the tab, by keyword, with no inference anywhere in it. So with
#: no model the honest answer is not "I am not available": it is those
#: paragraphs, unedited, which is most of what the model would have said to
#: begin with.
#:
#: What is lost without the model is real and is not hidden: the paragraphs
#: are not rewritten to fit the question, several may arrive when one would
#: have done, and a question the keywords do not reach gets nothing. The reply
#: says so in its first line rather than passing this off as an answer
#: composed for the asker.
#: Said after the answer, never before it (decision 59, step 4; the Guide
#: row "the answer first, the preface goes"): the reply says where it came
#: from in words a person would use (INBOX 787: "From the app's own help
#: text, word for word: no model is running." read badly).
OFFLINE_LEAD = "From the app's help, with no model running."

OFFLINE_NOTHING_MATCHED = (
    "The local model is not running, and nothing in the app's own help text "
    "matches that. Try a word from the feature's own name, a tab name, or "
    "open Settings, Help, which lists every topic."
)

#: **A greeting is answered as one** (INBOX 787: "hey" was answered with the
#: open tab's topic, the Dashboard's paragraph, twice). The reply says who is
#: answering and the client puts the tab's three starters under it
#: (`atlasStartersFor`), so the first thing to ask is one tap away.
_GREETING = re.compile(
    r"^\W*(?:hi|hey|hello|hiya|howdy|yo|good (?:morning|afternoon|evening))"
    r"(?:\s+(?:there|again|atlas|guide))?\W*$",
    re.I,
)
_THANKS = re.compile(r"^\W*(?:thanks|thank you|thx|cheers|ta)(?:\s+(?:atlas|a lot|so much|very much))?\W*$", re.I)
GREETING_REPLY = (
    f"Hi, I'm {GUIDE_NAME}, the app's guide. Ask me where a feature lives, "
    "what a setting does or how to do something here. Three to start with:"
)
THANKS_REPLY = "You're welcome. Ask me about any tab or setting."


def social_reply(question: str) -> dict | None:
    """The Guide's reply to a greeting or a thanks, or None for a question."""
    text = (question or "").strip()
    if _GREETING.match(text):
        return {"content": GREETING_REPLY, "badges": [], "sources": [], "greeting": True}
    if _THANKS.match(text):
        return {"content": THANKS_REPLY, "badges": [], "sources": []}
    return None


#: **The composed answer** (INBOX 787, the owner: "they should have the option
#: to see either the base help text or a slightly more customised version with
#: the composer"). The question's own answer first (where it is, for a where;
#: the help sentence that best answers it, for anything else), then the
#: steps or one more sentence, then where the feature lives. Every sentence is
#: the help text's own or a fixed phrase around its path; the topic word for
#: word is the other side of the answer's toggle (`system_answer`).
_WHERE_ASKED = re.compile(r"^\s*(?:where(?:'s| is| are| do| can| would)?|which (?:tab|setting|menu))\b", re.I)


#: A second sentence longer than this is a wall, not a help: the topic's
#: own text, a tap away, has it.
SECOND_SENTENCE_WORDS = 35
_HOW_ASKED = re.compile(r"^\s*(?:how (?:do|can|should|would) (?:i|you|we)|how to|can i|is there a way)\b", re.I)
_COUNTS = ("no", "one", "two", "three", "four", "five", "six")


def _place(path: str) -> str:
    """"the Reminders tab" for "Reminders tab"; a Settings path as written."""
    return f"the {path}" if path.endswith(" tab") and not path.startswith("The ") else path


#: A full stop that ends no sentence: "(e.g. Summarise)", "etc. and", "vs.".
_ABBREVIATION = re.compile(r"\b(?:e\.g|i\.e|etc|vs|approx|incl|cf)\.$", re.I)


def help_sentences(body: str) -> list[str]:
    """The sentences of a help topic of five words or more. A sentence ends
    at a stop before a capital, a quote or a bracket, or at the end: "0.5x",
    ".ics", "a category's ... menu" and "e.g. Summarise" end nothing (the
    Guide's gold: "Skills are one-click requests shown above the chat box
    (e." was a lead)."""
    out, start = [], 0
    for m in re.finditer(r"[.!?](?=\s+[\"“(\[*]?[A-Z0-9]|\s*$)", body):
        chunk = body[start:m.end()]
        if _ABBREVIATION.search(chunk) or chunk.endswith(".."):
            continue
        out.append(chunk.strip())
        start = m.end()
    #: Five words at least: "Notes keys and controls." is a topic's title.
    return [line for line in out if len(line.split()) >= 5]


def _help_sentences(body: str) -> list[str]:
    return help_sentences(body)


def _second_sentence(question: str, body: str, said: str) -> str:
    """One more sentence of the topic that shares a word with the question
    and is not the one already said, else ""."""
    wanted = {w for w in _WORD.findall(question.lower()) if w not in _STOP and len(w) > 2}
    for line in _help_sentences(body):
        if line == said or said.startswith(line) or line in said or len(line.split()) > SECOND_SENTENCE_WORDS:
            continue
        have = set(_WORD.findall(line.lower()))
        if any(h == w or (min(len(h), len(w)) >= 5 and (h.startswith(w) or w.startswith(h))) for w in wanted for h in have):
            return line
    return ""


def _guide_lead(question: str, topics: list[dict]) -> str:
    """The help sentence that best answers `question` (`composer.help_line`).
    Before the composer is loaded (a bare import of this module), the
    topic's first sentence leads: never an answer with no answer in it."""
    from tessellate.ai import capability

    if topics[0]["id"] == "privacy" and capability.privacy_line(question):
        return capability.privacy_line(question)
    line = act_registry.help_sentence(question, topics) if act_registry.help_sentence else None
    lead = line[0] if line else next(iter(_help_sentences(topics[0]["body"])), "")
    #: "Or type the reminder, ...": the topic's joining word is not the
    #: answer's first word.
    joined = re.match(r"(?:Or|And|But|Also|So),? (?=[a-z])", lead)
    return lead[joined.end()].upper() + lead[joined.end() + 1:] if joined else lead


def _guide_opening(question: str, path: str, steps: tuple, lead: str) -> tuple[list[str], bool, bool]:
    """The answer's first lines, and whether it said the place and walked
    the steps: where it is for a where-question; how many steps and where
    from for a how-to with steps; else the lead sentence."""
    where = bool(path) and bool(_WHERE_ASKED.match(question))
    walk = bool(steps) and bool(_HOW_ASKED.match(question)) and len(steps) < len(_COUNTS)
    lines = [f"It's in {_place(path)}."] if where else []
    if walk:
        lines.append(f"It takes {_COUNTS[len(steps)]} steps" + (f", from {_place(path)}:" if path else ":"))
    elif lead:
        lines.append(lead)
    return lines, where, walk


#: A topic that is about a switch, and the switch: its preference, its
#: default and its name. The Guide says which way it is set now ("how do I
#: turn on web search" when it is on is answered "Web search is on now").
_SWITCHES: dict[str, tuple[str, bool, str]] = {
    "websearch": ("web_search_enabled", False, "Web search"),
    "autonomous": ("autonomous_tasks_enabled", False, "Background AI"),
}


def _preference(key: str, default: bool) -> bool:
    try:
        from tessellate.core import deps

        return bool(deps.get_config().get_preference(key, default))
    except Exception:  # noqa: BLE001  # no config (a bare import): say nothing of the state
        return default


def _state_line(topic_id: str) -> str:
    """"Web search is off now.": the switch a topic is about, as it is set."""
    switch = _SWITCHES.get(topic_id)
    if switch is None:
        return ""
    key, default, name = switch
    return f"{name} is {'on' if _preference(key, default) else 'off'} now."


def _stated_lead(question: str, topics: list[dict]) -> str:
    """The lead, after the switch's state when the topic has one; a lead
    that only gives the default ("off by default") gives way to the next
    sentence that answers, since the state now says it."""
    state = _state_line(topics[0]["id"])
    lead = _guide_lead(question, topics)
    if state and re.search(r"\bby default\b", lead):
        lead = _second_sentence(question, topics[0]["body"], lead) or lead
    return " ".join(x for x in (state, lead) if x)


def composed_answer(question: str, topics: list[dict]) -> str:
    """The Guide's answer composed for `question` from the best topic."""
    first = topics[0]
    meta = TOPIC_META.get(first["id"], {})
    path = str(meta.get("path") or "").rstrip(".")
    steps = tuple(meta.get("steps") or ())
    lead = _stated_lead(question, topics)
    lines, where, walk = _guide_opening(question, path, steps, lead)
    more = "" if steps else _second_sentence(question, first["body"], lead)
    lines += ["\n".join(f"{n}. {step}" for n, step in enumerate(steps, 1))] if steps else [more] if more else []
    if path and not where and not walk:
        lines.append(f"**Where:** {path}")
    related = [topic_title(topic) for topic in topics[1:]]
    if related:
        lines.append("**Related:** " + ", ".join(related))
    return "\n\n".join(lines)


def offline_answer(
    question: str,
    tab: str | None = None,
    context: str | None = None,
) -> dict:
    """The same shape `answer` returns, composed without a model.

    `content`, `badges` and `sources` all come from the matched topics, so an
    offline reply carries the same quick-access chips and the same named
    sources an online one does: the chips are what turn "reminders live on the
    Reminders tab" into a way to get there, and they are exactly as true with
    the model off.
    """
    question = (question or "").strip()[:MAX_MESSAGE_CHARS]
    social = social_reply(question)
    if social:
        return social
    question, said = _read_as(question)
    #: Read from the words, not the tab (B11, B86): asked for ideas, for help,
    #: or what Atlas can change. Understood, so "Taking that as" is not said.
    from tessellate.ai import guide_intent

    read = guide_intent.reply(question, tab, {topic["id"]: topic for topic in HELP_TOPICS})
    if read:
        read["content"] = f"{read['content']}\n\n{OFFLINE_LEAD}" if not read.get("greeting") else read["content"]
        return read
    if guide_intent.read(question):
        said = ""
    topics = topics_for(question, tab) if question else []
    if not topics:
        #: The app's help text for whatever is on screen, when there is any:
        #: a question this could not place is still a question asked *from
        #: somewhere*, and that somewhere describes itself.
        on_screen = (context or "").strip()[:MAX_CONTEXT_CHARS]
        if on_screen:
            return {
                "content": f"{on_screen}\n\n{OFFLINE_LEAD}",
                "badges": [],
                "sources": [],
            }
        return {"content": OFFLINE_NOTHING_MATCHED, "badges": [], "sources": []}
    #: **Composed by default, the help text a tap away** (INBOX 787). The
    #: composed answer is the content; `system` is the topic as written
    #: (INBOX 430's layout), which the client offers as "From the help".
    system = system_answer(topics)
    return {
        "content": f"{said}{composed_answer(question, topics)}\n\n{OFFLINE_LEAD}",
        "badges": badges_for(topics),
        "sources": source_names(topics),
        "system": system,
    }


def _read_as(question: str) -> tuple[str, str]:
    """The question with its misspellings put right, and the line that says
    so ("Reading that as ..."), as the composer's answers open (ledger row
    404): "hwo do i set a remnder" gets the steps "how do I set a reminder"
    gets, not the topic's first sentence."""
    from tessellate.ai import composer_ack, question_noise

    fixed: list = []
    repaired = question_noise.repair(question_noise.tidy(" ".join(question.split())), fixed=fixed) if question else question
    if not fixed:
        return question, ""
    said = "".join(part[1] for part in composer_ack.acknowledge(repaired, voice="natural", seed=question))
    return repaired, said


def answer_stream(
    question: str,
    model_manager: ModelManager,
    ollama: Provider,
    history: list[dict] | None = None,
    tab: str | None = None,
    context: str | None = None,
) -> Iterator[dict]:
    """The same turn, streamed.

    Reported: the Guide's reply "will be blurted out really fast like it isnt
    streaming but just outputting at once", and its thinking "only shows up
    after the response is finished". Both were true and neither was a bug in
    the client: `/help/ask` answered in one piece after the whole reply had
    been generated, and the panel faked the writing with a timer, which is
    why it ran at a speed no model types at and why the thinking could not
    appear until there was nothing left to wait for.

    Yields `{"type": "thinking"|"delta", "text": str}` as the model produces
    them and one closing `{"type": "done", ...}` carrying the badges and
    sources, which are known before the first token but are sent last so the
    client has one place to finish a turn.
    """
    question = question.strip()[:MAX_MESSAGE_CHARS]
    if not question:
        yield {"type": "done", "content": "", "badges": [], "sources": []}
        return
    if not ollama.is_running():
        #: Not a canned apology: the app's own help text for what was asked,
        #: with the same chips and sources an answered turn carries. See
        #: `offline_answer`.
        offline = offline_answer(question, tab, context)
        yield {"type": "delta", "text": offline["content"]}
        yield {"type": "done", **offline}
        return

    messages, topics = _prompt_for(question, history, tab, context)
    pieces: list[str] = []
    #: `GUIDE_MODE` rather than `"quick"`: same brevity, same temperature,
    #: but thinking is not turned off, so the `thinking` events below are
    #: events that can actually happen. Under `"quick"` this loop's
    #: `thinking_delta` branch had never once run on a real backend.
    for piece in ollama.chat_stream(
        model_manager.utility_model(), messages, mode=presets.GUIDE_MODE
    ):
        thinking = piece.get("thinking_delta")
        if thinking:
            yield {"type": "thinking", "text": thinking}
        delta = piece.get("content_delta")
        if delta:
            pieces.append(delta)
            yield {"type": "delta", "text": delta}
    content = "".join(pieces).strip()
    yield {
        "type": "done",
        "content": content,
        "badges": badges_for(topics),
        "sources": source_names(topics),
        "system": system_answer(topics),
    }


def answer(
    question: str,
    model_manager: ModelManager,
    ollama: Provider,
    history: list[dict] | None = None,
    tab: str | None = None,
    context: str | None = None,
) -> dict:
    """One turn of the help chat.

    `history` is whatever the caller is holding client-side for the current
    session (see module docstring): never read from or written to the
    database. `tab` is the surface the question was asked from and `context`
    that surface's own help copy, both optional and both only ever used to
    choose and extend the reference notes. Returns
    `{"content": str, "badges": list[dict]}`."""
    question = question.strip()[:MAX_MESSAGE_CHARS]
    if not question:
        return {"content": "", "badges": [], "sources": []}
    if not ollama.is_running():
        return offline_answer(question, tab, context)

    messages, topics = _prompt_for(question, history, tab, context)
    #: Still `"quick"`, not `GUIDE_MODE`: this is the one-shot fallback, taken
    #: only when a stream could not be opened, and it returns one object at the
    #: end. There is nowhere for thinking to be shown on this path, so paying
    #: a reasoning model to produce it would buy the reader nothing but a wait.
    #: The Guide's own preset, as `answer_stream` uses: this is the fallback
    #: path for the same panel, and it asked for "quick" (Quick's cap, no
    #: thinking) until INBOX 410's cap test caught the two disagreeing.
    reply = ollama.chat(model_manager.utility_model(), messages, mode=presets.GUIDE_MODE)
    content = reply["content"].strip()
    return {
        "content": content,
        "badges": badges_for(topics),
        "sources": source_names(topics),
        "system": system_answer(topics),
    }


# --- the app's own help, for the Chat tab and the agents --------------------
#
# Asked for directly: "give the chat tab chat ai and agent access to the help
# info as well in case users ask it questions for help". Reported beside it,
# with a screenshot: "how should I use the knowledge graph??" in Chat was
# answered from the notes ("none of them specifically explain how to use a
# knowledge graph"), because the Guide panel was the only thing that could
# read these entries.
#
# **Gated twice.** Topic keywords include everyday words ("note", "chat",
# "question"), so a keyword match alone would attach help to nearly every
# question about the notebook. The question has to be phrased as a how-to
# (`_HOW_TO`) *and* name a topic. Two entries at most, clipped, and carried
# with the question rather than in the system prompt, so the cached prefix
# stays byte-identical turn to turn.
_HOW_TO = re.compile(
    r"\b(how (do|can|should|would) (i|you|we)|how to|what can (i|you)|what does|"
    r"what is the|where (is|are|do|can)|is there a way|can (i|you)|help me|explain)\b",
    re.IGNORECASE,
)
HELP_BLOCK_MAX_TOPICS = 2
HELP_BLOCK_MAX_CHARS = 1400


def names_app(question: str) -> bool:
    """Whether a how-to the notes could not answer plainly names a part of the
    app: a keyword of several words ("connect a model"), or two keywords of
    the topic it matches. One single-word keyword is not enough: "how do I
    learn python" matches Code files on "python", and "how can I improve my
    sleep" Capture on "improve" (O1, measured 2026-10-17)."""
    if not question or not _HOW_FRAME.match(question):
        return False
    topics = _matching_topics(question)
    if not topics:
        return False
    lowered = question.lower()
    hits = [k for k in topics[0]["keywords"] if _keyword_in(k, lowered)]
    return len(hits) >= 2 or any(" " in k.strip() and not _HOW_FRAME.match(k) for k in hits)


def help_block_for(question: str) -> str:
    """The app's own help for a how-to question, as a block to put before it,
    or "" when the question is not asking how the app works."""
    if not question or not _HOW_TO.search(question):
        return ""
    topics = _matching_topics(question)[:HELP_BLOCK_MAX_TOPICS]
    if not topics:
        return ""
    text = "\n".join(f"- {topic_title(topic)}: {topic['body']}" for topic in topics)
    if len(text) > HELP_BLOCK_MAX_CHARS:
        text = text[: HELP_BLOCK_MAX_CHARS - 1].rstrip() + "…"
    return (
        "From Tessellate's own help (use this if the question is about how the "
        f"app works; it is not one of my notes):\n{text}\n\n"
    )
