# review-1108: diagram fixes (180d1929) and in-app boop, open findings

Dispatch after perfdgm-1108 (diagram files) and perfbuddy-1108 (avatars.js) land.
Desk-side findings went to deskfix-1108; composer findings to r3fix-1108.

Diagram:
- HIGH `diagram-kinds.js:1041` reads `diagramModel.bar.historyKey`, but `diagramBar` loads only for flowcharts (`diagram-builder.js:660`): a sequence `.mmd` opened first throws on every keydown and Ctrl+Z reaches the app undo.
- MED `diagram-embed.js:481-486`: the window's Ctrl+Z listener does not stop the event; with focus on Picture, List, Source, Done, Cancel or "?" (outside the builder pane) Ctrl+Z runs the builder undo and then the app undo (`settings-wiring.js:644`).
- MED `diagram-outline.js:56,66`: Keep is remembered per host element; documents share `#doc-preview` (`documents.js:4134`), so one Keep turns the tall-chart offer off for every diagram document. Key it by diagram.
- MED `diagram-ops.js:181`: the automatic "no" applies to every `join` caller: re-pointing an unlabelled branch (`diagram-edge-pick.js:53`, which promises to keep the words) and template or suggested edges (`diagram-suggest.js:56`) get "no". Limit it to a new second branch of a decision whose first label is yes (case and punctuation folded). `test_diagram_r6` is still named "asks for its words" while asserting the second branch is not asked; rename and add a test that a non-yes first label still asks.
- LOW Guide `diagram-blocks` lost "1 to 7 the other shapes, Shift+N the last one" and "K colours" (`help_topics_more.py:3291`) without a note: restore within the 1900 budget or move behind data-help-for.
- LOW `mermaid-draw.js:576`: a click anywhere on an embedded picture opens the diagram; check it does not stop caret placement in the Live editor.
- LOW a text field inside the diagram window: Ctrl+Z goes to the window's listener and cancels the browser's text undo; the comment says otherwise.

In-app companion:
- **FIXED buddyrev-1108** HIGH `avatars.js:10539,10547`: a click on the nose zone is a boop (once per 3 s) and replaces the click reaction (wake, pout, spin). A boop should be a quick tap that is not a click the user meant as a click, or add to the click reaction rather than replace it.
