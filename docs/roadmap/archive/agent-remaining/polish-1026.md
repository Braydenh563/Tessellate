# polish-1026 (agent/polish-1026)

Done
- Shell items (OPEN.md, 22-10 bug doc, Shell) re-measured at six widths: notes More button, Settings Models top, bottom band, chat suggestion wrap all hold. Recorded in OPEN.md.
- Sweeps errors, docks, contrast, touch, chrome at 1440, 720, 390, light and dark: errors 0 and contrast clean everywhere; touch found the chat mode segment (42px) and the no-model notice caret (30px) under the 44px floor at 720. Fixed in 10-responsive.css and offline-split-lazy.css.
- Speed: Library bundle fetched with the 3 s lazy list (app.js, one name added; app.js gz cap left 0 bytes spare). Library first visit 280 ms to 52 ms to paint; Documents long tasks about 585 to 520 ms (noise-level: its cost is the editor start, not the fetch).

Remaining
- Graph first visit: 4 to 7 long tasks of 60 to 300 ms at 1440 (frontend/js/graph-canvas.js gcDraw 55 ms self, rest is raster and commit of a continuously animating canvas in headless software rendering). No clear JS cause; needs a GPU browser to judge.
- Documents first open: codemirror.min.js evaluate (about 140 ms) and the Harper wasm compile (260 ms, background) run on first open; could be warmed on idle too (documents-prose.js).
- The app holds about 11,300 DOM nodes at boot (settings-modal 2,769 hidden, library whiteboard view 1,778); a lighter hidden DOM would cut style recalculation (UpdateLayoutTree 163 ms over 16 runs on Library).
- Not run: whiteboard and map contrast sections skip without a board in the notebook; touch.js forces a coarse pointer at every width.
