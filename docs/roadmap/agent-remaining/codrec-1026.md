# codrec-1026: code editor and recordings dogfood (INBOX 1400)

Driven with Playwright at 1440x900 and 390x844, light and dark, server on :8802 with no model and no Voice notes add-on. Scripts live in the session scratch dir, not the repo. Not pushed.

## Done (by class)

- Prose chords in a code file (56e59a7): Ctrl+B, I, E, U, 1 to 3, Ctrl+Shift+7/8/9 and S wrote markdown into Python or SQL (`**name = "abc"**`); they now decline for a file with no rendered form (`docProseChord`). The slash and `[[` menus no longer open over a code file (`editorHandleInput`): a `//` comment at a line start raised Heading 1.
- Recordings library (67d7afb): the search box read names only; the server now reads names and transcripts (`GET /recordings?q=`, LIKE-escaped, JSON-quote aware), each hit shows its line with the time and plays from there. Transcribe was missing from the menu until the recorder had run once in a session (`voiceStatus` is fetched by the recorder alone), and with no add-on there was no row to say why; it is always there and says what to install.
- Code on a phone (bdc72c0): the bar at the foot held Bold, Italic, Heading and a "/" for a Python file; it now holds Tab, Outdent, Undo, Redo and 13 symbols (17 keys, 44px, scrolls sideways, keeps the editor focus). Ctrl+G goes to a line in a code file (was find next). Download as .html of a code file saved an empty page named `apppy.html`: it now saves the source named `app.py.html`; the image bundle, Word and heading-map rows are out of a code file's menu.
- Print or save as PDF on a code file says it is for writing (it printed a blank sheet; the print path reads the rendered preview a code file does not have) and Download audio is in a recording's menu (6cff7c7). The word-count goal button is out of a code file.

## Measured, fine

- Silent-click audit (every visible button, 450 ms, mutation/toast/url/focus): 0 silent in reminders (20 buttons, 1440 and 11 at 390), Library media (6), docs (60), skills (90), links (5), notes (15), dashboard (15), chat (28), documents (37).
- Code editor: line numbers, Ctrl+/, Alt+Up/Down and Shift+Alt+Down line moves, bracket auto-close, find, language picker (persisted after reload), Format (JS, HTML, JSON error message), Run for JS and HTML (output in `#doc-panel-output`), Python Run disabled with a reason and a link to Packages, Assistant with no model says what needs one, autocorrect leaves code alone. 0 console errors.
- Recorder: record, pause (state and status text change; the clock freeze itself was not measured, wrong element id), resume, stop at 1440 and 390 dark; targets 44 at 390; card has speed, scrub (arrows step 5 s), marks, rename, delete with Undo, trim.
- OCR workspace (`ocrflow.js` MODE=missing): all pass, says what is missing and offers the install.

## Remaining

- Done in the second pass (see `git log`): the code status bar (lines, characters, language), the Assistant's empty Ask (field flagged, hint under it), a code file's print (listing with line numbers; Ctrl+P and the menu row), the recording waveform (64px, 48px on a phone).
- Not driven: the Assistant hint on a phone's sheet, a print in a real browser dialog (measured with `emulateMedia` print and `page.pdf`), a print of a file with very long unbroken lines, note templates beyond the silent-click audit, attachments, OCR with an engine present (`MODE=present`), real transcription (no add-on in this sandbox), real microphone and real touch.
