# uifix-1109: what is left

- INBOX 1712 (not fixed, not reproduced): "why do some of these extend so far to the right??". Measured the Chat tab Sources grid (answer-kit.js:2408, 02-chat-graph.css:4381), the popup agent's rows (palette.js `cmdSourceRow`, 02-chat-graph.css:4322) and the Ask tab's records with wide pictures: all equal width. Next: the owner's window width and which surface; if it is the grid, a 4-column grid at 1920 puts cards 280 px apart (274 px floor), which may be the "300 px further right".
- Pre-existing red on the base: tests/test_frontend_wake_sources.py (documents-callouts.js raf 0 to 1, documents.js raf 13 to 12; from the merged callouts split, not this branch). The seed needs its own commit.
- Port 8797 was taken by another server; measured on 8799.
- Not verified: List bar at a wider-than-224 px list (the list is tight at 1100, 1440 and 1920 alike; a dragged-wider divider was not tried).
