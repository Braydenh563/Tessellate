# wbpaste-1026 (WHITEBOARD_PLAN 1356): built

- Done: paste options chip, Paste special, Paste into the shape's text, Paste without comments, pasted pictures fitted to the view, map chip (one topic), shared text readings (documents-prose.js PASTE-CORE block). Sweep `scratchpad/ui-sweeps/wbpaste.js` 21/21 at 1440x900 and 720x900.
- Next: nothing open for 1356. Paste without comments is now tested against commented copies (wb4-1026; wbpaste.js 25/25).
- Not verified: real OS clipboard (sweep dispatches ClipboardEvents and uses the headless clipboard API); a real spreadsheet copy; touch.
- Found-not-fixed: app.js gzip cap (14,300) has no room for one more script line, so the shared helpers and the board paste code sit inside documents-prose.js and whiteboard-commands.js instead of their own files; a split needs the cap to come down elsewhere first.
