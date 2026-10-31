# polish5-1031 (agent/polish5-1031): remaining

Port 8813 was taken by the dupfetch agent's server, so this branch measured on 8825.

Done:
- step 1: back-to-top above the floating New button (navigation.js `aboveDockFab`), board picker face two lines on a phone (library-lazy.css), review fixes (a) `wbFrameSpilledMap` and (b) `resetShortcuts` waits for the reveal module.
- step 2: documents seeded under an active search (library.js `seedLibraryDocsAll`). Library list hints and Move order measured on docs, boards and media at 1440 and 390: hint shown, Move up and Move down are rows 0 and 1, no fix needed.
- next: wbopen, labels (nothing in scope left).

Skipped by the coordinator: objmove L2, L3, anything in obj-*.js or kebabMenu (a new agent owns Library picture-card drag and row menus).

Left, from mapphone-1031:
- The Map chip is hidden below 600 (07-whiteboard-misc.css `#wb-map-chip`); putting the kind into the picker face as an icon is a design call.

Left, from labels-1031 and blindux-1031 (not built, one line each):
- Filter stays the word on both menus (tests/test_ui_recipes.py, INBOX 813): a decision.
- `/ask-history/stats` fetched twice at boot: the dupfetch agent's.
- Notes sub-tab reopens on Your notes (navigation.js `showNotesSection`), Notes tab drops you on the list, `#notes-tidy` icon-only (a width decision), 'travel' chip, 'Mentions Jun 14', 'Open' for two states: design calls.
- Drag reorder on Boards and Media: obj-*.js, the new agent's. Library list hints measured here, fine.
- Not verified: a model-filed note's 'Go to it' beside Write another (needs a model); the notifications list with a real model.

Left, from wbopen-1031 (none cheap; all L, a decision, or not verifiable here): 807 merged cells (whiteboard-format.js:1491), 819 New split button (decide the one-press default; index.html at its byte cap), 855 document comments in the board's thread shape (documents.js `renderDocComments`), 856 voice strings (112 files), 858 hover frame at 2,000 notes (needs an idle machine), 860 owner hardware.
Found: the two base failures wbopen and blindux noted (test_guide_social_1414 closing, test_scratchpad_size) pass on this head.
Server on 8825 (pid via `pgrep -f '[u]vicorn.*--port 8825'`) is still up; kill it by PID.
