# Deep audit 2026-10-31: code (code editor and IDE: file types, syntax, completions, codekit, run, tests, debugger, the code panel, find, large files, conflicts, export, library and search)

Fable suite, surface 6 of 12. Server on 8852, fake model on 11600, no Pyodide
extra (Python shows its install line). Drives hc1 and hc2 (Playwright, 1440
and 390, dark; requests counted per step) and an API probe. Files made: js,
py, json, html, csv, a 7,000-line (409,669-character) JavaScript file.
Observed unless marked code.

## Rows

| Row | Sev | Kind | Finding | Evidence | Where | Verified | Fix | Size |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CE1 | med | missing | **No member completion.** `console.l` offers nothing; the source completes keywords, snippets and the file's own identifiers of three letters or more, found by a regex over the whole text on every request (up to 2,000 options). Python's stdlib table works but ranks `P_ALL`, `O_PATH`, `POSIX_SPAWN_DUP2` above `path` for `os.pa` (every row `boost: 2`, no prefix ranking). | hc1 completion-js `r2: none`; python `comp` | `documents-code.js:734` `docCodeCompletionSource`; `:709` `docPyStdlibSource` | run and code | A small member table for the browser globals (`console`, `document`, `Math`, `Array.prototype`, `fetch`) and own object literals in the file; rank exact-prefix rows first; cache the identifier scan per document version. | M |
| CE2 | med | ux | **On a phone, running a file hides the editor.** At 390 x 844 the run panel keeps its 321 px and the editor's scroller is left 9 px tall; the code cannot be seen while its output is. | hc2 phone-run `editorH: 9`, panel `h: 321` | `docRunPanel` `documents-code.js:3365` (height kept per tab in px) | run | Cap the panel at 40% of the editor's height on narrow viewports, or open it as a sheet over the editor with a handle. | S |
| CE3 | med | perf | A 7,000-line file: open 530 ms with a 474 ms task, each keystroke 9 to 17 ms synchronous plus a 212 ms task behind it, a scroll jump 106 ms; the outline lists all 7,000 functions. A 10,000-line file (about 560,000 characters) cannot be saved at all: `MAX_CONTENT` 500,000 answers 422 "Check the content" with no size in the message. | hc2 big-code-7k; hc1 big-code (422) | highlight and outline passes; `routes_documents.py:66` | run | Outline capped to the visible range with a search; the limit named in the message ("over 500,000 characters"); a lint pass at idle only. | M |
| CE4 | low | a11y | `.cm-scroller` fails scrollable-region-focusable (serious) at 1440 and 390; the find panel's checkbox labels are 11.8 px (U9 remainder; the close button is now 24 x 24 and the count reads "2 matches"). `#doc-type-button` mismatch as docs DC5. | hc1 panel-axe, find-panel-u9; hc2 phone-axe | engine mount; `library-lazy.css:7523` | run | `tabindex="0"` or `aria-hidden` on the scroller as the editable has the focus; 13 px labels. | S |
| CE5 | low | ux | Tab indents (two spaces, good) but Shift+Tab leaves the editor for a link-like button instead of outdenting. | hc1 indent-tab `focusAfterTab: BUTTON.linklike` | keymap in `documents.js` (Tab bound, Shift-Tab not) | run | Bind Shift-Tab to `indentLess`; keep Escape then Tab as the way out. | S |
| CE6 | low | ux | A run has no time limit: an infinite loop stayed "Running" for 16 s until Stop (the UI stays responsive; the 500-row output cap is the only automatic stop). Each output row adds its own "Go to line N" button, so a loop printing one line yields a column of identical 43 x 28 buttons. | hc1 run-js-loop `mid.btns`, `ms: 16302` | `DOC_RUN_MAX_ROWS` `documents-code.js:2682`; row renderer | run | Fold repeated rows ("tick … x 11") with one line link; a soft limit at 30 s with "Still running. Stop?" | S |
| CE7 | low | missing | CSV opens as raw text with no grid (1028 D42 open); JSON and CSV have no Run and the Rendered view is off for both; the HTML preview frame in the run panel is 166 px tall. | hc2 json-html-csv | `documents-code.js:4271`, run panel frame | run | A read-only grid for csv and tsv; a taller preview or "Open in a tab". | M |
| CE8 | low | copy | A code file's library card says "19 words just now"; lines (and the type) would describe it. | hc1 library-and-search `card.text` | library card renderer | run | "6 lines · JavaScript". | S |
| CE9 | low | arch | `documents-code.js` 6,289 lines, 30 `addEventListener` to 1 `removeEventListener`, `docCodeScan` 427 lines, `docRunPanel` 264; `run_sandbox.py` 1,687 lines holds the route, the sandbox HTML, the worker script and the Python runtime source as strings. | counts | files | code | Move the sandbox page and the runtime to static files served from the same route; split scan, run and debug. | M |

## 1028 rows re-verified (code editor)

| Row | Now | Evidence |
| --- | --- | --- |
| U6 code file not under New | partly | templates dialog lists eight Code templates; the type button reads the type; Library New not re-run |
| U7 proportional code font | fixed | `.cm-content` and gutter `ui-monospace, "Cascadia Code", …` 14.72 px |
| U9 unstyled find panel | mostly fixed | close 24 x 24, inputs 247 x 32, buttons 32 tall, radius 4.8 px, "2 matches"; labels 11.8 px remain (CE4) |
| D32, D33 chords and two find UIs | open | not re-run; code unchanged (`documents.js:22806`, `documents-code.js:2627`) |
| D38 run-job heartbeat | open (code) | run jobs still start after an await |
| D42 CSV grid | open | CE7 |
| D51 code features present | confirmed | multi-cursor and folding not driven; bracket close, auto-indent, lint gutter, go to line seen |

## Coverage

| Area | Driven | Notes |
| --- | --- | --- |
| New js, py, json, html, csv files by API and open | run | type button names the type; Run only for js, py, html |
| Run JavaScript: output, line links, error, infinite loop, Stop | run | 674 ms to output; errors map to the line ("Stopped by an error."); worker keeps the UI alive |
| Tests (`test`/`expect`) | run | "1 passed, 1 failed", per-test rows with the diff |
| Debugger: F9, F5, step over, variables, call stack, Shift+F5 | run | pauses on the breakpoint; variables update per step |
| Diagnostics js (client), py (`/documents/check-syntax`, one POST per pause) | run | Problems tab counts |
| Completions: identifiers, Python stdlib | run | CE1 |
| Format (js-beautify), wrap row, Tab | run | |
| Find panel (engine), Replace in every document | run | docs DC4, DC10 |
| Code panel: Assistant (fake model, quick actions), Snippets (built-in list, save) | run | 2.1 s to the answer; panel 320 px, "Code panel" label |
| Export (.js download), library card, `/search` for code text | run | |
| Save conflict from another window | run | banner "Changed in another window. Resolve"; the resolve dialog not seen within 700 ms of a manual save (not verified) |
| Phone 390: editor, run panel, side panel | run | 44 px targets; CE2 |
| API: check-syntax (1.2 MB and 100,000 nested parens answered in under 20 ms; unknown language 400), snippets (65,536 cap), code-assist (action required), run jobs, sandbox headers | run | sandbox page: `sandbox allow-scripts`, `default-src 'none'`, `connect-src 'none'`, COOP and COEP set |
| Python run (needs the Pyodide extra), SQL run, p5 sketches, Emmet, colour swatches, hover docs, multi-cursor, folding, Go to line, Console tab, code revisions (`documents-ide.js`) | not driven | |

## Already good

- The JavaScript runner is a sandboxed iframe (`allow-scripts`, no network, no storage) with a worker; an infinite loop never freezes the page and Stop ends it.
- Errors, test failures and breakpoints all point at their line; the debugger shows variables, watches, the call stack and the breakpoints.
- Diagnostics for JSON and JavaScript are client-side; Python's go to a stateless route that refuses unknown languages with a 400 rather than an empty list.
- Code files export with their own extension; the search index finds their text; the library card shows the type.
- The find panel is styled with tokens; Tab inserts indentation; code is monospace.

## Not verified

- Python execution (the extra is not installed here); SQL and p5 runs; Emmet and hover docs; the conflict resolve dialog; multi-cursor and folding; the Console tab's evaluation; `/documents/run-sandbox` is served without a session (a static page; not judged).
