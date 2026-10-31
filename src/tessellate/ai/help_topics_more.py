"""The Guide's reference, part two: every Settings section, the companion, the
faces, and the app's layout, plus how each entry is laid out as an answer.

INBOX 430 (the owner): "expand the help content massively, covering every
tab, setting and feature", after the Guide told him the corner companion was
"a feature within the Ask tab". It had nothing to say about the companion at
all, so a model with no reference guessed. The rule stays the one
`help_chat.HELP_TOPICS` states: an entry is the model's only source of facts
about the app, so each one here was written from the running app's own
controls and their own wording (Settings, section by section), not from
memory of what the app used to do.

`MORE_TOPICS` joins `HELP_TOPICS` (help_chat.py); `TOPIC_META` gives every
entry, old and new, the parts the system answer is laid out from
(`help_chat.system_answer`): a title, the path to where it lives, the steps
where there are steps, and the settings row a link opens (`target`, the row's
id, which `openSettingsModal(section, target)` scrolls to and lights).
"""

from __future__ import annotations

MORE_TOPICS: list[dict] = [
    {
        "id": "companion",
        "keywords": (
            "companion", "corner companion", "buddy", "mascot", "sidekick",
            "little character", "character in the corner", "call back",
            "call it back", "hide the companion", "show the companion",
            "companion size", "the little guy", "rub the companion", "flip the companion",
        ),
        "body": (
            "The corner companion is a small character that lives on the page, "
            "not in any tab: it finds a free spot on each page, perches on a "
            "panel or a toolbar and rides with it as the page scrolls, reacts "
            "to what you do (you type, it keeps quiet company; you idle, it "
            "plays), and naps when you are away. It steps out of the "
            "way of menus, popups and the guided tour. Choose who it is in "
            "Settings, Appearance, Atlas and faces, Corner companion: Off, "
            "You, The chat's persona, Atlas, or Your own character (a name and "
            "parts of its own). Companion size is Small, Medium or Large, or "
            "drag the handle at its corner (double-click or double-tap the handle "
            "for Medium again); the size is marked On this device, so a phone "
            "keeps its own. Drag it onto a panel and that page "
            "keeps it there on this device; throw it (let go while moving fast) and it flies, "
            "bounces off the window's edges and stays where it lands. Move the pointer back and forth over it to rub it "
            "and it leans into your hand; shake it up and down while you carry "
            "it and it turns upside down, then lands a little dizzy (each has a "
            "switch in Appearance, under What it does on its own). When it has "
            "something on (headphones while a sound plays, a bell for a "
            "reminder, a moon on its ear as it rests), rest the pointer on it and its "
            "tooltip says what and why. Its large view (double-click it) has a "
            "row of things to ask of it: wave, cheer, hop, stretch, shrug or "
            "wiggle, and Atlas also juggles stars, reads its map and "
            "meditates. Right-click it, or press Shift+F10 on it, for its "
            "menu: Say hello, Enlarge, Stay here on every page, Let it choose "
            "its spot here, a size, Call back and reset its place, and Hide. "
            "Ctrl+Shift+Y shows or hides it from anywhere, and the command "
            "palette and Find anything have Show or hide the companion. If it "
            "is ever out of reach, Call back (beside the setting, in its menu "
            "or in the command palette) brings it back."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-travel",
        "keywords": (
            "companion portal", "companion puff of smoke", "companion vanishes",
            "companion walks off the screen", "companion ducks under the bar",
            "companion moves too much", "companion distracting", "companion travels",
            "companion sneezes", "companion grooms", "companion sighs",
        ),
        "body": (
            "The corner companion travels rarely and never while you type or "
            "carry it. When it has somewhere far to go it takes a calm way: it "
            "opens a portal and walks through, vanishes in a puff of smoke, walks "
            "off one side of the window and comes in at the other, or ducks "
            "behind a bar and climbs down from the other. Never the same way "
            "twice in a row. The rest of the time it sits, looks around, "
            "stretches, yawns, grooms, sniffs, sighs or shakes itself off. With "
            "Reduce motion on, or Interface animations off, it only fades or "
            "stays put. To keep it still, set Corner companion to Off in "
            "Settings, Appearance, Atlas and faces."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-throw",
        "keywords": (
            "throw the companion", "flick the companion", "throwing the companion",
            "companion splat", "companion climbs", "companion hangs from the top bar",
            "companion went off the screen", "companion lies down", "companion slips off",
            "companion went off the top", "companion tumbles",
        ),
        "body": (
            "Throw the corner companion by letting go of it while it is still "
            "moving fast. It flies, bounces off the window's edges and stays "
            "where it lands, and now and then something else happens: it "
            "catches the top bar and hangs from it, grabs a panel's top edge "
            "and climbs on, catches the end of a panel as it falls past or "
            "slides off one and pulls itself up, splats against a side of the "
            "window and slides "
            "down to the panel below, or goes off one side and comes back on "
            "the other. How you throw it chooses: a soft toss lands near, a hard "
            "one sideways can go far or into a corner, and a hard one upwards "
            "can leave the top of the window and fall back in. A panel only "
            "catches it when it comes down slowly, and it may land, slide off "
            "or tumble and get up. Once down it settles in its own way: sitting with its "
            "legs dangling or kicking, lying down, stretching, or swinging "
            "from the bar. Wherever it ends, it never covers a button: come "
            "down on one and it moves only to the nearest clear place. With "
            "Reduce motion on, it simply appears where it lands."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "what-is-atlas",
        "keywords": (
            "what is atlas", "who is atlas", "what does atlas do", "what can atlas do", "about atlas",
            "meet atlas", "atlas assistant",
        ),
        "body": (
            "Atlas is the assistant inside Tessellate. It answers questions from your notes and cites them, "
            "files new notes, sets reminders, finds, tags, moves and links notes (a change that cannot be "
            "taken back waits for your Confirm), and opens the part of the app you name. Ask lives in Notes, "
            "Chat has its own tab, and Ctrl+Shift+A opens it over any tab, where its paperclip, a drop or a paste adds files as chips. With no model connected it "
            "answers from your notes by itself."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "atlas-look",
        "keywords": (
            "atlas look", "atlas style", "classic globe", "globe", "atlas character",
            "atlas's face", "atlas mood", "atlas moods", "masculine", "feminine",
            "what does atlas look like", "change atlas", "atlas avatar",
            "assistant avatar", "app emblem", "reply avatar", "chat avatar", "app logo",
        ),
        "body": (
            "Atlas is drawn as a small character of starlight with rings "
            "round its head, or, if you prefer, as the classic glowing globe: "
            "Settings, Appearance, Atlas and faces, Atlas style. Atlas look "
            "picks Masculine or Feminine, or Auto, which follows Face looks "
            "when that is set to one look and your own face's look otherwise; "
            "it is used everywhere Atlas appears, the dashboard mark and the "
            "chat's replies included. Assistant avatar, in the same place, swaps "
            "the face on the assistant's chat replies, the popup agent and the "
            "guide between Atlas and the app's animated emblem (it holds still "
            "under Reduce motion or with Interface animations off); other "
            "personas keep their own faces. "
            "Atlas's face follows the app's mood: "
            "thinking while an answer runs, happy when it lands, worried at an "
            "error, sleepy late at night. Enlarge, in the companion's menu or "
            "on any face, shows the full drawing; right-click the companion "
            "there to change who it is, its look or its size."
        ),
        "badge": {"label": "Atlas look", "section": "appearance", "target": "atlas-look-row"},
    },
    {
        "id": "faces",
        "keywords": (
            "avatar", "avatars", "generated face", "profile picture", "face looks",
            "avatar animation", "faces follow", "follow the pointer", "persona face",
            "dashboard mark", "faces", "blinking", "my face",
        ),
        "body": (
            "Every person, persona and chat gets a generated face, drawn from "
            "its name: a name that says a mood (\"sleepy wizard\") or an animal "
            "gets that face, and any other name still gets a character of its "
            "own, the same one every time, and each character wears a mood in "
            "its own way. Settings, Appearance, Atlas and faces: Avatar "
            "animation (Always, On hover, Off) lets faces blink and act out "
            "their mood, Faces follow the pointer turns eyes and heads toward "
            "your mouse, Face looks sets hair, brows and jaw (Neutral, "
            "Masculine, Feminine; never read from a name), and Dashboard mark "
            "swaps the dashboard's logo for a face. Your own face is in "
            "Settings, Profile, Your look: Shuffle redraws it, and Choose parts "
            "yourself sets any part by hand. Reduce motion stops the animation."
        ),
        "badge": {"label": "Atlas and faces", "section": "appearance", "target": "avatar-motion-row"},
    },
    {
        "id": "profile",
        "keywords": (
            "profile", "my profile", "my name", "display name", "your look",
            "shuffle", "change my name", "what to call me", "greeting name",
        ),
        "body": (
            "Settings, Profile is you, kept on this computer: Your name (shown "
            "in the greeting and on your mark), Your look (your face, drawn "
            "from your name; Shuffle redraws it and Back to my name's own "
            "undoes that, Choose parts yourself sets each part), and About me, "
            "which Atlas reads for more personal answers only while \"Let Atlas "
            "read your name and About me\" is on. Delete my profile data clears "
            "it; answers just get less personal."
        ),
        "badge": {"label": "Profile", "section": "preferences"},
    },
    {
        "id": "tools-setting",
        "keywords": (
            "tools it can use", "which tools", "turn off a tool", "disable a tool",
            "small model mode", "run budget", "tool list", "tokens per step",
            "tools offered", "using a tool", "use a tool", "stop atlas using",
            "cut that reply short", "model size", "does atlas do sums",
        ),
        "body": (
            "Settings, Tools it can use also has Use these tools from another "
            "app: a snippet to paste into an MCP client such as Claude Desktop, "
            "with a Copy button; that client can also read your notes (never "
            "a private one) and use your skills as prompts. "
            "A number Atlas would work out (a sum, a percentage, a conversion, a "
            "count of days) comes from the app's own calculator, Calculate, and a "
            "date in your words from Read text, so a small model computes "
            "nothing in its head; Check answer finds any number its answer "
            "says that the notes do not, and Propose act shows a change as "
            "a card you confirm. "
            "Settings, Tools it can use lists the actions Atlas may take in "
            "Agent mode, grouped as Reads your notebook, Changes your notebook, "
            "Asks you first and Reaches the web; turn one off and it is never "
            "offered. Destructive "
            "actions always ask you first, and once Atlas has read a web page, "
            "a file, or a note clipped or imported from outside, every change "
            "and every web request asks too. How many are offered at once: Only "
            "what the message needs (the default) or Always send all of them, "
            "if Atlas ever misses a tool you asked for. Small model mode offers "
            "a small model one tool at a time (Auto decides from the model's "
            "name, On, Off). Run budget caps what one skill run may spend, in "
            "tokens per step and in seconds; 0 means no limit. A skill may also "
            "cap its own tool calls and steps; a run that passes a cap stops, "
            "says which, and keeps its changes for Undo. With small model mode "
            "on, a skill measured below 80% on small models shows Needs a "
            "larger model, with why. In Agent mode "
            "the model's size, read from its name, decides how many tools it "
            "sees and how long one step may write: under 3B and up to 8B get "
            "a short toolbox and a reply that runs long is cut short, 8B and "
            "up get everything."
        ),
        "badge": {"label": "Tools it can use", "section": "tools"},
    },
    {
        "id": "learned",
        "keywords": (
            "what it learned", "learned", "worked out", "derived", "forget everything learned",
            "learned from you", "filing accuracy",
            "read my notes now", "export what it learned",
            "while you were away", "disagree", "contradict", "answered later",
        ),
        "body": (
            "Settings, What it learned is what Atlas worked out by itself while "
            "reading your notes (a claim a note makes, a question it leaves "
            "open, two claims in different notes that disagree, a question a "
            "later note answers), where What it remembers is what you told it. "
            "The Dashboard's While you were away card counts each kind from the "
            "last read; a pair shows the other sentence under it, a button to "
            "open the other note and, for a disagreement, one to link the two "
            "notes as disagreeing. Every row "
            "says which note it came from, which model decided it and how sure "
            "it was. Edit a row and no later run overwrites it; delete one and "
            "it is never worked out again. What may run switches each kind off; "
            "Read my notes now runs it; Export what it learned and Forget "
            "everything learned act on all of it and never touch your notes. "
            "The Learned from you line under the title counts your corrections "
            "and gives filing accuracy, the share of the notes Atlas filed that "
            "you left where it put them, older half of the last 200 against newer."
        ),
        "badge": {"label": "What it learned", "section": "learned"},
    },
    {
        "id": "make-a-diagram",
        "keywords": (
            "make a diagram", "draw a diagram", "diagram of", "a diagram", "create a diagram",
            "diagram without a model", "flowchart", "draw a flowchart", "chart of my plan",
            "plan as a diagram", "map out", "visualise my notes", "visualize my notes",
        ),
        "body": (
            "With no model, two places make a diagram. Library tab, Create, New mind map "
            "opens a map you type into (Tab adds a child, Enter a sibling), and its "
            "templates, Trip plan among them, start you with branches in place. "
            "Insert, Mermaid diagram on a board takes a few lines of text and draws a "
            "flowchart, sequence, state, Gantt or pie chart live. A note's menu, "
            "Make a mind map, builds a map from that note's headings and lists. "
            "The Writing room's diagram needs a model for anything beyond a rule-made "
            "flowchart, timeline or mind map."
        ),
        "badge": {"label": "Mind maps", "tab": "library"},
    },
    {
        "id": "open-questions",
        "keywords": (
            "open questions", "questions view", "unanswered", "undecided", "still undecided",
            "answered by", "mark answered", "drop a question", "ask about these",
            "find questions", "generate questions", "read notes now",
            "questions without a model", "i wonder", "need to find out",
            "questions my notes leave open", "leave open", "left open", "unanswered questions",
            "questions in my notes", "questions i have not answered", "questions i haven't answered",
            "still unanswered", "left unanswered", "unanswered in my notes",
        ),
        "body": (
            "Notes, Questions lists the questions your notes ask in passing, "
            "your own ones only (not a quote, a prompt list, a script's line or "
            "a joke answered on the next line), "
            "found when Atlas reads your notes (Read notes now, which says how many it "
            "read and found, or on its own "
            "with background tasks on), grouped by note, newest note first: "
            "Open, Answered or Dropped, picked in the bar with a count on each. A "
            "note that asks any says so on its card (2 open questions); pressing "
            "that shows only its questions. A row says when it was asked; when a "
            "later note answers it, the row "
            "says so with the sentence, and pressing that line opens the note. "
            "Mark answered asks which note answers it and links the two notes; "
            "Drop puts a question aside; Reopen brings either back. With no "
            "model the reading is by rule: a sentence ending in a question mark, "
            "or one that says I wonder, not sure if, need to find out, should I "
            "or how do I; a later note on the same thing that states it marks "
            "it answered. Ask about "
            "these opens Ask answering from the notes with open questions only "
            "(Ask all notes under the box goes back). The Dashboard's While you "
            "were away card counts the open ones and names the oldest."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "general-settings",
        "keywords": (
            "smart quotes", "link offers", "offer links", "auto clear",
            "empty the bin", "delete old chats", "chat history", "mute notifications",
            "general settings", "seasons", "hemisphere", "southern hemisphere", "summer", "winter",
        ),
        "body": (
            "Settings, General. Calendar: First day of the week, and Seasons, which half of the year "
            "summer, winter, spring and autumn mean (northern or southern hemisphere; automatic follows "
            "your language and region, so en-AU, en-NZ and en-ZA read summer as December to February). "
            "Bin: auto-clear binned notes, documents, reminders and OCR readings after a "
            "number of days. Chat history: delete saved chats after a number "
            "of days (0 keeps every chat; pinned chats are never deleted). "
            "Notifications: mute everything except reminders. Writing: smart "
            "quotes and dashes in documents, Check link text (spelling and grammar skip the words "
            "of a link unless it is on), and offers to turn a named note or document into a link "
            "(switch them off there, or press Never offer a link to this name on one offer; Offer them "
            "again brings every kept name back). Answer style moved to Settings, "
            "Personas, and Search relevance to Settings, Search and index."
        ),
        "badge": {"label": "General", "section": "general"},
    },
    {
        "id": "search-index",
        "keywords": (
            "search relevance", "minimum similarity", "above-average margin",
            "search engine", "semantic search", "embedding model", "re-index",
            "embedding models", "multilingual search", "change embedding model",
            "pull a model", "pull a model by name", "found on this computer",
            "uninstall embedding model", "reinstall embedding model", "cached models",
            "files missing", "model files incomplete",
            "rebuild search index", "search index", "search is wrong",
            "too many results", "too few results", "search feels too strict",
            "download search by meaning", "no thanks", "refuse download", "turn on search by meaning",
            "cancel install", "fastembed", "130 mb download", "search model download",
        ),
        "body": (
            (
                "Settings, Search and index. Search engine: the built-in one (recommended, about 300 MB "
                "of memory while the app is open) or an Ollama embedding model such as nomic-embed-text. "
                "The built-in one needs the fastembed package (ONNX Runtime, no PyTorch) and a small model "
                "from huggingface.co, about 130 MB in all. Nothing is downloaded without a yes: the first time a "
                "save needs it Tessellate asks once, with Download and No thanks, and search uses "
                "keywords until you say yes. The switch Download search by meaning turns it on later, "
                "or off again, and Settings, Packages keeps a manual Install. Changing the engine re-reads every note in the background "
                "(Background tasks shows it, with Stop) and search keeps using the current model until "
                "the new one has read every note. Embedding models lists the choices, from MiniLM "
                "(smallest, fastest) and BGE Small (the default) to multilingual ones (Multilingual E5, "
                "BGE M3, Qwen3), with each one's size, languages, context and licence, and its state "
                "(Downloaded with its size on disk, Not downloaded, or Files missing, with Reinstall; "
                "Settings, Packages points here): Use switches in one press, and a model under other "
                "terms (EmbeddingGemma) links to them instead; each row's ⋮ has Use, Install or "
                "Reinstall, and Uninstall (refused on the model in use). Found on this computer lists "
                "embedding models already here (the Hugging Face cache, Ollama, LM Studio), with Use "
                "where Tessellate can load them and why not where it cannot. Pull a model by name takes a"
                " Hugging Face repo (owner/name) or an Ollama name and checks it online only when you "
                "press Pull. Search index: Rebuild search index after an update or a restore, or if "
                "search stops finding notes you know are there. Search relevance: Minimum similarity and "
                "Above-average margin; raise them for fewer, surer results, lower them if search feels "
                "too strict, and Reset to default undoes both."
            )
        ),
        "badge": {"label": "Search and index", "section": "searchindex"},
    },
    {
        "id": "search-engine-moved",
        "keywords": (
            "search engine moved", "engine moved", "upgraded from pytorch", "old search engine",
            "pytorch", "torch", "sentence-transformers", "old search files", "old model files",
            "remove old models", "free disk space", "why download again", "download again",
        ),
        "body": (
            (
                "After an upgrade from a version that ran search by meaning on PyTorch, the question about "
                "downloading it says the engine moved. The old model files do not work with the new engine, "
                "so it is one download (about 130 MB for BGE Small) that replaces them, asked first, with "
                "keyword search working meanwhile. Notes made with BGE Small or Multilingual E5 Small keep "
                "their search data; notes made with any other model are read again in the background. Once "
                "the new model is ready, Settings, Search and index, Old search files lists the old model "
                "folders with their sizes and Remove deletes one; in the packaged app it also removes PyTorch "
                "and sentence-transformers. Nothing else changes."
            )
        ),
        "badge": {"label": "Search and index", "section": "searchindex"},
    },
    {
        "id": "answer-style",
        "keywords": (
            "answer style", "concise", "detailed", "shorter answers",
            "longer answers", "friendly", "professional wording", "formal wording",
            "natural wording", "wording when no model", "composer voice",
            "voice", "playful", "plain answers", "neutral", "how atlas sounds",
            "insight", "patterns in answers", "what atlas adds",
            "long text in an answer", "wall of text", "folded text",
        ),
        "body": (
            "Settings, Personas, Answer style: how Atlas words its answers, "
            "Friendly (the default), Concise or Detailed, whichever persona is "
            "active. Below it, How Atlas sounds with no model picks the voice "
            "it answers from your notes in without a model: Warm and concise "
            "(the default), Neutral, Playful or Plain, with a sample under it. "
            "The facts and the sources are the same in every voice. What "
            "Atlas adds of its own sets whether an answer about a topic ends "
            "with a pattern from your notes: Nothing, One line (the default) "
            "or Everything it finds; each Not right raises the bar. A long "
            "block in any reply (the text read from a picture, say) is folded "
            "to one line, its first sentence and its length; press it to read "
            "the whole."
        ),
        "badge": {"label": "Answer style", "section": "personas", "target": "pref-style"},
    },
    {
        "id": "wrap-lines",
        "keywords": (
            "wrap lines", "wrap text", "wrap a table", "wrap code", "wrap a code block",
            "table scrolls sideways", "code scrolls sideways", "long lines in code",
            "wide table", "horizontal scroll", "don't wrap",
        ),
        "body": (
            "A wide table or a code block in an answer (and in a note's Read view) "
            "scrolls sideways. The Wrap lines button in the card's top bar, beside "
            "Copy, breaks the long lines instead, so nothing scrolls; Don't wrap "
            "(the same button, pressed) puts the scrolling back, which is what you "
            "want for code you mean to paste. Tables and code remember their own "
            "choice for the next one."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "background-tasks",
        "keywords": (
            "background tasks", "running now", "what is it doing", "job", "jobs",
            "battery", "battery-efficient", "save power", "quit the app",
            "quit tessellate", "quit memorymap", "stop the server", "close the app properly",
            "last run", "last ran", "background jobs", "job history", "did it run",
            "run now", "night shift", "stop a job", "cancel a job", "scheduled pass",
            "process log", "what did it do", "who started it",
            "what ran overnight", "when did i last back up",
        ),
        "body": (
            "Settings, Background tasks shows what the app is doing right now "
            "(re-indexing, downloading a model, installing packages, setting up "
            "search), each running job with a progress bar (a moving one when "
            "it cannot count its steps), how long it has run and who started it, "
            "with Stop on the jobs that can stop safely, and what has finished "
            "since it started, with how long it took. Every run, a chat answer "
            "or an Agent turn too, has its lines in a fold: what it searched, "
            "each tool it called, done; live while it runs. Background jobs lists every kind of job, the never-run "
            "ones too, with when it last ran and how it went; each scheduled "
            "pass (autonomous background AI, the night shift, the daily backup, "
            "resurfacing, the embeddings backfill, housekeeping) also says when "
            "it runs by itself and has Run now. Beside each "
            "control (Back up now, Rebuild search index, Find duplicates, the "
            "importers) a line reads, for example, \"Last run 2h ago, "
            "succeeded, 412 notes indexed\", with the exact time on hover; a "
            "failure says why in a few words. Ask \"what ran overnight\" or "
            "\"when did I last back up\" and the answer comes from these "
            "records, with times. Autonomous background AI is here "
            "too. Battery-efficient "
            "mode pauses background AI, heavy graph work and the moving "
            "artwork. Quit Tessellate stops the app and its server properly, so "
            "the next start finds its port free."
        ),
        "badge": {"label": "Background tasks", "section": "tasks"},
    },
    {
        "id": "health",
        "keywords": (
            "health", "is my notebook ok", "integrity", "integrity check", "corrupt",
            "corruption", "last backup", "last error", "data folder size", "how big",
            "is it healthy", "check the database",
        ),
        "body": (
            "Settings, About, Health says how the notebook is, each line dated: "
            "the last backup and when it was taken, the data folder's size, Files on disk (a bar of the notebook, attached files, pictures, backups and optional features), what "
            "is running now, the last error in the log, and Integrity, whose "
            "Check now has the database check itself and counts the search index "
            "beside your notes. The palette's Health goes straight there. The "
            "app also gives the notebook file a quick check each time it starts, "
            "and if that fails it says so and points to the newest backup in "
            "Settings, Import & export."
        ),
        "badge": {"label": "About", "section": "about"},
    },
    {
        "id": "maintenance",
        "keywords": (
            "maintenance", "check this computer", "doctor", "doctor.sh", "doctor.bat", "start --doctor",
            "reinstall", "reinstall on next start", "rebuild", "venv", "reinstall.sh", "tools.sh",
            "launcher logs", "open the launcher logs", "desktop shortcut", "make a desktop shortcut",
            "uninstall", "remove the app", "how do i uninstall",
        ),
        "body": (
            "Settings, About, Maintenance runs the launcher's own actions from "
            "the app. Check this computer runs the checks doctor.sh and "
            "doctor.bat print (Python, free disk, the port, the model server, "
            "the notes folder, the last launch) plus the search model and other "
            "devices, each row with a tick, a warning or a cross and what to do. "
            "Reinstall on next start rebuilds the app's Python environment the "
            "next time start.sh or start.bat opens the app, the same as "
            "reinstall.sh; your notes, settings and models are not touched, and "
            "Cancel takes it back. A copy from the installer has no environment "
            "to rebuild: its Repair shortcut is the way. Open the launcher logs "
            "opens the folder the launcher writes to, and Make a desktop "
            "shortcut makes the one start --shortcut makes. Uninstall… never "
            "removes anything itself: it shows the steps and the command for "
            "this computer with Copy, and Export my notes first. These work "
            "only on the computer the app runs on; on a phone they are off."
        ),
        "badge": {"label": "About", "section": "about", "target": "maintenance-group"},
    },
    {
        "id": "activity",
        "keywords": (
            "activity", "activity panel", "what is running", "stop a job", "stop it",
            "stop the model", "unload the model", "free memory", "model in memory",
            "stop generating", "stop the answer", "agent runs", "running jobs",
        ),
        "body": (
            "Activity lists every job running now: indexing, a model loading or "
            "answering, imports, reading text, transcribing, backups and the "
            "agent's passes, each with a bar, its lines and Stop where it can stop "
            "part way; every model call is listed, on its own or inside the job "
            "that made it. Under it, what finished in the last half hour says how "
            "it ended, how long it took and when, with its lines. While anything runs, the status bar's job slot says how "
            "many and names the newest. Open Activity from it, its agent runs count, or the "
            "palette (Activity). Its Agent runs tab lists each run this session "
            "with its steps, and the log is in its menu. Stop the model, in the "
            "menu and in Settings, Models beside Use this model, stops any answer "
            "and unloads the model from memory (Ollama drops it at once; the chat's Stop reaches the model too); a server "
            "this app did not start keeps its own model, and the message says so."
        ),
        "badge": {"label": "Models", "section": "models"},
    },
    {
        "id": "packages",
        "keywords": (
            "packages", "package", "pip", "install a feature", "optional feature",
            "extra", "extras", "dictation model", "embedding model", "markitdown",
            "bundle", "bundles", "reinstall", "uninstall", "install several",
        ),
        "body": (
            "Settings, Packages lists what Tessellate can do with one more "
            "package installed: nothing there is needed to write, search, tag "
            "or organise notes, each one switches on a feature that is "
            "otherwise off, downloaded from PyPI to this machine. Bundles "
            "group the packages one kind of work needs (Documents, Vision, AI, "
            "Voice, Desktop, Code, Languages): a bundle's Install fetches what is "
            "missing, and its ⋮ reinstalls or removes them all. Tick packages "
            "to install, reinstall or remove several at once from the bar "
            "above the list; they run one after another and one that fails "
            "does not stop the rest; a bundle's row shows each of its packages "
            "as it goes, waiting, installing or done. A notice that names Settings, Packages "
            "(a feature that is not installed) has an Open Packages button that scrolls to "
            "that package's row. An installed package's ⋮ has Reinstall "
            "(for a feature that is on but not working) and Remove (the "
            "packaged app keeps its Desktop window, so that row has Reinstall "
            "only), and its row shows its version and size on disk. What pip is "
            "doing shows an install as it runs. Dictation model size runs from "
            "Tiny (fastest) to Medium (most accurate); each size says whether it "
            "is on this computer, a size that is not downloads the first time "
            "you dictate with it (choosing it asks first, and nothing downloads "
            "until then), and Remove this size frees the disk. Skip silence before "
            "transcribing (on) stops Whisper writing words into the quiet around "
            "a clip; Dictation language skips the guess; Words to expect lists "
            "names and terms it should spell your way. Embedding models lists "
            "the built-in models on this machine, each downloaded once and kept; "
            "which one search uses is chosen in Settings, Search and index."
        ),
        "badge": {"label": "Packages", "section": "extras"},
    },
    {
        "id": "import-export",
        "keywords": (
            "import markdown", "import a folder", "import a pdf", "import word",
            "import as a document", "slide deck", "merge duplicates",
            "tidy up duplicates", "full backup", "restore a full backup", "mmenc", "seal a backup",
            "export csv", "export json", "exports folder", "zip",
        ),
        "body": (
            "Settings, Import & export. Export your data as JSON, CSV, Markdown "
            "or a full backup (the database, media and attached files as one "
            "file, sealed with a password if you type one: a .mmenc, else a "
            ".zip); Restore a full backup, just below, reads either back and "
            "replaces the notebook after a safety snapshot; Open exports "
            "folder and Save exports to set where files land. Tidy up "
            "duplicates finds notes that say much the same thing, no AI "
            "needed, and merging keeps every tag and bins the rest. Import "
            "markdown files or a folder (Obsidian frontmatter is understood), "
            "or a PDF, Word file or slide deck, one note per chapter or slide. "
            "To keep a file whole as a document you can edit instead, open "
            "Library, Documents, the more menu, Import a file as a document. "
            "Backups: Back up now, and how many to keep; one is also taken "
            "each day the app starts, and restoring snapshots first, so even a "
            "restore can be undone. A line above the list gives the schedule, when "
            "it last ran and whether that worked, and when the next is due; in the "
            "desktop app, Also copy each backup to sends a second copy to a folder "
            "you choose, such as an external drive. Each backup row says when in words, marks "
            "the newest Latest, and says what made it (the daily backup, Back "
            "up now, before an update or a restore), its size and whether it "
            "was checked. App cache, at the bottom: Clear app cache "
            "reloads the app with fresh files and never touches your notes."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "settings-reset",
        "keywords": (
            "reset a setting", "reset to default", "default setting", "changed setting",
            "reset section", "export settings", "import settings", "settings file",
            "copy my settings", "move my settings", "this browser", "which settings sync",
        ),
        "body": (
            "A setting changed from its default shows a bar at its left edge and "
            "a reset button at the end of its row, which puts that one setting "
            "back; Reset N changes, in the section's title bar, puts back every "
            "changed setting in that section. Performance mode, Text size, "
            "Density, Zoom and the companion's size, marked On this device, are "
            "kept only on the device you set them on (a phone and a computer "
            "each have their own zoom); the rest, your colours and fonts "
            "included, are kept in your notebook and follow you to every "
            "browser you sign in from. Settings, "
            "Import & export, Your settings: Export settings saves every setting "
            "as one .json file (no notes in it); Import settings reads one back, "
            "applies each setting it can, adds its skills, personas and templates "
            "to yours by name, says which it skipped and why, and offers Undo."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "logs",
        "keywords": (
            "logs", "log", "support bundle", "report a bug", "bug report", "error report",
            "send a report", "email support", "send you my logs", "diagnostics", "copy diagnostics",
            "something is slow", "app is laggy", "lag report",
        ),
        "body": (
            "Settings, Logs shows what happened, for when something did not "
            "work: filter by source and level, follow new lines, copy or clear "
            "them. The ? beside the three dots in its bar says what each control "
            "does. The support bundle collects the logs and the app's state; "
            "Email it opens a message to support with the bundle to attach. "
            "To send the logs for something slow or broken, open the three dots in "
            "the Logs bar and press Copy diagnostics (or Save diagnostics as file), "
            "or run Copy diagnostics from the palette: one plain-text report of lag "
            "with its cause, errors, slow routes and how big the notebook is, with "
            "no note text, that you paste into a message."
        ),
        "badge": {"label": "Logs", "section": "logs"},
    },
    {
        "id": "find-anything",
        "keywords": (
            "find anything", "ctrl p", "finder", "find a note fast", "find a file",
            "jump to a note", "saved searches", "find a chat",
        ),
        "body": (
            "Find anything (Ctrl+P, or the magnifying glass in the status bar) searches notes, "
            "files, documents, chats and actions in one box as you type: Enter opens "
            "the top result, the arrows move, Esc closes, and the star keeps the "
            "search as a row under Saved searches in the Notes sidebar. Sort has Best "
            "match, Group by category (a note under its category, the rest under "
            "their kind), Newest first and Oldest first. Its '?' lists "
            "the operators. It lists the command "
            "palette's actions too, so \"dark\" finds Toggle light/dark, after the "
            "notes and files. The command palette (Ctrl+K) sends what you type "
            "here: its last row, Search everything for, opens this box with "
            "the words already searched. As you type it suggests your recent searches, "
            "then note titles, tags and categories, with the best match in grey: Tab or "
            "Right takes it, and Settings, General, Search turns it off."
        ),
        "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
    },
    {
        "id": "background-art",
        "keywords": (
            "animated background", "background animation", "moving background",
            "wallpaper", "background style", "constellation", "fireflies",
            "rain background", "lightest background", "background cost",
            "wander", "drift", "pen strokes", "paused background",
        ),
        "body": (
            "Settings, Appearance, Animated background: Style is a card per "
            "art, lightest first, each with a preview and its cost, Light, "
            "Medium or Heavy, from what one frame takes; picking a card turns "
            "the background on. Wander draws pen strokes that walk and fade; "
            "Drift is slow colour noise. A background that has been paused for "
            "20 seconds (hidden window, idle, covered) becomes a picture of itself "
            "and carries on when you come back. Movement sets how much it moves and Intensity "
            "how strong it is. Page background in Theme & colour sets the "
            "colour under it. Performance mode and Battery-efficient mode both "
            "stop it, and so does Reduce motion."
        ),
        "badge": {"label": "Animated background", "section": "appearance", "target": "bg-style-row"},
    },
    {
        "id": "themes",
        "keywords": (
            "save a theme", "my own theme", "custom css", "text size",
            "corner rounding", "zoom level", "colour scheme", "color scheme",
            "build a scheme", "border style", "shadow", "interface animations",
        ),
        "body": (
            "Settings, Appearance. Themes: press the eye in a theme's corner to see it on the whole app, then Apply or Cancel, "
            "press Surprise me for a random one, save and switch your own. Theme & "
            "colour: Palette, Mode (light, dark or system), Accent colour or a "
            "custom one (a colour a button's words cannot be read on is "
            "offered at the nearest shade that can), Page background, and "
            "Build a scheme from one colour. "
            "Typography & layout: Text size, Font (System, Serif, Mono, Arial, "
            "or Readable, the Atkinson Hyperlegible face), Density, Corner rounding, "
            "Zoom, Border style and Shadow intensity (Text size, Density and Zoom "
            "are marked On this device: a phone and a computer each keep their "
            "own, while colours and fonts follow you). Effects & accessibility: "
            "Performance mode, the glass's sheen, blur and opacity, Progress "
            "indicators, Reduce motion (stills Atlas, the background art, the "
            "graph and the whiteboard) and Interface animations (on by default: "
            "a button's press, menus and dialogs opening, a tab's sliding marker, "
            "even with Reduce motion on; off makes them instant) with Reveal "
            "replies under it (a reply no model wrote rises into place). Advanced has "
            "Custom CSS. Ctrl+Shift+L "
            "switches light and dark from anywhere."
        ),
        "badge": {"label": "Appearance", "section": "appearance"},
    },
    {
        "id": "tabs-overview",
        "keywords": (
            "tabs", "what tabs", "overview", "getting started", "where do i start",
            "what is tessellate", "what is memorymap", "what does this app do", "tour of the app",
            "parts of the app",
        ),
        "body": (
            "Tessellate has seven tabs along the top. Dashboard: your day at a "
            "glance and quick actions. Notes: capture and your notes list. "
            "Chat: ask and let the agent act on your notes. Graph: how notes "
            "connect. Library: documents, whiteboards, mind maps, files and "
            "everything else in one place. Timeline: everything by date. "
            "Reminders: what is due. Settings (the gear, or Ctrl+,) holds the "
            "rest, and Atlas the guide (this chat) answers how-to questions "
            "from any tab. Press t then a letter to jump between tabs (o opens the OCR workspace), and "
            "Settings, Help starts the guided tour."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "phone-nav",
        "keywords": (
            "phone", "on my phone", "mobile", "bottom bar", "tab bar", "bottom tabs",
            "more button", "where is the graph on my phone", "where is the timeline",
            "phone menu", "app menu",
        ),
        "body": (
            "On a phone the tabs are a bar along the bottom: Dashboard, Notes, "
            "Chat, Library and More, last. More opens a sheet: Graph, Timeline "
            "and Reminders first, then Ask the agent, Commands, Guide, Agent "
            "activity while the agent runs, and Settings. More is lit while one "
            "of its pages is showing, and carries the count of reminders due. "
            "Press the tab you are on again to go back to the top of its page. "
            "The bar shrinks to icons while you scroll down and gets its words "
            "back on the way up. The app menu (the three dots at the top right) "
            "holds Forward, Recent places, Redo, Find, light or dark, the "
            "Settings window, Lock, and Quit; Back and Undo sit in the top bar."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "settings-overview",
        "keywords": (
            "settings", "where are the settings", "open settings", "find a setting",
            "search settings", "preferences", "cant remember what its called",
            "find by meaning",
        ),
        "body": (
            "Settings opens from the gear in the top bar or Ctrl+,. Its sections "
            "are grouped: AI (Models, Search and index, Personas, Skills, Tools "
            "it can use, What it remembers, What it learned, Web search), "
            "Notebook (Profile, General, Templates, Import & export), Look and "
            "feel (Appearance, Keyboard shortcuts), Privacy and security "
            "(Account & security, Privacy), System (Packages, Background tasks, "
            "Logs) and Help and About. The search box at the top of the list "
            "finds a setting by any word in it or by what it does, with words "
            "that mean the same (\"night\" or \"darker\" finds the theme, "
            "\"battery\" the battery-efficient mode, \"back up\" Backups, "
            "\"the little guy in the corner\" the companion, and a slip such as "
            "\"chnage pasword\" the password), and "
            "lists the matching settings under it, each opening where it sits; with "
            "an embedding model on (Settings, Search and index), up to three more found by "
            "meaning follow under Close in meaning. A long section lists its "
            "groups under its own name in that list: press one to go to it, and "
            "the one you are reading is marked as you scroll. On a phone the "
            "section picker holds the same groups under the section you are in. "
            "A section with several folded groups has Expand all at the top of "
            "its page (Collapse all once every group is open)."
        ),
        "badge": {"label": "General", "section": "general"},
    },
    {
        "id": "lock",
        "keywords": (
            "auto-lock", "auto lock", "change my password", "reset password",
            "other devices", "on my phone", "another computer", "sessions",
            "lock everywhere", "re-encrypt", "new key", "rotate key",
            "recovery key", "make a recovery key",
        ),
        "body": (
            "Settings, Account & security. Signing in: ask for a password when "
            "the app opens (private notes and other devices always ask). Other "
            "devices: let a phone or computer on your network open the app, "
            "always with your password, over https on port 8443, and only on "
            "networks you trusted (the wifi icon in the status bar, Alt+L). "
            "Ask before a new device signs in holds one until you Allow; "
            "Allowed devices have Remove. Loosening "
            "needs your password. The first "
            "visit warns that the certificate is not trusted: compare its "
            "SHA-256 fingerprint with the one under the switch before you "
            "continue, and Regenerate certificate makes a new one. Trust this certificate on your phone downloads it, and its ? says how to install it on iPhone and Android. If this computer's address changes, the app makes a new certificate straight away. Change your password (private "
            "notes move across; a new one needs at least 8 characters, and an "
            "easy one gets a warning). Re-encrypt private notes (Settings, Account & security) makes "
            "a new encryption key and moves every private note onto it, so an old "
            "backup stops opening them; every other session is signed out. Sessions: Auto-lock when idle, from 5 minutes "
            "to 12 hours, and Lock everywhere now; the lock in the top bar "
            "locks at once. Recovery key: Make a recovery key (or Replace it) "
            "asks your password and shows a key once, to copy or download and "
            "keep away from this computer; the old one stops working. Forgot "
            "your password? on the lock screen, on this computer only, has two "
            "paths: the recovery key and a new password keeps private notes "
            "and hands you a new key; I don't have it asks for a six-digit code Tessellate prints in its terminal or log (ten minutes, one use) and then resets the password like "
            "python -m tessellate --reset-password, which keeps ordinary notes, "
            "documents, boards and settings, leaves private notes sealed for "
            "good, and turns other devices off."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "model-bench",
        "keywords": (
            "model bench", "test my models", "which model is best", "compare models",
            "best model for my notes", "benchmark", "try my models",
        ),
        "body": (
            "Settings, Models, Test my models runs your installed models on your "
            "own notes and recommends one. Tick the models to compare and press "
            "Run the test: each model files a sample of the notes you filed "
            "yourself, answers a question about each one from three notes shown "
            "to it, and calls a search tool five times. Every row shows Filing, "
            "Answers and Tools as a percentage, how long an answer took and how "
            "many tokens it used, with the first few things it got wrong, so you "
            "can check the recommendation. Use this one makes that model answer "
            "in chat. Stop ends a run, and a stopped run makes no "
            "recommendation. It needs at least six filed notes, runs entirely on "
            "this computer, and can be switched off in Settings, What it "
            "learned, What may run, Model bench."
        ),
        "badge": {"label": "Test my models", "section": "models", "target": "bench-box"},
    },
    {
        "id": "margin-reader",
        "keywords": (
            "margin reader", "margin", "notes beside my writing", "related notes while writing",
            "did I write this before", "contradiction while writing", "second reader",
        ),
        "body": (
            "The margin reader reads with you while you write a document. Turn "
            "it on from the document's menu, While you write, Margin reader. A "
            "column to the right of the editor then shows at most three cards "
            "about the paragraph the caret is in, a moment after you stop "
            "typing: Repeats (you already wrote this in another note), Differs "
            "(the same thing with a different number or a not, or what the "
            "model judges a disagreement), Answers (it answers an open question "
            "from your notes), Date (a time in the paragraph, with Make a "
            "reminder) and Related. Each card has Open and Not this; nothing is "
            "ever written into your text. It is off until you turn it on, "
            "remembered on this device, and can be switched off everywhere in "
            "Settings, What it learned, What may run, Margin reader."
        ),
        "badge": {"label": "What it learned", "section": "learned"},
    },
    {
        "id": "web-clipper-bookmark",
        "keywords": (
            "bookmarklet", "clip to tessellate", "clip to memorymap", "clip a page from my browser", "browser extension",
            "save this page", "clipper bookmark", "keep a web page", "clip a web page",
            "from my browser", "clip from the browser",
        ),
        "body": (
            "Settings, Import & export, Web clipper has a bookmark called Clip to "
            "Tessellate (typing clipper in the command palette opens it). Drag it to your browser's bookmarks bar (or press Copy the "
            "bookmark and make a bookmark with it as the address). On any page, "
            "press it: a small Tessellate window opens beside the page with its "
            "title and address, and Save as a note keeps the page's main text, or "
            "only the text you had selected. Your own browser sends the page, so "
            "nothing is fetched from the web: it works with web search off and on "
            "pages you signed in to see. No browser extension is needed. A clipped "
            "note keeps its address, Atlas treats its text as someone else's words "
            "and never follows instructions in it, and clipping the same page again "
            "points you to the note it made the first time."
        ),
        "badge": {"label": "Web clipper", "section": "data", "target": "web-clip-box"},
    },
    {
        "id": "import-apps",
        "keywords": (
            "import from notion", "notion", "evernote", "enex", "apple notes", "obsidian vault",
            "import from another app", "move my notes from", "switch from notion", "switch from evernote",
            "import report", "what was skipped", "memorymap folder", "stop the import",
        ),
        "body": (
            "Settings, Import & export, Import from another app has five buttons: "
            "From Notion (choose the zip from Notion's Export, Markdown & CSV), "
            "From Obsidian (choose the vault folder), From Evernote (choose the "
            ".enex files you exported), From Apple Notes (choose the folder an "
            "exporter app wrote, one HTML, Markdown or text file per note) and "
            "From a Tessellate folder (the zip Export notebook folder writes, every "
            "field back as it was). "
            "Choosing starts the import and the toast's Undo moves exactly those "
            "notes to the recycle bin. Folders and notebooks become categories, "
            "tags and dates come along where the app wrote them, and links between "
            "Notion pages become wiki links. Each note remembers where it came from, "
            "so importing the same export again adds nothing twice; the toast counts imported, skipped and failed. Imported text is treated as someone else's "
            "words: Atlas never follows instructions written in it. A note's day "
            "comes from the export where it says one with its year: a daily "
            "note named 2024-03-14, a date: or Created: line; that is its day "
            "on the Timeline, and \"tomorrow\" in it means the day after it was "
            "written. The import's summary names the people and places it read. "
            "Every import keeps a report of what it read, wrote, skipped and found "
            "already here, each skipped file named with why: See the report when it "
            "ends, or Report in the Activity panel. "
            "A long import shows in the Activity panel with Stop; the notes made "
            "before Stop stay."
        ),
        "badge": {"label": "Import from another app", "section": "data", "target": "import-app-box"},
    },
    {
        "id": "simple-mode",
        "keywords": (
            "simple mode", "fewer tabs", "hide tabs", "hide the tabs", "tabs i do not need", "too many tabs", "simpler", "beginner",
            "where did the graph go", "where did the timeline go", "where are reminders",
        ),
        "body": (
            "Settings, General, Simple mode: Show only Dashboard, Notes, Chat and "
            "Library. It hides the Graph, Timeline and Reminders tabs, the "
            "Library's Boards & maps, What it learned and the advanced response "
            "settings until you want them. Nothing is turned off: every hidden "
            "place still opens from the command palette (Ctrl+K), and reminders "
            "still ring. It is remembered on this device; turn it off in the "
            "same place to bring the tabs back."
        ),
        "badge": {"label": "Simple mode", "section": "general", "target": "simple-mode-box"},
    },
    {
        "id": "usage-ledger",
        "keywords": (
            "what you use", "what i use", "usage", "most used", "never use", "unused features",
            "is it tracking me", "telemetry", "analytics",
        ),
        "body": (
            "Settings, General, What you use counts each tab you open and each "
            "command you run from the palette, on this computer only, in a small "
            "file in your data folder: names and dates, never what you typed, "
            "and never sent anywhere (there is no telemetry). It lists your most "
            "used tabs and commands and the ones not used in 90 days, and the "
            "command palette lists the commands you use most first. Clear the "
            "counts forgets every one."
        ),
        "badge": {"label": "What you use", "section": "general", "target": "usage-box"},
    },
    #: Brief 89: the Statistics page and the palette's small tools, each
    #: written from the controls' own words (statistics.js, utility-tools.js).
    {
        "id": "statistics",
        "keywords": (
            "statistics", "stats", "notes per month", "word count of my notebook", "notebook statistics",
            "this week", "weekly review", "week in review", "growth per month", "usage statistics",
        ),
        "body": (
            "Statistics counts your notebook with no model: notes, words, tags, "
            "categories, documents, links and notes with no link, a chart of notes "
            "made per month over the last year, reminders made, done, open and late, "
            "and what you use on this computer (features used, uses counted, and "
            "the ones not used lately). The charts answer you: hover or focus a point "
            "or bar for its period and exact value, move between them with the arrow "
            "keys, and click or press Enter to open it (a month opens the Timeline "
            "there, a feature bar opens that feature). The counts open what they count, "
            "the Range menu sets how far back the growth chart goes (3 months, a "
            "year, or since the first note), and each week row has a small line of "
            "this week's days against last week's. The Ask about your statistics box at "
            "the top answers from the same counts with no model: try Summarise my "
            "month, What do I use most? or Am I writing more than last month?, or ask "
            "how many notes you wrote in July, or when you wrote your first or newest note. Clear (shown once there is an answer) empties the box. This week compares notes made, words "
            "written and reminders done since Monday with the whole of last week. "
            "Open it from the Statistics button under the Dashboard's Activity "
            "heatmap (or a click on the heatmap), the This week card's All "
            "statistics, or Statistics in the command palette (Ctrl+K). Ask "
            "\"notebook stats\" or type /stats in Chat, Ask or the popup agent and "
            "the answer carries the figures as cards with small charts, and Open "
            "Statistics in their head. Private and binned notes are not counted."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        "id": "calculator",
        "keywords": (
            "calculator", "open the calculator", "keypad", "unit converter",
            "convert units", "currency converter", "work out a sum",
        ),
        "body": (
            "The calculator works out sums, percentages and conversions with no "
            "model, the same way /calc does. Open it from the command palette "
            "(Ctrl+K, Calculator, or Convert units for the conversion tab; both "
            "are also in the / menu), by typing /calc with nothing after it, or "
            "with Open the calculator under an answer that worked something "
            "out. Work out takes a sum typed or keyed (12 * (3 + 4), 15% of 80, "
            "5 km to miles), shows the result as you type and says how it read "
            "it; Enter or = keeps it in the list of earlier results, and Copy "
            "result copies it. The keypad is one Tab stop: the arrow keys move "
            "around it. Convert units picks a kind (length, weight, currency "
            "and more), an amount and two units, with a swap button; currency "
            "rates are set by hand and dated, not today's rate."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        #: INBOX 1481: a chat that is not kept (chat-private.js, `ChatRequest.private`).
        "id": "chat-private",
        "keywords": (
            "private chat", "incognito", "temporary chat", "not saved", "off the record",
            "chat without history", "no memory", "private session", "discard a chat",
        ),
        "body": (
            "A private chat is a chat that is not kept. Start one from the gear "
            "under the message box (Private chat), from the chat's ⋯ menu "
            "(Private chat), or from the command palette (Ctrl+K, Private chat). "
            "A Private mark in the chat's head says it is on, and the empty chat "
            "says: Private chat. Nothing here is saved or remembered. While it "
            "is on, the chat is not saved in the chat list and does not come "
            "back after a reload, the question is not offered again under Ask "
            "again, the notes it read are not counted as used, and the AI "
            "neither reads what it was taught (Settings, What it remembers, and "
            "what you said of insights and sentences) nor can save anything "
            "new about you. It still answers from your notes, and Agent mode "
            "still works on them. New chat, opening another chat, Delete this "
            "chat or closing the page asks once to discard a private chat that "
            "has messages; the same switch ends an empty one. Save this chat as "
            "a document, in the chat's ⋯ menu, keeps a copy if you want one."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "timer",
        "keywords": (
            "timer", "countdown", "stopwatch", "pomodoro", "set a timer", "start a timer",
            "stop the timer", "time how long",
        ),
        "body": (
            "Type timer in the command palette (Ctrl+K; its ? at the foot lists "
            "the timer, the stopwatch and Count words) for Start a timer (25 "
            "minutes) and Start a stopwatch, or type a length, such as timer 10 "
            "minutes, 90s timer or countdown 2h, and press Enter. The time runs "
            "on the status bar (on a phone the bar comes back while it runs); "
            "press that timer chip in the status bar to stop the one it shows. Several "
            "timers can run at once (the chip shows the one ending first), and they "
            "come back after a reload. When a timer "
            "runs out it says so in a message and a notification. The "
            "Dashboard's Focus timer widget is a separate timer: a ring with "
            "the time, lengths of 5, 15, 25 or 50 minutes (or minus and plus "
            "for any other), one Start that becomes Pause, a chime and a "
            "notification at the end, Breaks for a five-minute break after "
            "each session, and the minutes focused today."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        #: WORLD_CLASS_PLAN 25c: the dashboard's first steps (first-run.js).
        "id": "first-steps",
        "keywords": (
            "first steps", "start in three steps", "sample notebook", "sample notes", "example notes",
            "remove the sample notes", "demo notes", "try it out", "hide these steps", "get started", "setup popup", "closed the welcome", "checklist",
            "hide get started", "mark all as done", "show get started", "fold the first steps",
        ),
        "body": (
            "A new notebook's Dashboard shows Get started, a checklist of three steps: 1. Your name, "
            "2. Write a note, 3. Ask your notebook, with a bar showing how many are done. Each is ticked "
            "when it is done, and none of them needs an AI model: Ask answers from your notes' own "
            "words, and saving your first note offers Ask about it beside "
            "Saved. The caret folds the steps to one line. The card's ... menu holds Try a sample notebook, which adds eight example notes, tagged "
            "sample-notebook, to explore (ask \"where is the spare key?\", see two "
            "linked notes in the Graph); it is offered until you write your own "
            "first note. Remove the sample notes moves them all to the bin, where "
            "Restore brings one back, and takes away the categories they made. The steps leave once all three are done and "
            "the sample notes are gone. Mark all as done ticks every step and puts the card away; Hide Get started "
            "hides the card and the dock's Get started button. Settings, Help (Show Get started), Customise, the hide notice's Show again or the palette (Ctrl+K, Show Get started) brings them back. "
            "Until then the dashboard's Get started menu (beside Customise) lists the same three, ticked as "
            "they are done, with Take the tour and Replay the welcome, and the same checklist "
            "is the first row of the notifications bell until all three are done."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        #: WORLD_CLASS_PLAN 25c: the Guide's topics as one page (manual.js).
        "id": "manual",
        "keywords": (
            "manual", "user manual", "user guide", "documentation", "docs", "handbook",
            "print the help", "read all the help", "every help topic", "help page",
        ),
        "body": (
            "The manual is every topic Atlas answers from, on one page: Ctrl+K or "
            "Find anything, Open the manual; Settings, Help, Open the manual; or "
            "Open the manual in the Guide's More actions menu. It can also sit on "
            "the dashboard as a quick link (Quick access, Customise). "
            "The contents on the left jump to a group, the search box keeps only "
            "the topics that hold every word you type or what the words mean "
            "(\"trash\" keeps the bin's topic), those whose name holds them "
            "first, and the printer button "
            "prints what is shown (or saves it as a PDF). It is made from the "
            "Guide's own topics, so the two never disagree. What changed in each "
            "version is under Settings, About, What's new."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "live-captions",
        "keywords": (
            "live captions", "captions", "subtitles", "live transcription", "transcribe live",
            "write what i say", "speech to text live", "stop the captions",
            "how do i get live captions", "where are live captions", "open live captions",
        ),
        "body": (
            "Press Captions in Library, Recordings, or Live captions in a Voice "
            "note before you record; it is also in Tools and features, Audio, "
            "and in the command palette (Ctrl+K, type captions); Edit quick access "
            "can add it to the Dashboard as a tile. A bar appears "
            "over whatever you are looking at and writes what the microphone "
            "hears, on this computer, never over the internet. The bottom line "
            "is still being written; the three above it are done. Copy takes "
            "everything said so far, and Stop (or the palette row again) saves "
            "it as a note tagged captions. Translate, once the offline translator is "
            "installed (Settings, Packages), writes each finished line in Spanish "
            "under the captions; the note keeps what was said. Keep the audio of live "
            "captions (off until you turn it on, in Settings, General, Microphone) makes Stop "
            "save the audio too, in Library, Recordings, with the lines as its transcript. "
            "While a voice note records, the same "
            "captions write its words into the dialog as you speak, and the "
            "full transcript replaces them after. Captions need a local speech "
            "helper; its row in Settings, Packages says what is missing, and "
            "without one the row says so and nothing is recorded."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "count-words",
        "keywords": (
            "word count", "count words", "character count", "how many words", "reading time",
            "count the selection", "how long is this",
        ),
        "body": (
            "Select text in any editor (a note, the Capture box, a document) and "
            "run Count words from the command palette (Ctrl+K): it says the "
            "words, the characters with and without spaces, and the reading "
            "time, counted the way wc counts. With nothing selected it counts "
            "the whole editor you were in. The Capture box and a document also "
            "show a running count as you type."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "translate-offline",
        "keywords": (
            "translate this", "translate offline", "offline translation", "translate without a model",
            "translate to spanish", "bergamot", "ai free translation",
        ),
        "body": (
            "Select a passage in a note, a document or a reading and run "
            "Translate this from the command palette (Ctrl+K): it turns "
            "English into Spanish on this computer, with no model, in about a "
            "second, and Copy or Replace the selection puts it to use. With "
            "nothing selected it takes the whole editor you were in. It needs "
            "Translate offline, a 27 MB download in Settings, Packages "
            "(Languages); until then the row says so and opens that page. "
            "Other languages: the Writing room translates with your model."
        ),
        "badge": {"label": "Packages", "section": "extras"},
    },
    {
        "id": "insert-template",
        "keywords": (
            "insert template", "insert a template", "text snippet", "reusable text", "boilerplate",
            "template into a note", "paste a template",
        ),
        "body": (
            "Type insert template (or template and part of its name) in the "
            "command palette (Ctrl+K) to list your templates; Enter puts the one "
            "you choose where your cursor was, in any editor, with {date}, "
            "{{time}} and {{clipboard}} filled in. With no editor open it goes "
            "into the Capture box. The templates, yours and the built-in ones, "
            "are in Settings, Templates, where you write, edit and reset them."
        ),
        "badge": {"label": "Templates", "section": "templates"},
    },
    {
        "id": "capture-anywhere",
        "keywords": (
            "capture from anywhere", "global hotkey", "global shortcut", "system shortcut",
            "capture without opening", "note from another app", "--capture",
        ),
        "body": (
            "Settings, Keyboard shortcuts, Capture from anywhere shows the command "
            "for this install (tessellate --capture, with its full path) and a "
            "Copy button. Give that command a key in your system's own keyboard "
            "settings: on Windows a desktop shortcut with it as the target and a "
            "Shortcut key, on macOS a Shortcuts action, on Linux a custom keyboard "
            "shortcut. Pressing the key over any app opens a one-line box on the "
            "Tessellate that is already running; Enter saves the note, filed like "
            "any other, and the box closes. On a phone, Share to Tessellate does "
            "the same."
        ),
        "badge": {"label": "Capture from anywhere", "section": "shortcuts", "target": "capture-anywhere-box"},
    },
    {
        "id": "install-app",
        "keywords": (
            "install", "install the app", "install as an app", "add to home screen",
            "home screen", "pwa", "own window", "app icon", "share sheet",
            "share to tessellate", "share to memorymap", "not running on this computer", "offline page",
        ),
        "body": (
            "Settings, About, Install as an app gives Tessellate its own window "
            "and icon, and adds it to your phone's share sheet, so a page or a "
            "selection shared to it lands in Capture. The button appears only "
            "when your browser offers the install and the app is not installed "
            "yet; on an iPhone, tap Share, then Add to Home Screen. It is the "
            "same app, still served by the copy running on this computer. When "
            "that copy is not running, the installed app shows a page saying "
            "Tessellate is not running on this computer, with a Retry button, "
            "never an empty notebook: open Tessellate from the Start menu or "
            "the launcher, then press Retry."
        ),
        "badge": {"label": "Install as an app", "section": "about", "target": "about-install"},
    },
    {
        "id": "desktop-companion",
        "keywords": (
            "desktop companion", "companion on the desktop", "companion outside the app",
            "companion in the corner of the screen", "desktop pet", "quick note from the desktop",
            "companion when the window is closed", "show desktop companion",
        ),
        "body": (
            "In the desktop app on Windows the companion can sit in the bottom-right "
            "corner of your screen, above the taskbar, while the Tessellate window is "
            "in the tray, and go away when the window is open. It is off until you turn "
            "it on: Settings, About, Show the companion on the desktop while the window "
            "is in the tray, or Show desktop companion in the tray icon's menu. It is "
            "whoever you chose in Appearance (Atlas if you chose nobody). Click it for "
            "Quick note, Quick search or Open Tessellate; a note saved there is filed "
            "like any other, and a search result opens in the app. Right-click it for "
            "Settings or Hide (Hide turns the setting off). Drag it to move it; it "
            "remembers where you left it. While Tessellate is locked it shows only the "
            "companion and Open Tessellate, never a note or a result."
        ),
        "badge": {"label": "Desktop companion", "section": "about", "target": "desktop-companion-row"},
    },
]

#: **Every feature since 0.3.0, large and small** (INBOX 448 (1), the owner:
#: "the help settings as well as the help info available to the agents needs
#: more expansion for all the new features both large and small so people can
#: easily find out about all the features"). The inventory is
#: `tests/test_help_coverage.py`'s `FEATURES`, read from CHANGELOG's
#: Unreleased and 0.3.x sections: before these entries 8 of its 52 rows had an
#: entry that said so, and 4 reached it from the question a person would ask.
#: Each entry was written from the controls' own labels (index.html and the
#: module that draws them) and is keyed by the words a person searches with,
#: not the feature's name ("what does the percentage mean", "where are my
#: bookmarks").
MORE_TOPICS.extend(
    [
        {
            "id": "quick-add",
            "keywords": (
                "chips under the box", "read as", "quick add", "date chip", "what it read",
                "remind me friday", "natural language date", "type a date", "wrong date",
                "time chip", "repeat chip", "tag chip",
            ),
            "body": (
                "Quick add: where you type something dated or tagged (the Reminders "
                "box, Quick note, a new meeting's title, the Timeline's search and the "
                "command palette), what the words were read as shows as chips under "
                "the box as you type: a day, a time, a repeat, a person, a #tag, a "
                "window like \"last week\". Enter saves what the chips say. Press a "
                "chip to leave those words as words. When something needed is "
                "missing (a reminder with no time), it asks once and saves nothing "
                "until you add it, rather than guessing. In Quick note a day is an "
                "offer of a reminder on the note, used when pressed or when the note "
                "starts \"remind me\". On the Timeline, Enter turns a window into the "
                "From and To range and keeps the other words as the search. It all "
                "works with no AI model."
            ),
            "badge": {"label": "Reminders", "tab": "reminders"},
        },
        {
            "id": "editor-offers",
            "keywords": (
                "offers under the note", "offers while i write", "remind me from a note", "date in a note to calendar",
                "sum checked", "check my sums", "wrong sum", "wrong total", "check the total", "link suggestion", "suggest a link",
                "filing suggestion", "why this category", "chips under the note",
            ),
            "body": (
                "While you write a note (Capture, or a note's Edit form), offers show as "
                "chips under the box when you pause: a day in the text becomes Remind me "
                "(press it to set the reminder, with Undo; it goes on the Timeline and its "
                "calendar, and the notice's Show on calendar opens that day), a sum written with a wrong "
                "answer shows the right one (press it to put it in), and so does a Total: "
                "line under a column of amounts that does not add up; a name another note "
                "opens with becomes a [[link]], and File in names the category with its "
                "reason beside it. Nothing is offered on quoted words: text in quotation "
                "marks, a code span or block, or a quote line. At most five show at once. It all "
                "works with no AI model."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "quick-note",
            "keywords": (
                "quick note", "alt+n", "jot down", "note from anywhere",
                "without leaving the page", "quick capture", "web clipper",
                "save a web page", "web page as a note", "clip a page", "paste a link",
                "clear the box", "clear what i typed", "clear button", "eraser", "undo clear", "start over on a note",
            ),
            "body": (
                "Quick note (Alt+N, or Quick note in the command palette) opens a "
                "small box over whatever tab you are on: type, press Ctrl+Enter, "
                "and the note is saved and filed in the background while you stay "
                "where you were. Escape closes it and keeps the words for next "
                "time; Open in Capture moves them to the full composer. The "
                "dashboard's Quick capture saves the same way. A bare link pasted "
                "into Capture or Quick note offers its page as a note through the "
                "web clipper, only while web search is allowed. \"Clear\" (the eraser "
                "icon) is in every box you type into: Capture, with its title, tags "
                "and files, Quick note, Ask, Chat and the popup agent. It shows only "
                "while the box holds something, empties it, and Undo (in the toast, "
                "or beside the box in a popup) puts it all back."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "note-outbox",
            "keywords": (
                "server is down", "server down", "server away", "failed to fetch",
                "waiting to save", "not saved", "lost my note", "kept on this device", "lost my edit", "unsaved changes",
                "save while offline", "saved offline", "connection lost", "try now",
            ),
            "body": (
                "A note saved while the Tessellate server is not answering (from "
                "Capture, Save as draft, Quick note or the dashboard's Quick "
                "capture) is kept on this device rather than lost, and is sent by "
                "itself when the server is back. It sits at the top of the notes "
                "list as a card marked Waiting to save, and a notice above Capture "
                "counts what is waiting, with Try now to send it at once. A note "
                "sent twice is still saved once. An edit left unsaved in a note's "
                "form is kept on this device too: after a reload or a closed "
                "window, a message offers Open them to carry on. A document's "
                "last words before a reload are kept the same way, and Put them "
                "back returns them when that document opens."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "attachments",
            "keywords": (
                "paste a picture", "paste an image", "paste image", "paste a screenshot",
                "drag and drop", "drop a file", "attach a file", "attached file",
                "attachment card", "file card", "rename a file", "annotate", "describe with ai",
            ),
            "body": (
                "Paste a picture into Capture or a note being edited, or drop a "
                "file on it, and it is kept with the note. An attached file is one "
                "card everywhere (the note, Capture, a document, the graph and the "
                "Timeline): the picture or a kind icon, its name, kind, size and "
                "date. Click the card to open it; its ... menu has Open, Download, "
                "Rename, Describe with AI, Edit description, Annotate a copy, Copy "
                "as a link and Remove. Removing a file can be undone, and the "
                "upload is only deleted once nothing else uses it."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "chat-model-picker",
            "keywords": (
                "model picker", "choose a model", "pick a model", "pin a model", "pinned model", "recent models",
                "search models", "model for the chat tab", "switch the model", "which model",
            ),
            "body": (
                "The model picker beside the Chat, Ask and Writing boxes opens with a "
                "search, then Pinned and Recent models, then one row per source "
                "with its count (On this computer, 4 models): press a row to fold "
                "or open it. Every model has a pin that lifts it to the top. The "
                "arrows move, Enter chooses (in the search, the first match) and "
                "Escape closes it. It is the same choice as Settings, Models."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "chat-attach-cards",
            "keywords": (
                "attached note", "attached a note", "attach a note to chat", "note card in chat",
                "notebook card", "attachment card in chat", "preview an attachment", "chat attachment",
            ),
            "body": (
                "What you attach to a chat message from the notebook (a note, a "
                "document, a mind map or a library file) is one card: a glyph for "
                "what it is, its name in words, and one line under it (a note's "
                "age, or its next words once sent). In the box it is a small pill, the glyph, the name, "
                "its kind in brackets and an x to take it off (hover it for the full "
                "name); a passage you asked about and a web page you cited are the same "
                "pill. Once sent, the cards sit above your message, on its side, "
                "and a reopened chat draws the same. Press a card, or Tab to it and "
                "press Enter, for a preview with an Open button (Open note, Open "
                "document, Open mind map, Open file); Escape closes the preview and "
                "returns to the card."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "filing",
            "keywords": (
                "percentage", "percent", "how sure", "confidence", "filed", "filed without ai",
                "stuck on filing", "still filing", "file by meaning", "file it myself",
                "wrong category", "uncategorised", "uncategorized", "choose category",
                "filing style", "review queue", "is:review", "accept the filing",
                "what is filing", "how does filing work", "how filing works",
                "why was it filed", "why this category", "new category", "sensitive notes",
                "file health notes", "health notes", "money notes",
            ),
            "body": (
                "Each new note is filed into a category in the background. Its "
                "card shows how sure the filing was, for example 83% beside the "
                "category, and whether Atlas or your notebook's words filed it; "
                "the note's History names the model. That percentage is Atlas's "
                "own estimate, not the model's raw number: a small model often "
                "says 100% about everything, so nothing it picks reads above "
                "95%, a pick your other notes disagree with is lowered, and so is "
                "a pick for a category with few notes. A filing under 50% shows "
                "check this, and the line under the note box offers the other "
                "categories as one-tap buttons; a note you filed yourself shows "
                "Filed by you and no percentage. With no AI model running, a "
                "note is filed by your other notes and a built-in topic list, "
                "only into a category you have, and says why (It mentions squat "
                "(Fitness), like the 9 notes in Gym). Unsure, it stays in "
                "Uncategorised with one-tap choices, and New: Fitness when none "
                "fits. Health, money and family notes wait for you unless File "
                "health, money and family notes by their words too is on in "
                "Settings, Background tasks. While a "
                "note shows Filing, its chip offers File by meaning now, Leave it "
                "where it is and File it myself, and Stop in Settings, Background "
                "tasks files every waiting note by meaning. A note you file "
                "yourself is never moved by a late answer, and moving notes by "
                "hand teaches the filing where things go. In Settings, Background tasks, Load "
                "the search model when the app starts chooses when filing by "
                "meaning gets ready: at launch, or on the first note, which then "
                "waits a few seconds. Let the search model go after an idle hour "
                "frees its memory when nothing has been searched or filed for an "
                "hour; the next search loads it again. Filing style (Settings, Background tasks) files by topic, "
                "by project or by time. Filings Atlas was unsure of wait in "
                "is:review, with Accept the filing on the note's menu."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "suggested-tags",
            "keywords": (
                "suggested tag", "suggested tags", "plus tag", "plus tags", "+ tag",
                "tag suggestion", "stop suggesting", "don't suggest tags", "dont suggest tags", "add tag chip", "dismiss a tag", "tag with atlas",
                "why is this tag suggested", "why this tag", "turned down", "offer again",
            ),
            "body": (
                "The tags Atlas suggested when it filed a note stay on the note's "
                "card as \"+ tag\": one press adds the tag, and its x (Dismiss) stops "
                "suggesting it (Undo in the notice brings it back, and the note's "
                "Edit form lists the ones turned down under Not suggested, each "
                "one press from coming back). With no AI running they come from your own tags: "
                "the ones the note names (\"stats\" finds statistics), its title and first line "
                "first, then those on the notes most like it and the notes it links to; with room left, "
                "a subject the note names in two different words and you have not tagged yet (gym and squats "
                "make #fitness). Words in "
                "quotation marks and a scan's footer do not count. Either way a tag is offered "
                "only when the note has a word for it, at most three, and "
                "pointing at one says which word. A tag turned down on three notes is offered "
                "less everywhere; Manage tags lists it under Turned down, with Offer again. "
                "Tag and file with Atlas and Capture, while you type, suggest the same way. "
                "A note with fewer than three tags shows a quiet \"+ Tag\" after them: it opens up to "
                "three suggested tags as one-press chips above a field for your own. Its ... menu "
                "has \"Don't suggest tags for this note\", which stops the suggestions on that "
                "note alone (Undo in the notice brings them back, as does \"Suggest tags for this "
                "note again\" in the same menu)."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "tag-manager",
            "keywords": (
                "manage tags", "tag manager", "rename a tag", "rename tag", "merge tags",
                "merge a tag", "remove a tag", "delete a tag", "every tag", "tag counts",
                "tags row", "tag chip", "right click a tag", "right-click a tag",
                "tags everywhere", "duplicate tags", "similar tags", "sort tags",
                "unused tags", "used once",
            ),
            "body": (
                "The tag manager lists every tag with how many notes use it. Open "
                "it from the Notes ... menu (Manage tags), the Tags row in the "
                "notes sidebar, Settings or the command palette. Rename a tag, "
                "merge it into another, or remove it from all notes, one or "
                "several at a time; each change shows in the notes' history and "
                "has one Undo. Sort it by name, by notes or by the tag used most "
                "recently; Used once lists the tags only one note carries; tags "
                "that look like one (idea and ideas, to-do and todo) are offered "
                "as one Merge above the list, and the count after a tag shows its "
                "notes. Right-click a tag chip (or press the menu key on it) for "
                "Show notes, Rename in all notes, Remove from this note "
                "and Manage tags. The selection bar's Tags adds or removes tags on "
                "every selected note at once."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "tidy",
            "keywords": (
                "tidy", "tidy up", "clean up", "cleanup", "clean up notes", "broom",
                "weak links", "link reasons", "similar in meaning", "specific reason",
                "why are these linked", "auto tags", "tags atlas added", "low confidence",
                "tags used once", "look alike tags", "near duplicate", "duplicate notes",
                "find duplicates", "uncategorised", "short notes", "empty notes",
                "old reminders", "stale reminders", "without the ai", "without ai",
                "bulk", "housekeeping", "apply automatically",
                "categories that overlap", "category names", "similar categories",
                "patterns", "confirm a pattern", "not right", "wrong pattern", "insight",
                "dismiss a suggestion", "delete a suggestion", "hide a suggestion",
            ),
            "body": (
                (
                    "Tidy is the broom in the Notes dock, beside the search help; the number on it is how "
                    "many things its reviews found. It opens on an overview of all eleven reviews, each a "
                    "rule that needs no AI, with its count and one line on what it finds, the ones with "
                    "nothing to tidy last; press a row to open that review and its back button to return to "
                    "the overview. The reviews: Links to explain (Add reasons gives a link that only says "
                    "similar in meaning what the two notes share, a tag, a name or a week), Weak automatic "
                    "links (Remove links), Tags Atlas added (tags written by Atlas or a background pass, "
                    "never changed by you, that fit their note poorly; Remove tags), Tags used once (Remove "
                    "tags), Tags that look alike (Merge tags), Notes without a category (Move notes, to the "
                    "category their words point to), Near-duplicate notes (Merge notes), Categories that "
                    "overlap (Merge categories), Category names (Rename), Empty or very short notes (Move to "
                    "bin) and Reminders long past (Mark done). Each review's description says what its button"
                    " will change. A row's cross dismisses it for good (Undo restores it). Tick the rows "
                    "(each says why it is listed and what the button will do), then press the button; one "
                    "Undo puts the batch back, from the toast, Ctrl+Z or Recent runs. Apply automatically "
                    "runs a review after each note is filed; merging, renaming, binning and removing tags "
                    "used once never run on their own. Links to explain also has Add reasons to all in the "
                    "background, a job you can stop in Settings, Background tasks. The command palette and "
                    "Tools and features open Tidy too, and new links already say what their notes share when "
                    "they can. Under the overview, Patterns says what the notes measure (golf 4 times since 5"
                    " September), each with Confirm, which keeps it as your own word from then on, and Not "
                    "right, which never shows it or anything like it again;"
                )
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "manage-categories",
            "keywords": (
                "manage categories", "merge categories", "merge two categories",
                "split a category", "delete a category", "category colour",
                "category color", "colour of a category", "color of a category",
                "rename a category", "notes in a category", "view category",
                "category chip", "duplicate categories", "similar categories",
                "empty categories", "sort categories", "colour several categories",
            ),
            "body": (
                "Manage categories (the Categories head in the notes sidebar, a "
                "category's ... menu, Settings or the command palette) makes one "
                "(New category), renames, merges (a category's menu, Merge into), "
                "splits and deletes categories, asking where the notes "
                "go; every change can be undone, and deleting one can always keep "
                "its notes in Uncategorised. A split can be suggested from the "
                "notes' tags or by Atlas, which reads the notes and proposes "
                "named groups to review. Colour gives a category one of twelve "
                "swatches (or Automatic), shown on its dots, chips, graph nodes, "
                "the Timeline and the Dashboard; select several to colour, merge "
                "or delete them together, with one question and one Undo. Sort by "
                "name, notes or the one used most recently, Empty lists the ones "
                "with no notes, Tidy suggestions offer names alike (in spelling or "
                "meaning) as one Merge and categories empty for thirty days to "
                "Remove, Not these never asks about a pair again, and the "
                "count after a name shows its notes. A category chip on a note opens "
                "Show notes in the category, Move to another category and Manage "
                "categories; dragging a note's category label onto another "
                "category moves it too."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "note-history",
            "keywords": (
                "note history", "who changed", "who edited", "changed my note",
                "edited by atlas", "you and atlas", "two windows", "two tabs",
                "edited twice", "conflict", "keep your version",
                "then and now", "what did it say", "time travel", "as of",
            ),
            "body": (
                "A note's History (in its menu) lists every change and whose it "
                "was: You, Atlas, or You and Atlas (a save that took an Improve "
                "writing suggestion), with the exact time on hover, and any "
                "earlier version can be put back; Then and now on an earlier "
                "version sets what it said against what the note says today, "
                "sentence by sentence (Changed, No longer says, Says now). In Ask, "
                "the clock button answers from your notes as they were on a day "
                "you pick, and Back to now returns to today. It also says who "
                "filed the note "
                "and how sure, and a change made by an AI tool names the model "
                "that made it. When the same note or document is edited in two "
                "windows, a save over text changed elsewhere is refused and you "
                "choose: keep your version, take the other one, or compare the "
                "two first."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "notes-list",
            "keywords": (
                "sort notes", "recently edited", "a to z", "copy link", "copy wiki link", "copy app link",
                "connections column", "beside the list", "forgotten", "close to this",
                "backlinks", "unlinked mentions", "mentioned, not linked", "linked mentions",
                "most used", "note order", "f2",
            ),
            "body": (
                "Sort notes: Newest first, Oldest first, Recently edited, A to Z "
                "(\"note 2\" before \"note 10\"), Most used or Forgotten first; "
                "the choice is remembered. A note's menu has Copy wiki link to "
                "paste a [[link]] to it into another note, and Copy app link for "
                "an address that opens it in the app. Editing a note has the title, "
                "a line of properties and the text in one box: the category is its "
                "chip with a menu, tags are chips after it (Add tag: Enter or a "
                "comma adds one, pressing one removes it), and the formatting "
                "icons sit above the text, the rest behind More. Related notes "
                "fold into one \"suggested links\" line until you open it. The foot "
                "has Attach a link (pick a saved bookmark) and the word count at "
                "the left and Cancel and Save at the right. On a focused note, F2 edits it, Delete deletes it, and "
                "Home and End jump to the ends of the list. In a window 1280 wide "
                "or more, the note you are reading (the one you clicked, else the "
                "one in view as you scroll) has a Connections column beside the "
                "list: the notes it links to, the notes that link to it with the "
                "sentence each says it in, \"Mentioned, not linked\" (notes and "
                "documents that name it without a link; Link turns those words "
                "into a [[link]], and is greyed out when the name has a square "
                "bracket in it, which a [[link]] cannot hold), and \"Forgotten, and close to this\". The "
                "note's Connections sheet shows the same, with its rows as a quiet "
                "list (a glyph, the title, a muted line for the kind or day) under a "
                "row of count chips, and on a wide window an Open in the sidebar "
                "button that docks it as this column. Drag its left edge to change the "
                "column's width (arrow keys on the edge do it 16 pixels a press, "
                "and Home puts it back); the width is kept on this device."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "card-content",
            "keywords": (
                "table in a note", "code block in a note", "remote image",
                "picture from the web", "image not loaded", "note card",
                "what a card shows", "create a linked note", "link mode",
            ),
            "body": (
                "What a note's card draws. A table or a code block is drawn the "
                "way a document draws it, with its Copy button; a search does not "
                "mark words inside one. A picture from the web is not loaded, "
                "because this notebook works offline: the card says so and links "
                "to it, to open in a new tab. A [[link]] to a note that does not "
                "exist has a Create chip beside it, which offers to make the note "
                "or a document of that name. Esc leaves link mode (Link to "
                "another) and takes its notice down."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "addresses",
            "keywords": (
                "address", "url", "address bar", "web address", "browser back",
                "back button", "deep link", "link to this view", "own address",
                "copy app link", "app link", "link to a note", "hyperlink", "share a note",
            ),
            "body": (
                "Every view has its own address, such as #/notes/12, #/chat/45, "
                "#/docs/7, #/library/images or #/settings/appearance. A reload "
                "keeps the view, a bookmark or a pasted link opens it, the "
                "browser's Back and Forward walk the app's own history, and the "
                "window title names the view and what is open in it. To link to one "
                "thing, open its menu and choose Copy app link (notes, documents, "
                "boards, mind maps and chats have it): it copies an address that "
                "opens that thing while the app is running. Paste it into a note "
                "or a document and it becomes a link that opens in the same "
                "window. Copy wiki link is the other one: a [[link]] for pointing "
                "at a note or document from inside a note."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "bookmarks",
            "keywords": (
                "bookmark", "bookmarks", "reading list", "saved links", "saved link",
                "read later", "by site", "web links", "my links", "mark read",
                "bookmark link",
            ),
            "body": (
                "Library, Bookmarks is a reading list of web links; Add bookmark "
                "saves one. Unread and Pinned narrow the list (with counts), and "
                "opening a link marks it read. Sort by newest, oldest, title or By "
                "site, which groups links under their site in folds you can close. "
                "Each link shows its kind, Details opens in place with a note "
                "field, and selecting several offers Move to group, Mark read and "
                "Pin; pinned links lead every order but By site, and every delete "
                "has Undo. In a note or document, the / menu's Bookmark link "
                "inserts a saved bookmark as a link."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "contents",
            "keywords": (
                "contents", "table of contents", "outline of my notebook",
                "whole notebook", "notebook outline", "tree of notes", "index of notes",
                "expand all", "collapse all", "group by", "group the index",
            ),
            "body": (
                "Library, Contents is the whole notebook as a tree: pick By "
                "category, By tag, By topic, By month or By folder in its Group by list, "
                "and each group folds at its heading. A document lists its "
                "headings, so a press jumps straight to one. Expand all and "
                "Collapse all, in the ⋯ menu, open or fold every group; folded, "
                "the groups are a list of places to go. From the keyboard the Up and Down "
                "arrows move, Right opens a row, Left folds it, Home and End jump "
                "to the ends, and Enter opens. By month puts each document under "
                "the month it was made, with that month's notes. By topic groups "
                "notes by the subjects the graph finds in how they link; F2 or "
                "right-click on a topic's heading renames it or shows it on the graph."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "answer-pictures",
            "keywords": (
                "pictures in answers", "images in answers", "image in chat",
                "picture in chat", "sketch in chat", "show the picture",
                "thumbnail", "photo in the answer", "picture in note", "[picture 1]",
                "figure in the answer", "show me the sketch",
            ),
            "body": (
                "When an answer in Chat or Ask draws on a note with pictures or "
                "sketches, the note's numbered chip under Grounded in has up to "
                "three small pictures beside it (a +n says there are more). The "
                "chip opens the note; a picture opens in the image viewer, with "
                "its caption and the text read off it. Atlas can also place a "
                "picture inside its answer by writing [picture 2] for note 2 "
                "([picture 2.2] for its second): it appears as a figure under "
                "the paragraph, with its caption and a From note 2 link that "
                "opens the note, and a click opens the image viewer. Atlas "
                "shows one only when seeing it answers or shows the point; ask "
                "for the picture (show me the sketch) and a cited note's "
                "picture appears even without the token. At most three figures "
                "an answer; reopening the chat "
                "draws them again."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            #: INBOX 1300 C30: the viewer's two bars, filmstrip, keys and gestures.
            "id": "image-viewer",
            "keywords": (
                "image viewer", "lightbox", "view a picture", "zoom a picture",
                "rotate a picture", "actual size", "filmstrip", "next picture",
                "pinch to zoom", "swipe pictures", "download a picture",
                "open in a new tab", "picture details",
            ),
            "body": (
                "A picture or file opens in the viewer. The bar at the top names "
                "it and says where you are (2 of 5), with Copy text when it has "
                "a reading, Download, Open in a new tab, Details (the size, the "
                "caption and the text read off it, shown or hidden), the '?' "
                "and the ⋯ (rename, delete, see the text on the page). The bar at "
                "the foot zooms: out, in, back to fit, 1:1 for actual size, and "
                "Rotate; a PDF adds its page stepper. With more than one file a "
                "filmstrip above it jumps to any of them. Scroll zooms where the "
                "pointer is, drag moves a zoomed picture, double-click switches "
                "between fit and actual size. Keys: Left and Right, plus and "
                "minus, 0, 1, R, I, Escape. On a phone, swipe and pinch. The bars "
                "fade while the mouse rests on the picture and come back when it "
                "moves; never for the keyboard or reduced motion."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            #: INBOX 688, 714: the Ask box's AI switch (K34).
            "id": "answers-from-notes",
            "keywords": (
                "from your notes", "answer without ai", "no ai answer", "answer with no model",
                "composed answer", "without the ai", "ai or notes", "notes instead of ai",
                "switch off the ai", "ai off", "who answers", "ask without a model", "use ai",
                "save answer as document", "answer as mind map", "keep the answer",
            ),
            "body": (
                (
                    "Ask on the Notes tab has an AI switch beside its answer-length picker. On, your model writes the "
                    "answer, with From your notes under it; off, the answer is From your notes, with no AI. It opens with the answer, or for"
                    " a topic with how many notes and over which days (You have four notes about uni, 17 July"
                    " to 4 August), then tells each note in a sentence (In your first psych lecture you "
                    "learned ...) or under a bold label, one source mark that lights its note. It says what "
                    "the notes do not cover yet (Nothing yet on due dates), how alone or stale a fact is "
                    "(Nothing on bench since September), and can end with one offer you press (a reminder, a "
                    "checklist or a note, with Undo); next week is said as the day it meant. A count leads "
                    "with its figure, a person is a card, a comparison a table, what is left a checklist; "
                    "past five lines, Show more. The ... by Copy keeps it as a note, a document or a mind "
                    "map. Asked what it can do (can you search the web?), it says whether and how; it never "
                    "searches. Tell me more, or the second one, follows on from the answer before. The Chat "
                    "tab answers the same way whenever no model is running: its box stays open, and Agent "
                    "mode is greyed unless the Needle extra can run it (the app's own tools go first). Every "
                    "sentence is quoted from a note and cited like any answer; the app adds only the joining "
                    "words and the counts and dates it measured, names two notes that may disagree, and says "
                    "which of your words none of the notes found mention. The badge by the name says who "
                    "wrote it (From your notes, a model's name, or Composer); hover or click it for what "
                    "that means. The No model connected line above the Chat box "
                    "and the Ask box has a close button: it hides that line until "
                    "the next time you start the app, a new session, and connecting a model in Settings, "
                    "Models always brings the answers back. Hide it for good under Model backend."
                )
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "follow-up-trail",
            "keywords": (
                "follow-up", "follow up", "followup", "suggested question",
                "ask next", "next question", "breadcrumb", "bread crumb",
                "trail", "where did this question come from", "question chain",
                "tell me more", "what about", "the second one", "two meanings",
            ),
            "body": (
                "Under a finished answer, Chat offers Next questions and Ask "
                "offers Ask next. A question sent from one of them shows a "
                "Follow-up of line above it: each earlier question in the "
                "chain, as a link. In Chat a link scrolls to that question and "
                "lights it; in Ask, which shows one answer at a time, it opens "
                "that earlier answer under the line, and a second press folds "
                "it. The line is saved with the chat, so it is there when the "
                "chat is reopened. A question you type yourself starts a new "
                "chain. A short follow-up you type (what about running?, and "
                "Oppenheimer?, the second one) is answered like a first "
                "question; no, the data structures one stays chosen for the "
                "next shorter; and tell me more, once everything is said, "
                "says that is all your notes hold. When one word means two "
                "things in your notes (python the code, python the snake), "
                "the answer takes the newer and offers one chip for the other."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "why-this-answer",
            "keywords": (
                "why this answer", "how was this answered", "how did you get that",
                "where did this answer come from", "which model answered",
                "how long did it take", "what did it search", "explain the answer",
                "transparent", "process lines",
            ),
            "body": (
                "Under an answer in Ask, Why this answer opens the lines that "
                "made it, each with the seconds since you asked: what the "
                "question was read as, what was searched and how many notes "
                "matched, who wrote it (Atlas from your notes with no model, "
                "or the model by name, and whether it was handed the app's "
                "own answer as a fact), the shape it took, how many of the "
                "matching notes it cites, and how long it took."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "line-verdicts",
            "keywords": (
                "wrong fact", "pin as true", "pinned", "this is wrong", "that's not right",
                "mark a line wrong", "the answer is wrong", "stop saying", "correct an answer",
                "is this line right", "confirm a line",
            ),
            "body": (
                "Press a numbered mark in an answer: under the note's words, "
                "Is this line right? has Confirm and Not right. Not right "
                "leaves those sentences of the note out of every answer from "
                "the next one on, and no pattern that quotes them is offered. "
                "Confirm pins them as true: answers say them as your word, "
                "with the day you pinned them, and a model reads them that "
                "way too. Each goes on the undo stack, and lists in Settings, "
                "What it learned (Marked wrong or Pinned as true), where "
                "Delete takes it back. The note itself is never changed."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "library-skills",
            "keywords": (
                "ai skills", "built-in skill", "built in skill", "copy a skill",
                "duplicate a skill", "my skills", "skill list", "reads only",
                "changes notes", "last run of a skill", "undo a skill run", "undo the run",
            ),
            "body": (
                "Library, AI skills lists every skill: the filter beside the "
                "search shows All skills, Yours or Built-in (your own or the ones "
                "that ship with the app, each with its count), and "
                "the sort button (the arrows beside them) orders by Yours first, "
                "Name A to Z or Recently run. Each card says whether the skill Reads only or Changes "
                "notes, and how its last run went. Duplicate makes a copy of any "
                "skill, a built-in one included, to edit as your own; Delete has "
                "Undo. Settings, Skills is where a skill is written and edited. "
                "In Chat, a run's What changed list has an Undo on each change, "
                "and Undo the run puts back every note it changed at once, after "
                "showing what will go back (a board item cannot be undone, and "
                "the list says so)."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "ocr-engine",
            "keywords": (
                "ocr language", "reading language", "tesseract language", "install tesseract",
                "tesseract not working", "tesseract missing", "read again", "which engine",
                "language of the scan", "rapidocr", "ocr without tesseract",
                "choose rapidocr", "rapidocr instead of tesseract",
            ),
            "body": (
                "In the OCR workspace, the reader button's dot says whether "
                "Tesseract can read (green) or not (amber); its menu shows the "
                "version and the language it reads in. Pick the language there, "
                "and every read follows it, the background pass included. When "
                "Tesseract cannot read, the menu names the cause and offers "
                "Install, with its progress, and the tool row's ... menu opens "
                "Settings to manage it; a read it "
                "cannot do falls to the vision model, and each reading names the "
                "engine that read it. Read again reads afresh, and a reading can "
                "be edited by hand or added to an existing note. Settings, "
                "Packages shows the same status and language. RapidOCR, a second "
                "reader with nothing else to install (its own row in Settings, "
                "Packages), can be chosen in the reader button's menu, and then "
                "reads even when Tesseract is ready; with nothing chosen it reads "
                "when Tesseract isn't ready. Its models read English and Chinese, "
                "so the language does not apply. Not installed, the menu says so "
                "and its Install opens that Packages row. With no engine and no "
                "model the menu offers RapidOCR first (about 60 MB, nothing else "
                "to install), then Tesseract, each with its own Install, and Read "
                "says why it cannot read yet. The workspace remembers "
                "the reader you chose."
            ),
            "badge": {"label": "Packages", "section": "extras"},
        },
        {
            "id": "time-and-recency",
            "keywords": (
                "dates in my notes", "time words", "this friday", "next friday",
                "saved recently", "recently saved", "lately", "last note", "latest note",
                "newest note", "newest notes", "what did i write", "what did i save",
                "recent notes", "out of date", "newer note", "older note",
            ),
            "body": (
                "Ask and Chat read a note's time words as the note meant them: "
                "\"this Friday\" in a note written two weeks ago is that Friday, "
                "with its date, not this week's, and the weekly digest reads them "
                "the same way. Questions about recency are answered from the "
                "notebook rather than by searching for the words: \"What have I "
                "saved recently?\", \"what did I write lately\" or \"my last "
                "note\" lists your newest notes newest first, each cited with when "
                "it was written, and works with no AI model running. When a newer "
                "note says something else about the same thing (\"my address is "
                "now ...\"), the answer comes from the newer one and one line says "
                "what the older said; and a note that says how long it holds "
                "(\"until June\") gets a line once that time has passed, saying "
                "it may be out of date."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "model-downloads",
            "keywords": (
                "download a model", "suggested downloads", "suggested models",
                "which model fits", "fits my computer", "fit my computer", "too big",
                "hugging face", "huggingface", "pull a model", "install a model",
                "gguf", "custom model", "model name", "get a model",
                "installed models", "remove a model", "uninstall a model", "free disk space",
            ),
            "body": (
                "Settings, Models, Suggested downloads: cards grouped by purpose "
                "(chat and filing, bigger machines, search, images, reading "
                "text), each with its size on disk, the memory it asks for, what "
                "it is good at and whether it fits this computer, and one "
                "starting pick per group. A line above the cards shows the "
                "memory, free memory and graphics card it detected, and Edit "
                "corrects them when they are wrong; the badges use the "
                "corrected numbers and the memory free now. One button downloads it or puts it to "
                "use, with progress and Cancel on the card; Remove and Copy name "
                "are in its menu. Hide models too big for this computer leaves "
                "out the ones that will not fit. Download another model takes any "
                "Ollama model name or a Hugging Face link and says what it is "
                "before it downloads. Installed models shows the models you have "
                "as the same cards, with their size on this computer and what "
                "each is in use for; a card's menu puts it to use, copies its "
                "name or removes it (not while it is in use)."
            ),
            "badge": {"label": "Models", "section": "models"},
        },
        {
            "id": "appearance-panel",
            "keywords": (
                "appearance panel", "pop out appearance", "change theme without closing settings",
                "see changes while i change them", "peek", "appearance in a panel",
                "settings keep closing", "quick appearance", "section strip",
            ),
            "body": (
                "The Appearance panel is Settings, Appearance in a panel beside the "
                "app, so you see each change as you make it. Open it from the command "
                "palette (Ctrl+K, Appearance), by right-clicking the light and dark "
                "button in the top bar, or with Pop out at the top of Settings, "
                "Appearance (which closes Settings and leaves the panel). The strip "
                "under its head jumps to Theme, Colour, Text, Layout, Background art "
                "or Motion, and the panel opens on the last one you used. Peek fades "
                "the panel so you can judge a colour on the app behind it. A changed "
                "setting shows a small arrow that puts it back to its default. Drag "
                "its head to move it, to a screen edge to dock it, the corner to "
                "resize it. Back to Settings or Bring it back here returns the page."
            ),
            "badge": {"label": "Appearance", "section": "appearance"},
        },
        {
            "id": "object-move",
            "keywords": (
                "reorder", "drag to reorder", "custom order", "move a card", "change the order",
                "put in order", "alt arrow", "drag a note", "drag a document", "drag a board",
                "drag an image", "sort my own way", "copy a note", "paste a note", "copy a card",
                "paste into chat", "paste on a board", "tray", "drag a card to chat", "drag a note onto a board",
                "carry a card", "hold a card", "own order", "my own order", "own way", "my own way",
                "submenu", "side menu", "menu with an arrow", "text and description",
                "order my notes", "arrange my notes", "arrange notes", "put my notes in order", "rearrange",
            ),
            "body": (
                "Drag a card to put a list in your own order: Notes, and Library's "
                "Documents, Boards and maps, Images and Files. Press and hold a card "
                "still for a moment, then move; a dashed gap shows where it will land, "
                "and moving at once selects its text instead. A picture needs no wait, "
                "and on a phone you hold a card until it lifts, then move it. The sort then reads "
                "Custom order. Drop it where it started, or press Escape, and nothing "
                "changes. The toast has Undo. While a list is in Custom order a line above "
                "it says how to move a card, and a card's menu leads with Move up and Move "
                "down. The sort is in the Sort and view button when the row is narrow. "
                "From the keyboard, focus a card and press "
                "Alt+Up or Alt+Down to move it one place, or choose Move up or Move "
                "down in its menu (on a phone too). To copy a card, focus it and "
                "press Ctrl+C (Cmd+C on a Mac), or choose Copy card in its menu: a toast "
                "names it. Ctrl+V then attaches it in the chat box, puts a card on an "
                "open whiteboard, or writes its link in a note or a document, or its "
                "title in a reminder. You can also carry a card: press and hold, then drag it "
                "onto the chat box, an open note or document, a whiteboard, the "
                "reminder box or the tray, which outline when they would take it; "
                "rest on a page tab for half a second to open that page without "
                "letting go. Escape, or letting go over nothing, changes nothing. "
                "The tray in the status bar holds a few cards while you change pages: "
                "drop cards on it or choose Add to tray, then drag them out or click "
                "one to paste it where you were typing. In a long card menu a row "
                "with an arrow (Text and description on a picture, Copy and arrange "
                "on a board) opens a list beside it: rest the pointer on it, click it, "
                "or press Right arrow or Enter; Left arrow or Escape goes back. On a "
                "phone it opens as its own page of the menu with a back row."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "movable-panels",
            "keywords": (
                "move a panel", "move a popup", "drag a panel", "drag a popup",
                "resize a panel", "resize a popup", "make a panel bigger",
                "panel in the way", "popup in the way", "reset a panel",
                "movable", "resizable", "panel size", "dock a panel", "snap a panel",
                "panel back in the middle", "panels open where you left them",
            ),
            "body": (
                "Moving and resizing panels. On a computer with a mouse, any panel "
                "with a title row (the agent, Find anything, Statistics, Settings "
                "and the rest) can sit where you want it: drag its head to move it "
                "and drag the small corner mark at its bottom right to resize it. "
                "The head always stays on screen, and the content scrolls inside "
                "when the panel is small. A moved panel drops the dark backdrop so "
                "you can see what is beside it. Each panel remembers its place and size "
                "on this computer; the small arrow button in its head (Put back in "
                "the middle), a double-click on the head or Home puts it back. A "
                "double-click on the corner mark puts only the size back. A saved "
                "place or size that no longer fits the window opens the panel in "
                "the middle instead. "
                "Drag the head to a screen edge to dock it: a faint outline shows "
                "the zone, and letting go fills it (the left or right half, the "
                "bottom half, a quarter at a bottom corner or the top left and "
                "right, or the whole window at the top middle). A panel docked to "
                "the left or right half also moves the app aside, so the page "
                "fills the space beside it; the columns button in the panel's "
                "head, or Settings, Appearance, Move the app aside for a docked "
                "panel, turns that off (a corner dock and a panel with room "
                "short of 640 pixels beside it never move the app). The minus "
                "button beside Close (or Shift and Escape) minimises a panel: it "
                "keeps what you typed and waits as a small pill above the chat box "
                "(or the status bar), bottom left; the pill brings it back and its "
                "x closes it. Settings, "
                "Appearance, Panels open where you left them, turns the "
                "remembering off so every panel opens in the middle. From the "
                "keyboard, Tab to the corner mark (Move or resize this panel): the "
                "arrow keys move the panel 16 pixels, Shift and an arrow key "
                "resize it, and Home resets it. On a phone or any touch screen "
                "panels stay as sheets."
            ),
            "badge": {"label": "Appearance", "section": "appearance"},
        },
        {
            "id": "accessibility",
            "keywords": (
                "accessibility", "accessible", "screen reader", "zoom the app",
                "browser zoom", "200%", "400%", "keyboard only", "single key",
                "single-key", "speech input", "voice control", "toast", "toasts",
                "covering the button", "message covering", "larger text", "bigger text",
            ),
            "body": (
                "Accessibility. The app works at 200% and 400% browser zoom: on a "
                "short window Chat flows as a page, and sub-tab strips scroll with "
                "the page so a focused control stays in view. Settings, Keyboard "
                "shortcuts has Single-key shortcuts: turn it off so speech input "
                "or a stray key cannot set off m, / or ? and the other keys with "
                "no Ctrl or Alt. A toast steps aside, fading and letting clicks "
                "through, while the focused control is under it. For a screen "
                "reader every tab has one main landmark, editors and panels have "
                "names, and resize grips say how wide a panel is. Settings, "
                "Appearance has High contrast, Reduce motion, Interface animations, "
                "Text size and Zoom."
            ),
            "badge": {"label": "Appearance", "section": "appearance"},
        },
        {
            "id": "mind-map-study",
            "keywords": (
                "study the map", "study mode", "revise", "revision", "recall",
                "flashcards", "quiz me on my map", "test myself", "memorise",
            ),
            "body": (
                "Study the map. On a mind map, the board menu's Study the map "
                "goes full screen and asks one branch at a time: what is under "
                "it is hidden until you press Show (or Enter), then Knew it or "
                "Not yet marks it and moves on. Branches with topics under "
                "them are asked, and then each topic that has a note: its note is the "
                "answer, read out in the bar when you press Show. Nothing on the map changes. Your marks are kept "
                "for that map on this device, a branch you missed says so next "
                "time, and the end says how many you recalled. Esc stops."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-comments",
            "keywords": (
                "comment", "comments", "edit a comment", "reply to a comment", "resolve a comment",
                "resolved comments", "comment thread", "link in a comment", "bookmark in a comment",
                "attach to a comment",
            ),
            "body": (
                "Comments on a board or a map. Right-click a card, sticky, shape or "
                "topic and choose Comment… for a thread on it; the count on its "
                "corner opens it again. Each comment has Reply (answered one step in "
                "under it), Edit (in place: Enter keeps it, Esc puts it back, and the "
                "row then says edited), Resolve (folded under N resolved; the corner "
                "counts only what is open, and shows a tick once nothing is) and "
                "Delete (with its replies). In the box, Attach adds a bookmark, note, "
                "document or board, / offers links, a bookmark, an emoji or the date, "
                "and [[ links a note. A link alone on its line shows as a link card. "
                "Enter posts, Shift+Enter breaks the line, and Ctrl+Z takes back any "
                "change. Threads are not exported."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "sticky-notes",
            "keywords": (
                "sticky", "sticky note", "stickies", "note colour", "note color", "sticky colour",
                "text box or note", "text box vs sticky", "paper colour",
                "bold in a sticky", "format a text box", "selection bar on a board",
                "text size for some words", "different font for some words", "colour some words", "highlight colour on a board",
            ),
            "body": (
                "Sticky notes and text boxes on a board. A sticky (N, or the note "
                "on the tool dock) is paper: its colour, a lift, and a folded "
                "corner. A text box (T) is words on the board, with no fill and a "
                "faint dashed edge. Select a sticky and its bar starts with a Paper "
                "button that drops down seven papers (yellow, orange, pink, purple, blue, green, grey); any other "
                "colour, and a text box's own fill or edge, are under the bar's ... "
                "menu, Box. The folded corner can be switched off for one note (Format "
                "panel, Folded corner) or as the board's default (View, Folded sticky "
                "corners). Each change is one Undo step. Typing in either, / offers "
                "lists, a to-do, headings, links and an emoji, and [[ links a note. "
                "To format part of the text while typing, select words: the "
                "selection bar offers bold, italic, strike, highlight, code, link "
                "and a list, and Ctrl+B, Ctrl+I and Ctrl+K work too. Text style (Aa) on that "
                "bar sets a size, a font, a text colour and a highlight for the "
                "selected words only, kept in the text as {{size=24|words}}; its "
                "last button opens the Format panel's Text tab for the whole box. "
                "The box keeps "
                "markdown and shows it rendered once you finish (Format panel, "
                "Rendered markdown, to see the marks)."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "emoji-and-icons",
            "keywords": (
                "emoji", "emojis", "icon", "icons", "sticker", "stickers", "emoji picker",
                "icon picker", "insert an emoji", "insert an icon", "drag an icon", ":ph-",
            ),
            "body": (
                "Emoji and icons. One picker holds every Phosphor icon the app ships "
                "and about 470 emoji: Emoji or Icons in the tab strip under its title, "
                "type to search, Recent first, arrows and Enter to choose, Escape to close. "
                "The last Emoji group is Japanese emoticons (kaomoji such as a shrug or a table flip), "
                "found by name or by words like happy, cry and angry. On a board or a "
                "map, the smiley on the tool dock (Add on a board, Map on a map) or Insert, "
                "Emoji and icons… keeps it open: press one to place it "
                "in the middle of the view, or drag it where it goes. An emoji lands "
                "as a sticker (no card, resize it like any item), an icon as a shape "
                "you can recolour; dropped on a map topic, either becomes that "
                "topic's icon. Each is one Undo step. In a note or a document, the "
                "smiley in the formatting toolbar (the document's Insert menu) or "
                "Emoji or icon in the / menu puts one at the caret: an emoji as "
                "itself, an icon as :ph-name:, which reading shows as the icon."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-look",
            "keywords": (
                "central topic", "centre topic", "center topic", "main branch", "map levels",
                "hierarchy", "level style", "map style", "bigger centre", "core nodes",
                "solid fill", "topic style", "topic icon", "emoji on a topic", "icon picker",
            ),
            "body": (
                "How a map's topics look. A map draws as a hierarchy: the centre "
                "large, bold and filled, each main branch bold on a tinted card "
                "with a thick line, deeper topics plain. Enter on the centre adds "
                "a main branch. A topic's own size, shape or fill always beats "
                "its level's: the Text and Shape menus over a selected topic set "
                "them, and Fill offers Solid colour. View, How this map looks picks "
                "the hierarchy (Classic, Outline with plain text on the lines, "
                "Boxed, or Flat for every topic alike) and, with Setting on The "
                "centre, Main branches or Sub-topics, that level's size, weight, box, edge bar, "
                "fill, line and effect. A topic's Effect, in its Shape group: a soft shadow, or "
                "a glow in its branch colour (No effect keeps one plain on a level that has one). A topic's menu, Look: Copy this topic's style and "
                "Paste style (Ctrl+Alt+C and V, onto every selected topic), and "
                "Use this look for its level, which hands the topic's own look to "
                "every topic at its level. Each is one Undo step. A topic's icon: "
                "the Text menu's Icon row has eleven, and More icons and emoji… "
                "opens every Phosphor icon and about 470 emoji, searchable, with "
                "your recent ones first; an emoji or an icon, one per topic."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        #: Brief 69 (DOCUMENTS_PLAN 23, I1): run, preview and test, written
        #: from the run panel (documents-code.js), run-core.js's languages
        #: and the palette rows in DOC_COMMANDS.
        {
            "id": "code-run",
            "keywords": (
                "run code", "run a file", "run python", "run javascript", "run typescript",
                "typescript", "sql", "sqlite", "query", "p5", "p5.js", "sketch", "preview css",
                "preview svg", "svg", "unit test", "unit tests", "run tests", "unittest",
                "input()", "csv table", "query a csv", "run selection", "run cell", "output panel", "pyodide",
            ),
            "body": (
                "Run (Ctrl+Shift+Enter, beside Format) runs a code document in a "
                "sandbox with no network and none of your notes, and shows what it "
                "prints, its errors and their lines in the Output panel under the "
                "editor. JavaScript runs as it is (JSX in it becomes React.createElement "
                "calls); TypeScript runs with its types "
                "removed, not checked; SQL runs against a SQLite database made for "
                "the run, each statement's result a table, and a CSV document the "
                "query names is a table in it (Sales 2026.csv is sales_2026, its "
                "first row the columns); Python runs "
                "once Python is installed in Settings, Packages (until then Run is "
                "greyed and the line beside it goes there), and input() reads its "
                "lines from the panel's Input box. HTML, CSS (over a sample page), "
                "SVG and a p5.js sketch (New from a template, p5.js sketch) show as "
                "a page; Live in the panel refreshes it as you type (the panel's buttons are icons: point at one for its name). A file of "
                "tests (describe, it and expect in JavaScript or TypeScript; "
                "unittest or test_ functions in Python) runs its tests, each "
                "listed with its time and a failure underlined on its line; Run "
                "tests in the panel asks for them. The palette has Run the "
                "selected lines and Run the cell at the caret (between # %% "
                "markers). Stop ends a run; one still going after two seconds is "
                "listed in Activity, whose Stop ends it too. Beside Output, "
                "Problems lists every underline and Tests each test; the Console "
                "(Ctrl+Shift+Y) evaluates a line in what the run left, Python for "
                "a .py file and JavaScript for the rest, Up recalling the last. "
                "Debug (F5) steps "
                "JavaScript, TypeScript and Python; see the debugger."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        #: Brief 70 (DOCUMENTS_PLAN 23, I2): the debugger, written from the
        #: Debug tab (documents-code.js, `docDebugView`), the gutter
        #: (`docDebugExtension`) and the palette rows in DOC_COMMANDS.
        {
            "id": "debugger",
            "keywords": (
                "debug", "debugger", "debugging", "breakpoint", "breakpoints", "step over",
                "step in", "step into", "step out", "watch", "watch expression", "call stack",
                "variables", "conditional breakpoint", "f5", "f9", "f10", "f11", "bdb",
            ),
            "body": (
                "Debug runs a JavaScript, TypeScript or Python document to its "
                "first breakpoint and stops there. Click beside a line number (or "
                "press F9 on the line) for a breakpoint; right-click it to add a "
                "condition, and it stops only when that is true. A document keeps "
                "its breakpoints on this device after a reload. Press F5, or "
                "Start debugging in the run panel's Debug tab; the stopped line is lit, and "
                "the Debug tab shows Variables (the frame's names, then Globals; a "
                "list, dict or object opens into its items), "
                "Watch (type an expression under it; each stop evaluates it), the "
                "Call stack (a row goes to its line) and Breakpoints. F10 steps "
                "over a line, F11 into a call, Shift+F11 out of the function, F5 "
                "continues and Shift+F5 stops; the same five are buttons at the "
                "top of the tab. An error nothing catches stops on the line that "
                "raised it, with its traceback and the frame's variables. A Python "
                "file of tests debugs through its tests: a breakpoint inside one "
                "stops there, and the Tests tab lists each result. Python's "
                "input() asks in the panel mid-run. Python debugging needs a window "
                "that gives SharedArrayBuffer (the app's own does); JavaScript is "
                "stepped by an interpreter that reads ES5, so let, const, arrow "
                "functions and template strings are rewritten for it, and a class, "
                "destructuring or async code is named with its line and only Run "
                "takes it. A script that uses the page debugs against a stand-in "
                "document, so nothing is drawn."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        #: INBOX 788: the code panel beside a code file's editor, written from
        #: documents-codekit.js and its markup (`#doc-code-side`).
        {
            "id": "code-panel",
            "keywords": (
                "snippet", "snippets", "code snippet", "code library", "code modules",
                "save snippet", "insert snippet", "code panel", "coding assistant",
                "explain code", "explain this code", "refactor", "write tests for",
                "sections", "text sections", "section library", "ready-made blocks",
                "meeting notes block", "insert a section", "save a section",
            ),
            "body": (
                "Assistant and Snippets (beside Run, on a code document) open the "
                "code panel beside the editor, a sheet on a phone. The Assistant "
                "tab works on the selected lines, or the whole file: Explain, Fix "
                "(the problem at the caret), Write tests, Refactor, or a question "
                "typed below them (sent empty, it flags the field). A change comes back as a diff: Apply puts it in "
                "the editor, where one Ctrl+Z takes it out, and Reject leaves the "
                "file alone. With no model, Fix applies the quick fix, the tools "
                "row (Quick fix, Format, Run tests, Find usages) works as it is, "
                "a question those tools answer (format, run the tests, where a name "
                "is used, the symbols) runs the tool, and any other goes to the "
                "needle extra when it is installed; otherwise a Needs a model line "
                "links to Settings. Explain, Write tests, Refactor and the inline "
                "Ask bar (Ctrl+J) stay on screen, disabled, and a press says why. "
                "The Snippets tab lists the "
                "built-in library and your own snippets, this file's language "
                "first (Show every language for the rest); the search matches "
                "names, tags and languages, and #io matches the tag io. A row "
                "inserts at the caret, or drag a row into the text and it lands where a "
                "bar shows; one Ctrl+Z takes it out; built-in rows "
                "have stops that Tab walks. The panel's Save keeps the selected "
                "code: #words in the name you give become its tags. Each of your "
                "own rows has a menu to insert, rename or retag, and delete; "
                "saving, renaming and deleting each undo. Snippets belong to the "
                "notebook, not to one document. In a text document the same "
                "panel is Sections (the dock's Sections button, or Ctrl+K): "
                "ready-made blocks such as a meeting block, a risk table or a "
                "callout, with today's date filled in and prompts Tab walks. A "
                "row goes in at the caret or where you drop it, on its own lines "
                "with a blank line round it, and one Ctrl+Z takes it out; Save "
                "keeps the selected text as a section of your own."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
    ]
)

#: How each entry is laid out as a system answer. `title` heads it, `path`
#: says where it lives, `steps` are there when there is something to do in
#: order. An entry with no meta is laid out from its id and body alone.
TOPIC_META: dict[str, dict] = {
    "open-questions": {"title": "Open questions", "path": "Notes tab, Questions"},
    "make-a-diagram": {"title": "Making a diagram", "path": "Library tab, Create"},
    "capture": {"title": "Capturing a note", "path": "Notes tab", "steps": (
        "Open the Notes tab (t then n).", "Type into Capture a thought.", "Press Save: a local AI files it and suggests tags.")},
    "ask-chat": {"title": "Asking and chatting", "path": "Chat tab, or Ctrl+Shift+A over any tab"},
    "skills": {"title": "Skills", "path": "Settings, Skills"},
    "graph": {"title": "The graph", "path": "Graph tab"},
    "reminders": {"title": "Reminders", "path": "Reminders tab", "steps": (
        "Open the Reminders tab (t then r).", "Type into Remind me to, with a time such as \"tomorrow at 5pm\".",
        "Press Add; pick a priority or a repeat first if you like.")},
    "dashboard": {"title": "The dashboard", "path": "Dashboard tab"},
    "library": {"title": "The Library", "path": "Library tab"},
    "documents": {"title": "Documents", "path": "Library tab, Documents"},
    "whiteboard": {"title": "Whiteboards", "path": "Library tab, Boards & maps"},
    "timeline": {"title": "The Timeline", "path": "Timeline tab"},
    "memory": {"title": "What it remembers", "path": "Settings, What it remembers"},
    "spaces": {"title": "Spaces", "path": "The picker at the top of the sidebar"},
    "appearance": {"title": "Appearance", "path": "Settings, Appearance"},
    "statusbar": {"title": "The status bar", "path": "Settings, Appearance, Status bar"},
    "shortcuts": {"title": "Keyboard shortcuts", "path": "Settings, Keyboard shortcuts"},
    "models": {"title": "Models", "path": "Settings, Models"},
    "model-bench": {"title": "Test my models", "path": "Settings, Models, Test my models", "target": "bench-box"},
    "margin-reader": {"title": "The margin reader", "path": "A document's menu, While you write, Margin reader"},
    "web-clipper-bookmark": {"title": "Clip a page from your browser", "path": "Settings, Import & export, Web clipper", "target": "web-clip-box"},
    "import-apps": {"title": "Import from another app", "path": "Settings, Import & export, Import from another app", "target": "import-app-box"},
    "simple-mode": {"title": "Simple mode", "path": "Settings, General, Simple mode", "target": "simple-mode-box"},
    "usage-ledger": {"title": "What you use", "path": "Settings, General, What you use", "target": "usage-box"},
    "statistics": {"title": "Statistics", "path": "Dashboard, Activity heatmap, Statistics"},
    "chat-private": {"title": "Private chat", "path": "Chat, the gear under the message box, Private chat"},
    "timer": {"title": "Timer and stopwatch", "path": "Command palette, timer"},
    "calculator": {"title": "The calculator", "path": "Command palette, Calculator"},
    "manual": {"title": "The manual", "path": "Settings, Help, Open the manual"},
    "first-steps": {"title": "First steps and the sample notebook", "path": "Dashboard, Get started"},
    "live-captions": {"title": "How do I get live captions", "path": "Library, Recordings, Captions"},
    "count-words": {"title": "Count words", "path": "Command palette, Count words"},
    "translate-offline": {"title": "Translate this, offline", "path": "Command palette, Translate this"},
    "insert-template": {"title": "Insert a template", "path": "Command palette, insert template"},
    "capture-anywhere": {"title": "Capture from anywhere", "path": "Settings, Keyboard shortcuts, Capture from anywhere", "target": "capture-anywhere-box"},
    "install-app": {"title": "Install as an app", "path": "Settings, About, Install as an app"},
    "storage": {"title": "Where your data lives", "path": "Settings, Import & export"},
    "websearch": {"title": "Web search", "path": "Settings, Web search"},
    "privacy": {"title": "Privacy", "path": "Settings, Privacy"},
    "undo-bin": {"title": "Undo and the bin", "path": "the bin: the Library's Include the bin, or Ctrl+Z right after"},
    "autonomous": {"title": "Autonomous background AI", "path": "Settings, Background tasks"},
    "guide": {"title": "Atlas, the guide", "path": "Status bar, the compass (Ctrl+Shift+H)"},
    "command-palette": {"title": "The command palette", "path": "Ctrl+K"},
    "security": {"title": "Account and security", "path": "Settings, Account & security"},
    "troubleshooting": {"title": "When something does not work", "path": "Settings, Models, then Settings, Logs", "steps": (
        "Open Settings, Models and check a model is connected.", "Start Ollama, LM Studio or a llama.cpp server, pick a model and press Connect.", "Looks out of date or broken after an update: open Settings, Import & export and press Clear app cache.", "Still stuck: open Settings, Logs and press Email it under the support bundle.")},
    "tour": {"title": "The guided tour", "path": "Settings, Help", "steps": (
        "Open Settings, Help, or press Ctrl+K and choose Take the guided tour.", "Press Start the tour for all of it, or a part's row (its name over what it covers) for just that part.", "Next and Back move through it; Finish ends it.")},
    "personas": {"title": "Personas", "path": "Settings, Personas"},
    "templates": {"title": "Templates", "path": "Settings, Templates"},
    "updates": {"title": "Updates", "path": "Settings, About"},
    "name": {"title": "The name, formerly MemoryMap AI", "path": "Settings, About"},
    "notifications": {"title": "Notifications", "path": "The bell in the top bar"},
    "companion": {"title": "The corner companion", "path": "Settings, Appearance, Atlas and faces, Corner companion", "steps": (
        "Open Settings, Appearance, Atlas and faces.", "Pick who it is under Corner companion.", "Right-click it on the page for its menu; Ctrl+Shift+Y shows or hides it.")},
    "image-viewer": {"title": "The picture and PDF viewer", "path": "Library, open a picture or PDF"},
    "companion-throw": {"title": "Throwing the companion", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "companion-travel": {"title": "How the companion moves", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "desktop-companion": {"title": "The companion on the desktop", "path": "Settings, About, Show the companion on the desktop"},
    "what-is-atlas": {"title": "What Atlas does", "path": "The Chat tab, or Ctrl+Shift+A over any tab"},
    "atlas-look": {"title": "How Atlas looks", "path": "Settings, Appearance, Atlas and faces, Atlas style and Atlas look"},
    "faces": {"title": "Generated faces", "path": "Settings, Appearance, Atlas and faces"},
    "profile": {"title": "Your profile", "path": "Settings, Profile"},
    "tools-setting": {"title": "Tools it can use", "path": "Settings, Tools it can use"},
    "learned": {"title": "What it learned", "path": "Settings, What it learned"},
    "general-settings": {"title": "General settings", "path": "Settings, General"},
    "search-index": {"title": "Search and index", "path": "Settings, Search and index"},
    "search-engine-moved": {"title": "Old search files", "path": "Settings, Search and index, Old search files"},
    "answer-style": {"title": "Answer style", "path": "Settings, Personas, Answer style"},
    "background-tasks": {"title": "Background tasks", "path": "Settings, Background tasks"},
    "health": {"title": "Health", "path": "Settings, About, Health"},
    "maintenance": {"title": "Maintenance", "path": "Settings, About, Maintenance", "steps": (
        "Open Settings, About and find Maintenance.", "Check this computer shows one row per check, each with what to do.", "Reinstall on next start rebuilds the app's Python environment when the launcher next opens it; your notes are not touched.", "Uninstall… shows the steps and the command, with Export my notes first.")},
    "activity": {"title": "Activity", "path": "The status bar's job slot, or the palette, Activity"},
    "packages": {"title": "Packages", "path": "Settings, Packages"},
    "import-export": {"title": "Import and export", "path": "Settings, Import & export"},
    "logs": {"title": "Logs and reporting a problem", "path": "Settings, Logs", "steps": (
        "Open Settings, Logs.", "Open the three dots and press Copy diagnostics, then paste it into your message.", "For a bug that is not about speed, press Email it under the support bundle and attach the bundle.")},
    "find-anything": {"title": "Find anything", "path": "Ctrl+P, or the magnifying glass in the status bar"},
    "background-art": {"title": "The animated background", "path": "Settings, Appearance, Animated background"},
    "themes": {"title": "Themes, colour and type", "path": "Settings, Appearance"},
    "appearance-panel": {"title": "The Appearance panel", "path": "Ctrl+K, Appearance, or right-click the light and dark button"},
    "tabs-overview": {"title": "The app at a glance", "path": "The tabs along the top"},
    "phone-nav": {"title": "The app on a phone", "path": "The bar along the bottom, then More"},
    "settings-overview": {"title": "Finding your way round Settings", "path": "The gear in the top bar, or Ctrl+,"},
    "lock": {"title": "Passwords and locking", "path": "Settings, Account & security"},
    #: Titles for the entries that had none (INBOX 448): Settings, Help lists
    #: every entry by its title, and an id read aloud ("Files images") is not one.
    "files-images": {"title": "Pictures, scans and PDFs", "path": "Library tab, Images and Files"},
    "archive": {"title": "Archiving", "path": "Each item's own menu, and the Library's Archived filter"},
    "voice": {"title": "Dictation, recordings and read aloud", "path": "Notes tab, the microphone; Library, Recordings"},
    "meetings": {"title": "Meeting notes", "path": "Dashboard, New meeting; a meeting's meeting chip"},
    "extract-notes": {"title": "Split text into notes", "path": "Notes tab, Writing room, More, Split into notes"},
    "favourites": {"title": "Favourites", "path": "A note's star"},
    "ocr-workspace": {"title": "The OCR workspace", "path": "Read text, on any image or PDF"},
    "document-history": {"title": "A document's history", "path": "A document's ... menu, History"},
    "writing-checks": {"title": "Spelling, grammar and wording", "path": "The document editor"},
    "notebook-questions": {"title": "Questions about your notebook", "path": "Chat tab, or Ask on the Notes tab"},
    "studyhelp": {"title": "Study help with no model", "path": "Chat tab, or Ask on the Notes tab"},
    "contradictions": {"title": "Notes that disagree", "path": "Dashboard tab"},
    "write-with-atlas": {"title": "Writing room", "path": "Notes tab, Writing room"},
    "search": {"title": "Searching everything", "path": "Ctrl+P, or the dashboard's search box"},
    "links": {"title": "Linking notes", "path": "Type [[ in a note"},
    "performance": {"title": "When the app feels slow", "path": "Settings, Appearance"},
    "translate": {"title": "Translating", "path": "Notes tab, Writing room"},
    "tags-categories": {"title": "Tags and categories", "path": "A note's own row, or Capture's Filing menu"},
    "code-files": {"title": "Code documents", "path": "Library tab, Documents"},
    "code-completions": {"title": "Completions and snippets in code", "path": "A code document, as you type"},
    "code-run": {"title": "Running, previewing and testing code", "path": "A code document, Run", "steps": (
        "Open a code document (.js, .ts, .sql, .py, .html, .css, .svg).",
        "Press Run, or Ctrl+Shift+Enter.",
        "Read the Output panel under the editor; Line N goes to the line.",
        "Ctrl+Shift+Y opens the Console tab: type a line and press Enter.")},
    "code-panel": {"title": "The code panel: assistant, snippets and text sections", "path": "A code document, Assistant or Snippets (beside Run); a text document, Sections"},
    "debugger": {"title": "Debugging code", "path": "A code document, the gutter beside a line number, F5", "steps": (
        "Open a JavaScript, TypeScript or Python document.",
        "Click beside a line number, or press F9 on it, for a breakpoint.",
        "Press F5; at the stop, F10, F11 and Shift+F11 step, F5 continues.",
        "Read Variables, Watch and the Call stack in the panel's Debug tab.")},
    "mind-maps": {"title": "Mind maps", "path": "Library tab, Boards & maps"},
    "whiteboard-controls": {"title": "Whiteboard keys: tools and moving around", "path": "Library tab, Boards & maps"},
    "whiteboard-selection": {"title": "Whiteboard keys: selection, menus and presenting", "path": "Library tab, Boards & maps"},
    "board-history": {"title": "A board's history, and putting it back", "path": "A board, Board, History…"},
    "board-library": {"title": "The board's library, layers and pages", "path": "A board, the Sidebar button in its top bar"},
    "board-library-saving": {"title": "Saving to the board's library", "path": "A board, Ctrl+Shift+S or right-click, Library"},
    "board-templates": {"title": "Board and map templates", "path": "Library tab, Boards & maps, New, From a template"},
    "board-format": {"title": "The board's Format panel", "path": "A board, Ctrl+Shift+P or the selection's More menu"},
    "board-connectors": {"title": "Connector bends, connection points and importing diagrams", "path": "A board, Insert, Mermaid, draw.io or board SVG"},
    "board-workshop": {"title": "Voting dots and a workshop timer", "path": "A board, Board menu, Workshop"},
    "board-diagram-tools": {"title": "Diagram tools: zoom to the selection, tidy as a tree, change a shape, link a shape, shrink text to fit", "path": "A board, Arrange, View, or a selection's More"},
    "board-paste": {"title": "Paste on a board or map: options and Paste special", "path": "A board, Edit, Paste special"},
    "mind-map-controls": {"title": "Mind map keys and controls", "path": "Library tab, Boards & maps"},
    "documents-controls": {"title": "Document editor keys and controls", "path": "Library tab, Documents"},
    "live-view-marks": {"title": "Markdown marks in Live view", "path": "Library tab, Documents, Edit, Live"},
    "documents-features": {"title": "Document editor features", "path": "Library tab, Documents"},
    "documents-paste": {"title": "Paste options and Paste special", "path": "Library tab, Documents, document menu"},
    "documents-turn-into": {"title": "Turn into: change a block to a heading, list, quote or code", "path": "Library tab, Documents, select text, Turn into"},
    "mind-map-features": {"title": "Mind map features", "path": "Library tab, Boards & maps"},
    "mind-map-import-export": {"title": "Mind map templates, import and export", "path": "Library tab, Boards & maps"},
    "mind-map-study": {"title": "Study the map", "path": "Library tab, Boards & maps, a map's board menu"},
    "mind-map-look": {"title": "How a map's topics look", "path": "Library tab, Boards & maps, a map"},
    "emoji-and-icons": {"title": "Emoji and icons", "path": "The smiley on a board's or map's tool dock, or its Insert menu; a topic's Text menu"},
    "board-comments": {"title": "Comments on boards and maps", "path": "An item's right-click menu, Comment…"},
    "sticky-notes": {"title": "Sticky notes and text boxes", "path": "A board's tool dock, Add"},
    "callouts": {"title": "Callouts", "path": "Library tab, Documents"},
    "graph-controls": {"title": "Graph keys and controls", "path": "Graph tab"},
    "graph-display": {"title": "More graph controls", "path": "Graph tab, Options"},
    "graph-options-help": {"title": "What the Options sections do", "path": "Graph tab, Options"},
    "properties": {"title": "Note properties and types", "path": "a note's ⋯, Properties; or the command palette, Note types"},
    "entities": {"title": "People and things", "path": "Graph tab, an entity; or the command palette, People and things"},
    "chat-controls": {"title": "Chat keys and controls", "path": "Chat tab"},
    "wrap-lines": {"title": "Wrap lines in tables and code", "path": "Chat tab, a table or code block"},
    "notes-controls": {"title": "Notes keys, filters and selection", "path": "Notes tab"},
    "library-controls": {"title": "Library controls", "path": "Library tab"},
    "timeline-controls": {"title": "Timeline controls", "path": "Timeline tab"},
    "reminders-controls": {"title": "Reminders controls", "path": "Reminders tab"},
    "dashboard-controls": {"title": "Dashboard controls", "path": "Dashboard tab"},
    "hidden-features": {"title": "Hidden features and power keys", "path": "Everywhere"},
    "quick-note": {"title": "Quick note", "path": "Alt+N, from any tab"},
    "editor-offers": {"title": "Offers while you write", "path": "Notes, Capture, or a note's Edit form"},
    "quick-add": {"title": "Dates and tags read as you type", "path": "Reminders, Quick note, New meeting, Timeline search, the command palette"},
    "note-outbox": {"title": "Saving while the server is away", "path": "Notes tab, above Capture"},
    "attachments": {"title": "Pictures and files in a note", "path": "Capture, or a note being edited"},
    "chat-attach-cards": {"title": "Notes and files attached to a chat message", "path": "Chat, above the box and above a sent message"},
    "chat-model-picker": {"title": "Choosing the model for a box", "path": "Chat, Ask and Writing, beside the mode buttons"},
    "filing": {"title": "How a note is filed", "path": "A note's card, beside its category"},
    "suggested-tags": {"title": "Suggested tags", "path": "A note's card"},
    "tag-manager": {"title": "Managing tags", "path": "Notes tab, the ... menu, Manage tags"},
    "tidy": {"title": "Tidy: reviews with no AI", "path": "Notes tab, the broom in the dock"},
    "manage-categories": {"title": "Managing categories", "path": "Notes tab, the Categories head in the sidebar"},
    "note-history": {"title": "A note's history", "path": "A note's menu, History"},
    "notes-list": {"title": "Sorting and browsing notes", "path": "Notes tab, Your notes"},
    "card-content": {"title": "What a note's card draws", "path": "Notes tab, a note's card"},
    "addresses": {"title": "Every view has an address", "path": "The browser's address bar"},
    "bookmarks": {"title": "Bookmarks", "path": "Library tab, Bookmarks"},
    "contents": {"title": "Contents, the notebook's outline", "path": "Library tab, Contents"},
    "answers-from-notes": {"title": "Answers from your notes, no AI", "path": "Notes tab, Ask, the AI switch", "steps": (
        "Open Ask on the Notes tab.", "Turn the AI switch off beside the answer length.", "Ask: the answer is quoted from your notes, with no AI.")},
    "follow-up-trail": {"title": "Where a follow-up came from", "path": "Chat tab, or Ask in the Notes tab, under an answer"},
    "why-this-answer": {"title": "Why this answer", "path": "Notes tab, Ask, under an answer"},
    "line-verdicts": {"title": "Wrong fact and Pin as true", "path": "Ask or Chat, a numbered mark in an answer"},
    "answer-pictures": {"title": "Pictures in answers", "path": "Chat tab, or Ask in the Notes tab, Grounded in"},
    "library-skills": {"title": "AI skills in the Library", "path": "Library tab, AI skills"},
    "object-move": {"title": "Moving, copying and carrying cards", "path": "Notes tab, or Library tab, drag a card or press Ctrl+C; the tray in the status bar"},
    "ocr-engine": {"title": "Tesseract and the reading language", "path": "The OCR workspace, the reader button"},
    "time-and-recency": {"title": "Dates and recent notes in answers", "path": "Chat tab, or Ask on the Notes tab"},
    "model-downloads": {"title": "Downloading a model", "path": "Settings, Models, Suggested downloads"},
    "accessibility": {"title": "Accessibility and zoom", "path": "Settings, Keyboard shortcuts and Appearance"},
    "movable-panels": {"title": "Moving and resizing panels", "path": "Any panel with a title row, on a computer with a mouse"},
}

#: **How Settings, Help lists the entries** (INBOX 448 (1)). The page used to
#: hold thirteen hand-written topics beside this table's sixty, kept in step by
#: hand, and they had drifted (it still taught "g then a letter" for the tab
#: chord). It is drawn from this table now (`GET /help/topics`, settings-find.js
#: `renderHelpTopics`), in these groups and this order, so a new entry shows
#: on the page the moment it exists; `tests/test_help_coverage.py` fails when an
#: entry is in no group, or in two.
HELP_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Getting started", (
        "tabs-overview", "phone-nav", "first-steps", "tour", "guide", "manual", "hidden-features", "shortcuts",
        "command-palette", "find-anything", "find-a-place", "search", "addresses", "settings-overview", "settings-reset", "install-app", "name",
    )),
    ("Writing notes", (
        "capture", "quick-note", "quick-add", "editor-offers", "autocorrect", "share-note", "capture-anywhere", "note-outbox", "attachments", "quick-sketch", "notes-controls",
        "notes-list", "card-content", "note-history", "links", "favourites", "templates",
        "write-with-atlas", "translate", "translate-offline", "extract-notes", "voice", "live-captions", "meetings",
    )),
    ("Filing, tags and categories", (
        "tags-categories", "filing", "suggested-tags", "tag-manager", "manage-categories", "tidy",
    )),
    ("Asking Atlas", (
        "ask-chat", "answers-from-notes", "chat-controls", "chat-private", "chat-attach-cards", "chat-model-picker", "wrap-lines", "slash-commands", "chat-acts", "tasks", "nicknames", "follow-up-trail", "why-this-answer", "line-verdicts", "answer-pictures", "time-and-recency", "notebook-questions", "studyhelp",
        "contradictions", "skills", "personas", "answer-style", "memory", "learned", "open-questions",
    )),
    ("Documents and code", (
        "documents", "documents-controls", "live-view-marks", "documents-features", "documents-paste", "documents-turn-into", "callouts", "equation-editor", "document-history", "writing-checks", "code-files", "code-completions", "code-run",
        "debugger", "code-panel", "margin-reader",
    )),
    ("Boards and maps", (
        "whiteboard", "whiteboard-controls", "whiteboard-selection", "board-history", "board-library", "board-library-saving", "board-templates", "board-format", "board-connectors", "board-diagram-tools", "board-workshop", "board-paste", "make-a-diagram", "mind-maps", "mind-map-controls", "mind-map-features", "mind-map-import-export", "mind-map-study", "mind-map-look", "emoji-and-icons",
        "board-comments", "sticky-notes",
        "mind-map-structure", "mind-map-lines", "mind-map-callouts", "board-current-layer", "board-keyboard-create", "board-hand-drawn", "board-tables", "board-mermaid", "board-edit-data", "board-colours",
    )),
    ("Library and files", (
        "library", "library-controls", "bookmarks", "web-clipper-bookmark", "contents", "library-skills",
        "files-images", "image-viewer", "ocr-workspace", "ocr-engine", "object-move", "archive", "undo-bin",
    )),
    ("Graph, Timeline, Reminders and Dashboard", (
        "graph", "graph-controls", "graph-display", "graph-options-help", "entities", "properties", "timeline", "timeline-controls", "reminders",
        "reminders-controls", "dashboard", "dashboard-controls", "patterns", "notifications", "spaces", "statistics",
    )),
    ("Small tools", (
        "timer", "calculator", "count-words", "insert-template",
    )),
    ("Look and feel", (
        "appearance", "appearance-panel", "themes", "simple-mode", "accessibility", "movable-panels", "performance", "background-art",
        "statusbar", "companion", "companion-travel", "companion-throw", "atlas-look", "faces",
    )),
    ("Models and the AI", (
        "models", "what-is-atlas", "model-downloads", "model-bench", "tools-setting", "autonomous", "websearch",
        "search-index", "search-engine-moved", "packages",
    )),
    ("Privacy and your data", (
        "privacy", "security", "encryption", "lock", "phone", "lan-networks", "two-computers", "delete-data", "storage", "import-export", "import-apps", "usage-ledger", "background-tasks", "activity", "health",
    )),
    ("Settings and support", (
        "profile", "general-settings", "desktop-companion", "updates", "maintenance", "logs", "troubleshooting", "credits",
    )),
]


#: The acts Chat does from a sentence: generated from the act registry
#: (`ai/act_registry.py`, CHAT_PLAN decision 53), so a new act is in the Guide the
#: moment it is in the registry, and a renamed one cannot drift.
#: The Guide's gaps from the engine probe (CHAT_PLAN section 2, the help
#: row; `archive/agent-remaining/engine-probe-1010.md`): the phone, two computers,
#: encryption, deleting your data and sharing a note had no topic of their
#: own. `tests/test_guide_gaps.py` holds the probe's table at 1.0.
MORE_TOPICS.extend([
    {
        "id": "phone",
        "keywords": ("phone", "on my phone", "mobile", "iphone", "android", "tablet", "ipad", "use it on my phone",
                     "open it on my phone", "install on my phone", "phone storage", "runs on my phone",
                     "public wifi", "public network", "allow a device", "new device"),
        "body": (
            (
                "Your phone opens this computer's notebook over your own network: turn on Allow other "
                "devices on this network (Settings, Account & security, Other devices), then open the "
                "large address it shows (Copy is beside it, and QR code shows a code the phone's camera "
                "opens; Other addresses folds the rest) on the phone and sign in with your password. On "
                "an iPhone, press Install the certificate on the lock screen, then, in the iPhone's own "
                "Settings app, General, VPN and Device Management to install it and About, Certificate "
                "Trust Settings to trust it; its ? has the steps. The phone's first sign-in waits until "
                "you choose Allow on this computer (a notice with Allow and Deny); allowed devices are "
                "listed with Remove. On a network you have not trusted (a cafe, an airport) nothing can "
                "reach the notebook until you trust it: the wifi icon in the status bar (Alt+L) says "
                "open, closed or off, and its panel has the switch, the address and the trusted and "
                "untrusted networks. A phone's hotspot works too, with no restart. If the phone cannot "
                "connect, both must be on the same Wi-Fi (not a guest one), this computer's firewall must"
                " let the app in (on Windows, Other devices shows the one line to paste into an "
                "administrator Command Prompt, for private networks only), and on an iPhone the browser "
                "needs Local Network on (the iPhone's Settings app, Privacy & Security, Local Network) "
                "with any VPN or ad-blocking app (AdGuard's local VPN) paused. The phone reads and writes"
                " the same notebook, and a note changed on one shows on the other within seconds; nothing"
                " goes through the internet, so the computer has to be on. A phone never makes this "
                "computer act: installing, downloading a model, restoring a backup, quitting, opening a "
                "folder and the settings that point this computer elsewhere say Not available on this "
                "device, and an export downloads to the phone itself."
            )
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "two-computers",
        "keywords": ("two computers", "another computer", "second computer", "sync", "syncing", "laptop and desktop",
                     "move to a new computer", "new computer", "other computer", "use it on two"),
        "body": (
            "One notebook lives on one computer, in its data folder (Settings, Import "
            "& export shows where). There is no sync between two copies. To move to a "
            "new computer, save a full backup there and restore it on the new one, or "
            "copy the data folder while the app is closed. To use one notebook from a "
            "second computer at the same time, open it over your network from the "
            "first: Settings, Account & security, Other devices."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "encryption",
        "keywords": ("encrypted", "encryption", "is my data encrypted", "encrypt my notes", "is it secure", "secure",
                     "who can read my notes"),
        "body": (
            "Private notes are encrypted at rest with a key made from your unlock "
            "password; without it their words cannot be read from the data folder. "
            "Other notes are stored as they are written, in the data folder on your "
            "computer, so your disk's own encryption is what keeps them. A full "
            "backup can be sealed with a password (Settings, Import & export). A "
            "recovery key (Settings, Account & security) opens private notes if the "
            "password is forgotten, and Re-encrypt private notes makes a new key."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "delete-data",
        "keywords": ("delete my data", "delete everything", "erase my data", "remove my data", "wipe", "uninstall",
                     "start over", "delete all my notes"),
        "body": (
            "A deleted note, document or reminder goes to the bin first: Undo or the "
            "bin's Restore brings it back, and the bin clears itself after the time "
            "set in Settings, General, Bin (or Empty the bin at once). Everything "
            "else is in the data folder (Settings, Import & export shows where): to "
            "erase the notebook, save a backup if you want one, close the app and "
            "delete that folder, then uninstall. Nothing is kept anywhere else."
        ),
        "badge": {"label": "General", "section": "general"},
    },
    {
        "id": "share-note",
        "keywords": ("share a note", "share this note", "send a note", "share", "sharing", "give someone a note",
                     "email a note"),
        "body": (
            "Three ways, none through a server: the note's menu, Download .md, "
            "saves it as a Markdown file to send; copy its "
            "address (every view has one) for anyone opening this notebook with "
            "you; or let them open the notebook from their phone or computer on "
            "your network (Settings, Account & security, Other devices)."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
])
#: INBOX 896, 900: the status bar's Other devices icon and its networks,
#: a topic of its own so "lock" stays under the reply budget.
MORE_TOPICS.append({
    "id": "lan-networks",
    "keywords": ("wifi icon", "lan icon", "lan mode", "trusted network", "untrusted network",
                 "trust a network", "trust this network", "stop trusting", "forget a network",
                 "turn off other devices", "other devices off", "lan off"),
    "body": (
        "The wifi icon in the status bar, on this computer only, says whether other "
        "devices on your network can open the app: green open, amber closed on this "
        "network (one you have not trusted, or no network at all), plain off. Press "
        "it, or Alt+L, for its panel (a sheet on a phone-sized window): the switch, "
        "the address to type, Trust this network, and two lists, one row per "
        "network, named by its Wi-Fi name where this computer can read it, its "
        "address range under it. Trusted networks have Stop trusting and Forget; "
        "Untrusted networks, every network the app saw and stayed closed on, have "
        "Trust (asks your password) and Forget, always on the row. The "
        "switch applies at once, with no restart: off closes the port and signs "
        "every other device out, and when the wifi drops or you join a network you "
        "have not trusted the port closes by itself. Left on and unused for 14 days, "
        "it turns itself off and says so in the bell. Each time a phone opens the "
        "app, the privacy receipt lists it as a connection coming in, with its "
        "address only. A phone can never turn it on, trust a network or loosen a "
        "setting: those say Not available on this device."
    ),
    "badge": {"label": "Account & security", "section": "account"},
})
TOPIC_META.update({
    "lan-networks": {"title": "Other devices and networks", "path": "The wifi icon in the status bar, or Settings, Account & security, Other devices"},
    "phone": {"title": "On your phone", "path": "Settings, Account & security, Other devices"},
    "two-computers": {"title": "Two computers", "path": "Settings, Import & export"},
    "settings-reset": {"title": "Resetting and moving your settings", "path": "Settings, Import & export, Your settings",
                       "target": "settings-file-group"},
    "encryption": {"title": "What is encrypted", "path": "Settings, Account & security"},
    "delete-data": {"title": "Deleting your data", "path": "Settings, General, Bin"},
    "share-note": {"title": "Sharing a note", "path": "A note's menu, Download .md"},
})


#: canvasdepth2 (INBOX 797, round 2): the map's and the board's newer tools,
#: in topics of their own because `mind-map-features` and the board's own
#: entries are at the reply budget.
MORE_TOPICS.extend([
    {
        "id": "mind-map-structure",
        "keywords": (
            "structure of a branch", "branch structure", "branch layout", "org chart branch",
            "fishbone branch", "one branch as", "lay out one branch", "logic chart branch",
            "different layout for a branch", "xmind structure",
        ),
        "body": (
            "A branch can have its own structure, as in XMind: a topic's menu, "
            "Structure, lays the branch under it out as a logic chart, an org chart, "
            "a tree table, a timeline, a fishbone, both sides, a tree to the right "
            "or left, or radial, while the rest of the map keeps its layout. The "
            "branch is laid out as one block, so nothing else overlaps it; Follow "
            "the map's layout takes it back. Ctrl+Z undoes it in one step."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "mind-map-lines",
        "keywords": (
            "straight lines on a map", "map line style", "lines arent straight", "curved lines",
            "elbow lines", "which side a line leaves", "side of a topic", "line end side",
            "pin a line to a side", "topic shape", "hexagon topic", "diamond topic", "cloud topic",
            "circle topic", "chevron topic", "underline topic", "core idea shape",
        ),
        "body": (
            "Beside a map's Layout picker, the line style picker draws every line "
            "Curved, Straight or Elbow (right angles with rounded corners); a "
            "topic's own line Shape in its strip still wins. Point at a line, or "
            "select a topic, and each end of its line shows a hollow dot: drag it "
            "round the topic to choose the side the line leaves or enters, in any "
            "layout, and it stays on that side when either topic moves. "
            "Double-click the dot, or the topic's menu, Lines, Line ends: back to "
            "Auto, to let the layout choose again. A topic's Box picker offers "
            "Rounded, Pill, Box, Ellipse, Circle, Hexagon, Diamond, Cloud, Chevron, Underline and "
            "Plain, the words kept inside the shape. Ctrl+Z undoes each change."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "mind-map-callouts",
        #: No "votes": one typo from "notes", so "unlink two notes" read as this topic; "vote" matches its plural.
        "keywords": (
            "callout", "callout on a topic", "bubble over a topic", "speech bubble on a map",
            "add a callout", "remove the callout", "labels on a topic", "label a topic",
            "tags on a topic", "labels under a topic", "vote", "voting", "stamp",
            "stamps", "reaction", "thumbs up a topic",
        ),
        "body": (
            "A callout is a few words in a bubble over a topic, as in XMind: a "
            "topic's menu, Topic, Add a callout… writes it; double-click the bubble "
            "to change it, or Remove the callout in the same menu. Add labels… in "
            "the same group writes up to eight short tags, separated by commas, "
            "drawn as a row under the topic's words; double-click the row to "
            "change them. Stamps, in the topic's menu, adds a vote, a heart, a "
            "star, an agree, a question or a hot, each with its count after the "
            "labels; press a stamp on the topic to add one more, and Clear the "
            "stamps takes them off. The map makes room for all three when it is "
            "laid out, and the exports keep them."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-current-layer",
        "keywords": (
            "current layer", "draw on a layer", "draw on this layer", "new things on a layer",
            "active layer", "which layer", "layer new items go on",
        ),
        "body": (
            "The current layer, as in draw.io: in a board's sidebar, Layers, press a "
            "named layer's name and everything new (drawn, typed, pasted, imported "
            "or placed from the library) goes on it; the row is tinted while it is "
            "current. Press the name again, or its ⋯ menu's Stop drawing on it, "
            "for no layer. A hidden or locked layer takes nothing new. Undo brings "
            "a deleted item back on the layer it was on."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-keyboard-create",
        "keywords": (
            "keyboard only board", "make a sticky with the keyboard", "enter on a board",
            "place a text box without a mouse", "edit a sticky with enter", "board without a mouse",
        ),
        "body": (
            "Making and writing on a board without a pointer: press N, T or F to hold "
            "the Sticky note, Text or Frame tool, then Enter to drop one in the middle "
            "of the view (Insert, Sticky note does too). Tab walks the items; Enter on a selected "
            "text box or sticky puts the caret at the end of its words, and Enter on a "
            "selected shape writes in it. Escape leaves the words."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-hand-drawn",
        "keywords": (
            "hand-drawn", "hand drawn", "sketchy", "rough lines", "excalidraw look",
            "sketch style", "drawn by hand", "wobbly lines",
        ),
        "body": (
            "The hand-drawn look, as in Excalidraw: a board's View menu, Hand-drawn "
            "look, draws every shape and connector with rough strokes, the same "
            "each time it is drawn. One shape can differ: its Format panel's Style "
            "tab has Hand-drawn. The pen and the highlighter are drawn as you drew "
            "them, and a mind map keeps its own lines. Exports keep the look."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-tables",
        "keywords": (
            "table", "tables", "add a table", "table on a board", "rows and columns",
            "add a row", "add a column", "delete a row", "delete a column", "grid of cells",
        ),
        "body": (
            "A table on a board, as in draw.io: Insert, Table places three rows of "
            "three cells, the first a header. Double-click a cell to type in it; "
            "Tab and Shift+Tab go to the next and previous cell, Enter keeps the "
            "words, Escape drops them. Right-click the table for Add a row below or "
            "above, Add a column to the right or left, Widen or Narrow this column, "
            "Equal column widths, Delete this row or column (at the cell you "
            "pressed last) and First row as a header. Resize it by its handles; "
            "columns share the width equally until you widen or narrow one."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-mermaid",
        "keywords": (
            "mermaid on a board", "live diagram", "mermaid diagram on the board", "edit a mermaid diagram",
            "flowchart on a board", "diagram object", "pie chart on a board", "gantt on a board",
            "diagram fill", "diagram opacity", "solid diagram boxes",
        ),
        "body": (
            "A live Mermaid diagram on a board: Insert, Mermaid diagram... opens the "
            "source with a preview; Add to board places it at its drawing's shape. "
            "It is any Mermaid diagram (flowchart, sequence, class, state, Gantt, pie "
            "and the rest), drawn as a note draws it and redrawn with the theme. "
            "Select it and the Format panel's Style tab sets its Fill colour, Fill opacity "
            "and Line opacity (0, 25, 50, 75, 100; 100 is a fully solid fill), and the boxes redraw. "
            "Double-click it to change the source; a mistake shows the reason in the "
            "box instead of a picture. Turn into shapes, in the same window, replaces "
            "a flowchart, state, class or sequence diagram with shapes and connectors "
            "you can move one by one (Ctrl+Z puts the diagram back). Insert, Mermaid, "
            "draw.io or board SVG brings a diagram in as shapes straight away."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-edit-data",
        "keywords": (
            "edit data", "custom properties", "properties on a shape", "data on a shape",
            "named values", "metadata on a shape", "shape data", "add a property",
            "placeholder", "placeholders", "%name%", "tooltip", "hover text", "show a value in a label",
        ),
        "body": (
            "Edit data, as in draw.io: select one shape, line, connector, text box, "
            "picture, frame or table and open the Format panel's Data tab (or Edit "
            "data in the command palette). Add a property gives a name and a "
            "value; a name starts with a letter. Changes save as you leave a field, "
            "each one Undo step, and the values stay with the item. Type %name% in a "
            "shape's or connector's words to show that value there (a name it does not "
            "have stays as typed). %date% shows today's date and %page% the title of the "
            "frame the item sits in, unless the item has a value of that name. A shape or connector can take a Tooltip, shown "
            "when the pointer rests on it. Find on the board reads the values too."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-colours",
        "keywords": (
            "border colour", "border color", "fill colour", "fill color", "same colour",
            "same colour as the fill", "match the border", "swap colours", "recent colours",
            "eyedropper", "eye dropper", "pick a colour from the board", "colour picker",
            "change the colour of a shape", "outline colour",
        ),
        "body": (
            "Colours on a board: every colour button (a shape's Fill and Border on its "
            "bar and in the Format panel, text, and the draw colour) opens one menu. "
            "For a shape it names both, Fill and Border, with a dot of each: press "
            "the other to set it instead. Same as fill (or Same as border) makes "
            "them one colour and Swap trades them, each one Undo step. Recent "
            "holds your last eight picks on this device, above the board's colours; "
            "More colours opens any colour by number. Pick from the board is the "
            "eyedropper: the next click takes a colour instead of doing what it "
            "would, from a shape (its fill, or its border with Alt or Take a shape's border), "
            "a line, a text box or any colour button, and Escape stops it. A fill "
            "that is off shows dimmed; picking a colour turns it on."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
])
TOPIC_META.update({
    "board-edit-data": {"title": "Edit data on a board item", "path": "A board's Format panel, Data"},
    "board-colours": {"title": "Fill, border and recent colours on a board", "path": "A shape's bar, Fill or Border"},
    "board-tables": {"title": "Tables on a board", "path": "A board's Insert menu, Table"},
    "board-mermaid": {"title": "Live Mermaid diagrams on a board", "path": "A board's Insert menu, Mermaid diagram..."},
    "board-hand-drawn": {"title": "The hand-drawn look", "path": "A board's View menu, Hand-drawn look"},
    "board-current-layer": {"title": "The current layer", "path": "A board's sidebar, Layers"},
    "board-keyboard-create": {"title": "Making and writing without a mouse", "path": "A board, Keys and controls"},
    "mind-map-structure": {"title": "A structure per branch", "path": "A map topic's menu, Structure"},
    "mind-map-lines": {"title": "Map line style, line ends and topic shapes", "path": "A map, Layout, the line style picker"},
    "mind-map-callouts": {"title": "Callouts, labels and stamps on a topic", "path": "A map topic's menu, Topic"},
})


def _act_topic() -> dict:
    from tessellate.ai import act_registry

    return act_registry.guide_topic()


MORE_TOPICS.append({
    "id": "find-a-place",
    "title": "Finding where something is",
    "keywords": ("can't find", "cant find", "how do i get to", "show me link", "where did it go", "lost a button", "find a setting"),
    "badge": {"label": "Notes", "tab": "notes"},
    "body": (
        "Ask where something is, in Ask or Chat: \"where is the bin\", \"I can't find dark mode\", \"how do I get to backups\". "
        "The answer says where it lives and gives a Show me link that opens it and rings the control, as a row of Tools and "
        "features does. When two places could be meant, each has its own link. Any row of Tools and features, any Settings "
        "section and any tab can be found this way, typos and all."
    ),
})
TOPIC_META["find-a-place"] = {"title": "Finding where something is", "path": "Notes tab, Ask your notebook"}
MORE_TOPICS.append({
    "id": "nicknames",
    "title": "Calling Atlas by any name",
    "keywords": ("nickname", "call you", "call atlas", "your name", "lil bro", "what can i call you"),
    "badge": {"label": "Chat", "tab": "chat"},
    "body": (
        "Call Atlas whatever you like, a nickname or a word you just made up: \"hey lil bro, what's on today\", "
        "\"what's due this week, broski\". The name is taken off before the question is read, so it is never "
        "searched or corrected. A message that is only a name is a call: Atlas answers and offers three things to ask."
    ),
})
TOPIC_META["nicknames"] = {"title": "Calling Atlas by any name", "path": "Chat tab"}
MORE_TOPICS.append(_act_topic())
TOPIC_META["chat-acts"] = {"title": "Things Chat does for you", "path": "Chat tab"}
MORE_TOPICS.append({
    "id": "tasks",
    "title": "Tasks in Chat",
    "keywords": (
        "add a task", "tick off", "complete a task", "cancel a task", "delete a task", "remove a task",
        "snooze a task", "push back a task", "postpone a task", "undo a task", "tasks in chat",
    ),
    "badge": {"label": "Chat", "tab": "chat"},
    "body": (
        "A task is a reminder or an open checklist line (- [ ]) in a note, and Chat handles both from one sentence, with no model. "
        "Add: \"add a task to read chapter 5 tomorrow\" sets a reminder, and asks once for the time if you leave it out. "
        "Complete: \"tick off buy milk\" or \"mark the dentist task as done\" ticks the reminder or the checklist line. "
        "Cancel: \"cancel the dentist task\" or \"remove buy milk from my tasks\" puts a reminder in the bin and takes a "
        "checklist line out of its note. "
        "Snooze: \"snooze the dentist task until Friday\" or \"push buy milk to tomorrow 5pm\" moves a reminder to the new time; "
        "a checklist line has no time, so only reminders can be snoozed. "
        "If more than one task fits the words, Chat asks which one before it changes anything, and a name that fits only in part "
        "is asked about too. Each of these runs at once with Undo on the card, or Ctrl+Z: a ticked task is reopened, a cancelled "
        "one comes back from the bin, a snoozed reminder returns to its old time. Small typos in the sentence are read through."
    ),
})
TOPIC_META["tasks"] = {"title": "Tasks in Chat", "path": "Chat tab"}


#: Autocorrect outside the editor (Brief 94, INBOX 850): autocorrect.js.
MORE_TOPICS.append({
    "id": "autocorrect",
    "keywords": (
        "autocorrect", "auto correct", "autocorrection", "turn off autocorrect",
        "fix my typos", "it changed my word", "undo a correction", "corrected my word",
    ),
    "body": (
        "Autocorrect fixes a clear typo, such as teh, as you finish the "
        "word, in the note boxes, the chat and Ask composers, the reminder boxes and the titles. "
        "The corrected word is underlined for five seconds: rest the pointer on "
        "it or click it for a small menu to keep it, put back what you typed, "
        "or edit the word (a document gets the same underline), "
        "or press Backspace or Ctrl+Z straight after to put it back, and "
        "the toast carries Undo too. A word you put back is left alone for the "
        "rest of the session, and a word in your dictionary never changes. It "
        "never runs in code, links, tags or search boxes. Turn it off in "
        "Settings, General, Writing; a document has its own switch in the "
        "editor's ... menu."
    ),
    "badge": {"label": "General", "section": "general", "target": "pref-autocorrect"},
})
TOPIC_META["autocorrect"] = {"title": "Autocorrect", "path": "Settings, General, Writing", "target": "pref-autocorrect"}


#: The credits (uiset, 2026-10-11): Settings, Help, Credits, drawn from
#: frontend/credits.json, which scripts/build_credits.py writes from THIRD_PARTY.md.
MORE_TOPICS.append({
    "id": "credits",
    "keywords": (
        "credits", "open source", "libraries", "third party", "third-party",
        "attribution", "built with", "what is it built on", "licences", "licenses",
    ),
    "body": (
        "Settings, Help, Credits lists the libraries and data Tessellate is "
        "built on, each with its licence and a link to its source: the ones in "
        "the server, the ones in the app, the optional downloads and the "
        "whiteboard's shapes. Tessellate itself is AGPL-3.0."
    ),
    "badge": {"label": "Help", "section": "help", "target": "credits-fold"},
})
TOPIC_META["credits"] = {"title": "Credits and licences", "path": "Settings, Help, Credits", "target": "credits-fold"}


#: Patterns (INBOX 904 B84, the owner: "Do the patterns ever change?? What's
#: the meaning or use of them?? Can I view them"), with the line that opens.
MORE_TOPICS.append({
    "id": "patterns",
    "keywords": (
        "patterns", "pattern", "what are patterns", "times since", "weeks running", "keeps coming up",
        "patterns line", "do patterns change", "see the patterns",
    ),
    "body": (
        "Patterns are what your notes keep coming back to, counted from the notes "
        "themselves with no AI: a subject that came up again and again (\"university "
        "came up 4 times since 16 July\"), one written about every week, a plan "
        "still open, a decision you went back on, or a busy week. They change as you write, "
        "since each is counted again whenever the dashboard draws. Press the "
        "pattern on the dashboard's line to see the notes behind it; Notes, Tidy "
        "lists every pattern whole. Its ... menu has Confirm, which says it as a "
        "fact from then on, and Not right, which never shows it or anything like "
        "it again. A plan still open also has Done: it removes your Confirm and "
        "never shows that plan again, and a later note that shares the plan's "
        "words does the same on its own."
    ),
    "badge": {"label": "Dashboard", "tab": "dashboard"},
})
#: Slash commands (O6, `ai/slash.py`): written from the registry, so a command
#: added there is in this topic, `/help` and the "/" menu at once.
def _slash_commands_topic() -> dict:
    from tessellate.ai.slash_table import TABLE

    listed = " ".join(f"{usage}: {summary}" for _, usage, summary, _ in TABLE)
    return {
        "id": "slash-commands",
        "keywords": ("slash commands", "slash command", "commands", "exact answers", "chat commands", "type a command", "agent popup commands"),
        "body": (
            "Type a command in the chat box or the Agent popup's box for an exact answer from your notes, with no AI. "
            f"{listed} Typing / opens a menu with a row for each command; one that takes words "
            "fills the box with its name and waits for them. Asking in plain words "
            "(\"which notes have no tags\") runs the same command. /categories and /tags draw "
            "a bar for each, and /recent, /today and /made draw a small timeline of when; a day "
            "with nothing in it says where your notes run and draws that. A note named "
            "in any reply (Chat, Ask, the popup agent, the Guide) previews on hover "
            "or focus, and a reply that gives one to three notes shows each as a "
            "card under it; press a card to open the note."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    }


MORE_TOPICS.append(_slash_commands_topic())
TOPIC_META["slash-commands"] = {"title": "Slash commands", "path": "Chat tab, type / in the box, Commands"}


TOPIC_META["patterns"] = {"title": "Patterns", "path": "The dashboard's line under the greeting, and Notes, Tidy"}


#: INBOX 1352: the quick sketch pad rebuilt as a paint pad (sketch-pad.js).
MORE_TOPICS.append({
    "id": "quick-sketch",
    "keywords": (
        "quick sketch", "sketch pad", "draw a picture", "paint", "drawing tools" "remove a recent colour", "delete a custom colour",
        "brush", "pencil", "eraser", "highlighter", "bucket fill", "paint bucket",
        "eyedropper", "colour picker", "draw a rectangle", "draw a circle",
        "polygon", "annotate a picture", "draw on a picture", "download png",
    ),
    "body": (
        "Quick sketch (q, Ctrl+Shift+K, or Sketch on the dashboard) is a paint "
        "pad. The tools are down the left, each with a letter: S select, P "
        "pencil, B brush, H highlighter, E eraser, L line, A arrow, R "
        "rectangle, O ellipse, G polygon, T text, F fill, I colour picker. A "
        "shape is drawn corner to corner; Shift makes it a square or circle "
        "and snaps a line to 45 degrees, Alt draws it from the centre, and "
        "Escape cancels it; with the Text tool Escape places the text. The "
        "bar holds the ink and fill colours (X swaps them), the palette and "
        "a custom colour (the last six you picked show as recent colours; "
        "the small x on one, or Delete on it, takes it off, with an Undo; the plus saves the current colour again), the size ([ and ] change it; for Text it is the "
        "text size), outline, fill or both for shapes, Undo, Redo (Ctrl+Shift+Z "
        "or Ctrl+Y), Clear and a More menu (a picture under the ink, the paper "
        "colour). On a narrow window the palette, size and style are under "
        "Colour, size and style. Ctrl and the wheel zoom, 0 fits the page. "
        "Save as note adds the sketch to a new note once something is drawn; "
        "Download PNG saves the picture; a picture's Annotate opens it here."
    ),
    "badge": {"label": "Notes", "tab": "notes"},
})
TOPIC_META["quick-sketch"] = {"title": "Quick sketch", "path": "Notes, the sketch button; q or Ctrl+Shift+K anywhere"}


#: DOCUMENTS_PLAN 16: the guided equation editor (math-editor.js).
MORE_TOPICS.append({
    "id": "equation-editor",
    "keywords": (
        "equation", "equations", "equation editor", "write an equation",
        "maths", "math", "formula", "fraction", "square root", "greek letter",
        "symbol", "integral", "matrix", "latex", "tex", "alt+=", "alt equals",
    ),
    "body": (
        "The equation editor opens from /equation in a note, a document, a "
        "board's text or the Chat box, from a document's Insert menu, or with "
        "Alt+= there and in the Ask box (the same as Word's Alt+=); Ctrl+K, "
        "Equation opens it over the box you were in, and the shortcuts list "
        "has it under Tools. The equation is drawn as it will read, with "
        "dotted boxes where things go: click a box to fill it, Tab goes to the "
        "next one and the arrows move through the equation. Type it plainly: "
        "a/b makes a fraction, ^ and _ a power or a subscript, and LaTeX such "
        "as \\frac or \\alpha turns into the symbol as you type it. The "
        "palette inserts the structures Word offers (fraction, script, "
        "radical, integral, large operator, bracket, function, accent, limit "
        "and log, operator, matrix) and Greek, operators, relations, arrows, "
        "sets and calculus symbols; a selection goes into the first box. The "
        "LaTeX button shows the same equation as raw TeX to edit directly, and "
        "the two stay in step. A drawn equation in a note or a document is "
        "edited where it stands: click it, Enter or a click outside keeps the "
        "change as one undo step, Escape leaves it as it was. Inline sits in "
        "the sentence, Display on its own line; Ctrl+Enter inserts. It writes "
        "TeX between dollar signs, so the note stays plain text. On a touch "
        "screen the field offers its own keyboard."
    ),
    "badge": {"label": "Library", "tab": "library"},
})
TOPIC_META["equation-editor"] = {"title": "Equation editor", "path": "Type /equation, or Alt+=, in a note, a document, a board's text or Chat"}
