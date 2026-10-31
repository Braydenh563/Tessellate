# capture-1031 (INBOX 1479): the Notes tab's capture bar and card

Branch agent/capture-1031, port 8834, data /tmp/claude-0/capture-data.

Decisions (mine, in the brief's spirit): the bar sits above `#entry-list` in the
Notes tab (the reference's place); the Capture sub-tab and the quick note dialog
stay as they are. The card is the lazy `frontend/js/capture-card.js` and
`frontend/css/capture-card-lazy.css`, fetched on the bar's first focus, click or
input (`notes-list.js`, after the view toggle listeners). Per-note colour did
not exist (only category colour): step 3 adds `Entry.colour`.

Steps: 1 bar and card (Note mode), 2 To-do mode, 3 colour dots, tags, bell, 4 picture and Draw.

- done: step 1 fea3105; steps 2 to 4 in one commit (the gate failed the first
  staged run on five ratchets, fixed: `--swatch` instead of a new token, no new
  `typeof` guards or top-level lets, boot CSS cap +200, assert shapes).
  Draw opens the sketch pad over the card (host `saveLabel`, "Add to note")
  rather than a canvas inside the card: the pad is thirteen tools and a rail.
  Pictures are not in the draft (files cannot be kept), Close keeps them in
  memory until reload.
- next (found, not built): a Colour item in a note card's menu (a saved note's
  colour cannot be changed; the API takes it on `PUT /entries/{id}`); Draw as a
  canvas inside the card at 1440 only; real-model tag suggestions unverified.
