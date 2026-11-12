"""The Guide's reference, part two, middle: every feature since 0.3.0.

Moved out of `help_topics_more.py` whole (audit 1028 K24, 3,941 lines there; a
pure move, text and order unchanged). `help_topics_more.MORE_TOPICS` extends
itself with `MID_TOPICS` at the point this block used to sit, so the Guide's
order is the one it always had. Data only: no imports, no behaviour.
"""

from __future__ import annotations

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
MID_TOPICS: list[dict] = []
MID_TOPICS.extend(
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
                "opens with becomes a [[link]], and File in names the category a save files it "
                "in, with its reason beside it (on a close call, two or three File in choices "
                "and why it waits; what you save then says the same). Nothing is offered on quoted words: text in quotation "
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
                "time; Open in Capture moves them to the full composer. Private, in "
                "Quick note, Capture and the card's foot, seals just that one note (it starts "
                "on when Settings says new notes start private). The "
                "dashboard's Quick capture card is the same take-a-note bar as the top of "
                "the Notes tab: it opens in place into a title, the note or a to-do "
                "list, tags and a colour, with Draw and pictures, keeps your words as "
                "a draft, and saves the same way. A bare link pasted "
                "into Capture or Quick note offers its page as a note through the "
                "web clipper, only while web search is allowed. \"Clear\" (the eraser "
                "icon) is in every box you type into: Capture (as Clear all, with its title, tags "
                "and files; its title and its note also have an x of their own, which clears just that one), Quick note, Ask, Chat and the popup agent. It shows only "
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
            "id": "chat-list",
            "keywords": (
                "search chats", "search my chats", "find a chat", "find an old chat", "old chats",
                "saved chats", "chat list", "chats list", "chat sidebar", "sort chats", "pin a chat",
            ),
            "body": (
                "The Chats list beside the chat shows your last eight saved chats. "
                "The search box above it finds a chat by its title or by anything "
                "said in it and lists up to 32 matches. Sort "
                "puts them Recent, Most turns, Most tokens or A to Z, and a pinned "
                "chat stays first. Each chat's menu renames, pins, archives or "
                "deletes it. All in Library opens every chat, with the full search."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "queued-messages",
            "keywords": (
                "queue a message", "queued messages", "type while it answers", "type while it is answering",
                "send while generating", "edit a queued message", "remove a queued message",
                "cant type while it answers", "message waiting", "the box is locked",
            ),
            "body": (
                "In Chat, the popup agent and the Guide the box stays open while a "
                "reply is being written. Press Enter and what you typed waits in a "
                "list by the box; each one goes, oldest first, when the reply before "
                "it ends. Edit puts a waiting message back in the box, and the x "
                "removes it. Stop ends the reply and keeps the list: nothing sends by "
                "itself, so press Send to run the waiting messages in order, with "
                "what you typed last. What you are typing stays in the box while "
                "the list sends."
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
                "returns to the card. The Attach panel's Files tab lists both files "
                "you uploaded in the Library and files attached to notes, and "
                "anything you drag in from the tray is already ticked there; "
                "untick a row to take it off."
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
                "only into a category you have, not by a stray word, and says "
                "why (It mentions squat (Fitness), like the 9 notes in Gym). Unsure, "
                "it stays in Uncategorised with the closest two or three, and New: "
                "Fitness when none fits. Health, money and family notes wait unless File "
                "health, money and family notes by their words too is on in "
                "Settings, Background tasks. While a "
                "note shows Filing, its chip offers File by meaning now, Leave it "
                "where it is and File it myself, and Stop in Settings, Background "
                "tasks files every waiting note by meaning. A note you file "
                "yourself is never moved by a late answer, and moving notes by "
                "hand teaches the filing where things go. Filings Atlas was "
                "unsure of wait in is:review, with Accept the filing on the "
                "note's menu. More switches: Filing settings."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "filing-settings",
            "keywords": (
                "ask when unsure", "ask me when filing is not sure", "filing options",
                "filing options menu", "unsure filing", "wait for me to choose",
                "load the search model", "search model at launch", "filing style",
                "filing settings",
            ),
            "body": (
                "Filing's switches, in Settings, Background tasks. Ask me when "
                "filing is not sure (off by default; also the Filing options "
                "menu beside Filing on the Capture tab) keeps a filing under 70% "
                "from being applied: the note waits in Uncategorised and offers "
                "the closest two or three to pick from, in the Capture hint and "
                "on the saved note. Load the search model when the app starts "
                "chooses when filing by meaning gets ready: at launch, or on "
                "the first note, which then waits a few seconds. Let the search "
                "model go after an idle hour frees its memory when nothing has "
                "been searched or filed for an hour; the next search loads it "
                "again. Filing style files by topic, by project or by time."
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
                "card as a chip of two halves: \"+ tag\" adds the tag, and the x half (Dismiss) "
                "stops suggesting it (Undo in the notice brings it back, and the note's "
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
                "most used", "note order", "f2", "edit a note", "edit note", "change a note", "open a note", "write in a note",
            ),
            "body": (
                "Sort notes: Newest first, Oldest first, Recently edited, A to Z "
                "(\"note 2\" before \"note 10\"), Most used or Forgotten first; "
                "the choice is remembered. A note's menu has Copy wiki link to "
                "paste a [[link]] to it into another note, and Copy app link for "
                "an address that opens it in the app. To edit a note, press the pencil on its row (or F2 on a focused note), change it in place, then Save. Editing a note has the title, "
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
                "what a card shows", "create a linked note", "link mode", "headings", "outline of a note", "jump to a heading",
            ),
            "body": (
                "A table or a code block is drawn the "
                "way a document draws it, with its Copy button, and a code block "
                "that names its language is coloured; a search does not "
                "mark words inside one. A picture from the web is not loaded, "
                "because this notebook works offline: the card says so and links "
                "to it, to open in a new tab. A [[link]] to a note that does not "
                "exist has a Create chip beside it, which offers to make the note "
                "or a document of that name. Esc leaves link mode (Link to "
                "another) and takes its notice down. A note with three or more "
                "headings has a Headings row in its ... menu: pick one and the card "
                "opens out and scrolls to it."
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
                "inserts a saved bookmark as a link. The ... menu's Import "
                "bookmarks file adds the links of a file your browser exported, "
                "folders as groups, skipping ones already saved, with Undo; "
                "Export bookmarks saves them all as a file a browser can import. "
                "A link can carry tags (commas, in the Add form or Edit): each tag is a chip "
                "that filters across groups, search finds them, and the file keeps them."
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
                "sketches, the note's numbered chip under Cites (the row under the answer) has up to "
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
                "open in a new tab", "picture details", "copy an image", "copy image",
                "copy a picture", "save a picture",
            ),
            "body": (
                "A picture or file opens in the viewer. The bar at the top names "
                "it and says where you are (2 of 5), with Copy text when it has "
                "a reading, Download, Open in a new tab, Details (the size, the "
                "caption and the text read off it, shown or hidden), the '?' "
                "and the ⋯ (rename, delete, see the text on the page). The bar at "
                "the foot zooms: out, in, back to fit, 1:1 for actual size, and "
                "Rotate; the percentage between out and in is a field: type 150 and Enter, "
                "or open its arrow for 25 to 400 and Fit. A PDF adds its page stepper, and its 'Page 3 of 12' "
                "is a field too: type 7 and Enter to jump to page 7, or open its arrow for a list of pages. "
                "On a trackpad, pinch to zoom. With more than one file a "
                "filmstrip above it jumps to any of them. Scroll zooms where the "
                "pointer is, drag moves a zoomed picture, double-click switches "
                "between fit and actual size. Keys: Left and Right, plus and "
                "minus, 0, 1, R, I, Ctrl+C (copy the picture), Escape. Right-click a picture here, "
                "in the Library, in the chat, in a note or on a staged file (hold it on a phone) for Copy image and "
                "Save image; if the browser will not copy a picture, its link is copied. On a phone, swipe and pinch. The bars "
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
                    " a topic with how many notes and over which months (You have eleven notes about uni, and they follow one"
                    " semester, July to early November). Three or more dated notes then read as a few short paragraphs, notes that go together in one sentence, and one"
                    " closing insight (your slang is quoted, a finish congratulated). One source mark lights its note. "
                    "It says what "
                    "the notes do not cover yet (Nothing yet on due dates), how alone or stale a fact is "
                    "(Nothing on bench since September), and can end with one offer you press (a reminder, a "
                    "checklist or a note, with Undo); next week is said as the day it meant. A count leads "
                    "with its figure, a person is a card, a comparison a table, what is left a checklist; "
                    "a short list past five lines, Show more. The ... by Copy keeps it as a note, a document or a mind "
                    "map. Asked what it can do (can you search the web?), it says whether and how; it never "
                    "searches. Tell me more, or the second one, follows on from the answer before. The Chat "
                    "tab answers the same way whenever no model is running: its box stays open, and Agent "
                    "mode is greyed unless the Needle extra can run it (the app's own tools go first). Every "
                    "sentence cites a note; the app adds only joining words and what it measured, and says "
                    "which of your words no note held. The badge by the name says who "
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
                "the answer takes the newer and offers one chip for the other. A "
                "question the answer itself suggests (ask me \"...\") joins "
                "them as a button that asks it."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "why-this-answer",
            "keywords": (
                "why this answer", "how was this answered", "how did you get that",
                "where did this answer come from", "which model answered",
                "how long did it take", "what did it search", "explain the answer",
                "transparent", "process lines", "chips under the answer", "answer foot",
            ),
            "body": (
                "Under an answer in Ask, in a Chat reply and in the popup agent's "
                "answer is one row of quiet text buttons, each with a caret that "
                "turns down when open (Sources, Cites, how many sentences "
                "your notes back, Why this answer); the filled chips after "
                "Next: are questions to ask. In Chat and the popup agent "
                "the time ends it, the model being named in the answer's head, "
                "where Copy and the reply's other actions sit at the end. "
                "Each chip opens its part below, one at a time. "
                "Why this answer opens the lines that "
                "made it, each with the seconds since you asked: what the "
                "question was read as, what was searched and how many notes "
                "matched, who wrote it (Atlas from your notes with no model, "
                "or the model by name, and whether it was handed the app's "
                "own answer as a fact), the shape it took, how many of the "
                "matching notes it cites, and how long it took. "
                "Beside an Ask answer, each Matching records card is the "
                "note's title, two lines of it (Show more for the rest), one "
                "line of its category, date and match percentage, the reason "
                "it was found, and N links, which opens the notes it links to."
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
            #: Audit 1028 E59, E60, E62: the three per-answer ways to say "not that".
            "id": "answer-menu",
            "keywords": (
                "regenerate", "regenerate as", "retry an answer", "answer again", "another persona",
                "wrong answer", "this answer is wrong", "mark an answer wrong", "thumbs down", "read more notes", "edit your question", "keep the earlier version", "edit and resend",
            ),
            "body": (
                "An answer's menu (the three dots under it) has three ways to ask for a "
                "better one. Regenerate from here asks the question again; each retry "
                "reads more notes (5, then 10, 15, up to 20) and ignores a category the "
                "question named, so a note the first read missed can come in. Regenerate "
                "as lists your personas: the same question answered as one of them, for "
                "this answer only, and the persona picker stays as it was. This answer "
                "is wrong marks the whole answer wrong: the notes it cited come last for a "
                "question like it, and are left out once you say so twice. It shows "
                "only where the answer cites a note, never in a private chat, and Undo "
                "takes it back. Editing your own question clears the replies after "
                "it; in a saved chat with later replies, Keep the earlier version as "
                "a copy (on by default) first saves the whole chat as a copy named "
                "after it, \"before the edit\"."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "library-skills",
            "keywords": (
                "ai skills", "built-in skill", "built in skill", "copy a skill",
                "duplicate a skill", "my skills", "skill list", "reads only",
                "changes notes", "last run of a skill", "undo a skill run", "undo the run",
            ),
            "body": (
                "Library, Skills lists every skill: the filter beside the "
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
                "corrected numbers and the memory free now. One button downloads it (it waits until Ollama is "
                "installed and running; the cards show what fits either way) or puts it to "
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
                "Appearance (which closes Settings and leaves the panel). The tab row "
                "under its head (a glyph on each tab, and a count on Theme) jumps to "
                "Theme, Colour, Text, Layout, Background art "
                "or Motion, and the panel opens on the last one you used. Peek, in "
                "the head, fades "
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
                "Documents, Boards and maps, Images and Files. Take the grip at a card's left "
                "edge, or press and hold the card still, then move; a dashed gap shows where it lands, "
                "and moving at once selects its text (press those words and hold to retry). "
                "A picture needs no wait, "
                "and on a phone you hold a card until it lifts, then move it. The sort then reads "
                "Custom order. Drop it where it started, or press Escape, and nothing "
                "changes. The toast has Undo. In Custom order a line above the list and the "
                "card's menu say how to move a card. "
                "From the keyboard, focus a card and press "
                "Alt+Up or Alt+Down to move it one place, or choose Move up or Move "
                "down in its menu (on a phone too). To copy a card, focus it and "
                "press Ctrl+C (Cmd+C on a Mac), or choose Copy card in its menu: a toast "
                "names it. Ctrl+V then attaches it in the chat box, puts a card on an "
                "open whiteboard, or writes its link in a note or a document, or its "
                "title in a reminder. You can also carry a card: press and hold, then drag it "
                "onto the chat box, an open note or document, a whiteboard, the "
                "reminder box or the tray, which outline when they take it; "
                "rest on a page tab for half a second to open it without "
                "letting go. Drop a note on a category or, once the space switcher opens, on a "
                "space, to file it (with Undo). "
                "Chat sources and diagrams carry too (a diagram writes ![[Title]]). "
                "The tray in the status bar holds cards across pages: "
                "drop one on it (held over, it opens) "
                "or choose Add to tray, then drag cards out or click "
                "one to paste it where you were typing, or attach it to the chat. "
                "In a long card menu a row "
                "with an arrow (Text and description on a picture, Copy and arrange "
                "on a board) opens a list beside it: rest the pointer on it, click it, "
                "or press Right arrow or Enter; Left arrow or Escape goes back. On a "
                "phone it opens as a page of the menu with a back row."
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
                "remember panel position", "remember panel size", "panel position",
                "forget panel position",
            ),
            "body": (
                "On a computer with a mouse, any panel "
                "with a title row (the agent, Find anything, Statistics, Settings "
                "and the rest) can sit where you want it: drag its head to move it "
                "and drag any edge or corner to resize it from that side. "
                "The head always stays on screen, and the content scrolls inside "
                "when the panel is small. A moved panel drops the dark backdrop so "
                "you can see what is beside it. Each panel remembers its place and size "
                "on this computer; Settings, Appearance, Panels open where you left "
                "them, is the switch (off, every panel opens in the middle), and "
                "the arrow button in a head names it. That button (Put back in "
                "the middle), a double-click on the head or Home puts a panel back. A "
                "double-click on the corner mark puts only the size back. A saved "
                "place that no longer fits opens in the middle. "
                "Drag the head to a screen edge to dock it: a faint outline shows "
                "the zone, and letting go fills it (the left or right half, the "
                "bottom half, a quarter at a bottom corner or the top left and "
                "right, or the whole window at the top middle). A panel docked to "
                "the left or right half also moves the app aside, so the page "
                "fills the space beside it; the columns button in the panel's "
                "head, or Settings, Appearance, Move the app aside for a docked "
                "panel, turns that off (a corner dock and a panel with room "
                "short of 640 pixels beside it never move the app). A head reads: "
                "its buttons, help, more, minimise, Close. The minus "
                "button beside Close (or Shift and Escape) minimises a panel: it "
                "keeps what you typed and waits as a small pill above the chat box "
                "(or the status bar), bottom left; the pill brings it back and its "
                "x closes it. From the "
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
                "The app works at 200% and 400% browser zoom: on a "
                "short window Chat flows as a page, and sub-tab strips scroll with "
                "the page so a focused control stays in view. Settings, Keyboard "
                "shortcuts has Single-key shortcuts: turn it off so speech input "
                "or a stray key cannot set off m, / or ? and the other keys with "
                "no Ctrl or Alt. A toast steps aside, fading and letting clicks "
                "through, while the focused control is under it. For a screen "
                "reader every tab has one main landmark, editors and panels have "
                "names, and resize grips say how wide a panel is. After Notes or "
                "the Library loads or you filter it, one polite line says how "
                "many are shown, and the window title follows the view. Settings, "
                "Appearance has High contrast, Motion, Interface animations, "
                "Text size and Zoom. Every slider's number is a field: Tab to it, "
                "type a value, Enter applies it, Esc puts it back, and the arrow "
                "keys step it (Shift for ten)."
            ),
            "badge": {"label": "Appearance", "section": "appearance"},
        },
        {
            "id": "mind-map-study",
            "keywords": (
                "study the map", "study mode", "revise", "revision", "recall",
                "flashcards", "quiz me on my map", "test myself", "memorise",
                "build up branch by branch", "reveal a map step by step", "present a map from the centre",
            ),
            "body": (
                "On a mind map, the board menu's Study the map "
                "goes full screen and asks one branch at a time: what is under "
                "it is hidden until you press Show (or Enter), then Knew it or "
                "Not yet marks it and moves on. Branches with topics under "
                "them are asked, and then each topic that has a note: its note is the "
                "answer, read out in the bar when you press Show. Nothing on the map changes. Your marks are kept "
                "for that map on this device, and the next run is spaced: what you missed first, then what is due "
                "again (a day, 3, a week, 2, a month), then new ones; the palette's Study the map in map order "
                "asks in the map's order. The end says how many you recalled. Esc stops. "
                "Build up branch by branch shows the centre, then each branch a level at a time; Previous takes the last part away, End shows the whole map to take it apart; the map is not changed."
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
                "Right-click a card, sticky, shape or "
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
                "A sticky (N, or the note "
                "on the tool dock) is paper: its colour, a lift, and a folded "
                "corner. A text box (T) is words on the board, with no fill and a "
                "faint dashed edge. Select a sticky and its bar starts with a Paper "
                "button that drops down seven papers (yellow, orange, pink, purple, blue, green, grey); any other "
                "colour, and a text box's own fill or edge, are under the bar's ... "
                "menu, Box. The folded corner can be switched off for one note (Format "
                "panel, Folded corner) or as the board's default (View, Folded sticky "
                "corners). The Format panel's Fill opacity (0, 25, 50, 75, 100) makes a "
                "sticky's or text box's fill solid or see-through. Each change is one Undo step. Typing in either, / offers "
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
                "symbol", "symbols", "insert a symbol", "special characters", "greek letters", "arrows",
            ),
            "body": (
                "One picker holds every Phosphor icon the app ships "
                "and about 470 emoji: Emoji or Icons in the tab strip under its title, "
                "type to search, Recent first, arrows and Enter to choose, Escape to close. "
                "The last Emoji group is Japanese emoticons (kaomoji such as a shrug or a table flip), "
                "found by name or by words like happy, cry and angry. On a board or a "
                "map, the smiley on the tool dock (Add on a board, Map on a map) or Insert, "
                "Emoji and icons… keeps it open: press one to place it "
                "in the middle of the view, or drag it where it goes. An emoji lands "
                "as a sticker (no card, resize it like any item), an icon as a shape "
                "you can recolour (select one with copies, then Insert, Emoji and icons, "
                "Match all copies, makes every copy look like it; Swap everywhere changes an icon or an emoji in every place); dropped on a map topic, either becomes that "
                "topic's icon. Each is one Undo step. In a note or a document, the "
                "smiley in a note's formatting toolbar, the Insert button or "
                "Emoji or icon in the / menu puts one at the caret: an emoji as "
                "itself, an icon as :ph-name:, which reading, Live and an HTML "
                "export show as the icon (a name the icon font lacks stays text). "
                "Symbols is a third tab for characters a keyboard lacks: arrows, "
                "maths, Greek letters, currency, writing marks and key caps, each "
                "inserted as the character itself. Every panel has its own doors: "
                "a document's Insert menu (the same list as /) has Emoji or icon, Symbol, Equation and "
                "Calculator; Ctrl+K lists Emoji, Icons, Symbols and the calculator "
                "over any text box (with none, a pick is copied); the chords, in "
                "a document and in every note box, are Ctrl+; for emoji, "
                "Ctrl+Shift+; for icons, Ctrl+' for symbols, Alt+= for an equation "
                "and Ctrl+Shift+' for the calculator, all in the document's "
                "shortcut sheet; the note editor's strip has Emoji or icon, Symbol "
                "and Equation. Each opens the same movable panel, which comes up "
                "where it will stay."
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
                "A map draws as a hierarchy: the centre "
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
                "your recent ones first; an emoji or an icon, one per topic. How this map looks, Colour every level, "
                "gives each depth its own colour, and Show a legend draws the branch colours and the markers in use. Save this look there names a map's whole look to apply to another map. In a topic's text, bold, italic, code, an equation and a link written in Markdown draw as such; Ctrl+click opens a link."
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
                "a page, and a CSV or TSV as a read-only table (Run, the first 500 rows); Live in the panel refreshes it as you type (the panel's buttons are icons: point at one for its name). A file of "
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
