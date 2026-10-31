# capture-1031 (INBOX 1479): the Notes tab's capture bar and card

Branch agent/capture-1031, port 8834, data /tmp/claude-0/capture-data.

Decisions (mine, in the brief's spirit): the bar sits above `#entry-list` in the
Notes tab (the reference's place); the Capture sub-tab and the quick note dialog
stay as they are. The card is the lazy `frontend/js/capture-card.js` and
`frontend/css/capture-card-lazy.css`, fetched on the bar's first focus, click or
input (`notes-list.js`, after the view toggle listeners). Per-note colour did
not exist (only category colour): step 3 adds `Entry.colour`.

Steps: 1 bar and card (Note mode), 2 To-do mode, 3 colour dots, tags, bell, 4 picture and Draw.

- done: step 1 (see git log). next: step 2, `capture-card.js` mode seg and checklist rows.
