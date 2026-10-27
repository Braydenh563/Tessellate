# Third-party code and data

Tessellate is AGPL-3.0 and runs offline, so what it borrows ships inside the
repository rather than being fetched. This page credits every library vendored
into it, with the version and licence it came under; each one's licence text
sits beside it. `tests/test_vendor_manifest.py` fails the build when a file
under `src/tessellate/vendor/` or `frontend/vendor/` is missing from this page.

## Python (`src/tessellate/vendor/`)

| Library | Files | Version | Licence | Source | Used by |
| --- | --- | --- | --- | --- | --- |
| FlashText | `flashtext.py` | 2.7 | MIT (`flashtext.LICENSE.txt`) | https://github.com/vi3k6i5/flashtext | `ai/taxonomy.py`, matching the taxonomy pack's phrases in a note |

## Browser (`frontend/vendor/`)

| Library | Files | Version | Licence | Source | Used by |
| --- | --- | --- | --- | --- | --- |
| CodeMirror 6 | `codemirror/` | packages pinned in `codemirror/package.json` (view 6.x) | MIT (`codemirror/LICENSE`) | https://codemirror.net | the documents editor's source mode |
| Emmet | `emmet/` | 2.4.11 | MIT (`emmet/LICENSE`) | https://github.com/emmetio/emmet | abbreviations in the code editor |
| js-beautify | `js-beautify/` | 2.0.3 | MIT (`js-beautify/LICENSE`) | https://github.com/beautifier/js-beautify | Format on a whole JavaScript, CSS or HTML document, loaded on demand by `documents-code.js` |
| sucrase | `sucrase/` | 3.35.1 (bundled by `sucrase/build.sh`) | MIT (`sucrase/LICENSE`) | https://github.com/alangpierce/sucrase | running a TypeScript document: the types are stripped, not checked, loaded on demand by `run-core.js` |
| JS-Interpreter | `js-interpreter/` | commit 45d00b0 (2026-06-12; `interpreter.js` with its Acorn, minified by `js-interpreter/build.sh`) | Apache-2.0, Acorn MIT (`js-interpreter/LICENSE`) | https://github.com/NeilFraser/JS-Interpreter | Debug on a JavaScript or TypeScript document: the run sandbox steps the script line by line (`api/run_sandbox.py`), handed over by `run-core.js` on demand |
| sql.js | `sqljs/` | 1.14.2 (`sql-wasm.js` and `sql-wasm.wasm`, copied by `sqljs/build.sh`) | MIT (`sqljs/LICENSE`) | https://github.com/sql-js/sql.js | running a SQL document against an in-memory SQLite in the run sandbox, fetched on demand by `run-core.js` |
| Harper | `harper/` | harper.js 2.10.0 | Apache-2.0 (`harper/LICENSE`) | https://github.com/Automattic/harper | grammar checking in documents, as WebAssembly |
| D3 | `d3.v7.min.js` | 7.9.0 | ISC (`d3.LICENSE.txt`) | https://d3js.org | the graph and the whiteboard's layouts |
| p5.js | `p5.min.js` | 1.11.13 | LGPL-2.1 (`p5.LICENSE.txt`) | https://p5js.org | the generated brand emblem, and Run on a p5.js sketch document (`run-core.js` hands the file to the run sandbox) |
| Atkinson Hyperlegible | `atkinson/` | latin subset, 400 and 700 with their italics (woff2) | SIL OFL 1.1 (`atkinson/LICENSE`) | https://github.com/googlefonts/atkinson-hyperlegible | Appearance, Font, Readable: the `--ui-font` face, declared in `00-tokens-shell.css` |
| Phosphor Icons | `phosphor/` | the web font build | MIT (`phosphor/LICENSE`) | https://phosphoricons.com | every icon in the app |
| Mermaid | `mermaid/` | 12.2.0 (`mermaid.min.js`, unchanged from the npm package; `mermaid/VERSION.txt`) | MIT (`mermaid/LICENSE`) | https://mermaid.js.org | drawing every ```` ```mermaid ```` fence (flowchart, sequence, class, state, ER, Gantt, pie, mind map, timeline and the rest) in documents and chat, inside a sandboxed same-origin frame loaded on first use (`mermaid-frame.js`) |
| Mammoth | `mammoth/` | 1.13.0 (`mammoth.browser.min.js`) | BSD-2-Clause (`mammoth/LICENSE`) | https://github.com/mwilliamson/mammoth.js | reading a .docx imported into the Library, loaded on demand by `documents-word.js` |
| docx | `docx/` | 9.10.0 (`dist/index.iife.js` minified) | MIT (`docx/LICENSE`) | https://github.com/dolanmiu/docx | writing a document as .docx (Download as Word), loaded on demand by `documents-word.js` |
| English word list | `wordlist/` | built by `wordlist/build.sh` | the English Speller Database licence (`wordlist/LICENSE`) | https://wordlist.aspell.net | the documents editor's spelling check |
| Python standard library table | `python-stdlib/` | built by `scripts/gen_python_completions.py` | PSF License Agreement (`python-stdlib/LICENSE`) | https://docs.python.org/3/license.html | a Python document's completions after `module.` and its hover card |

## Optional downloads (Settings, Packages)

Never in the repository: each is fetched on an Install press from the pinned
address in `src/tessellate/core/extras.py`, checked against its sha256, and
unpacked into `<data dir>/extras/<id>/` with its licence beside it.

| Library | Files | Version | Licence | Source | Used by |
| --- | --- | --- | --- | --- | --- |
| Bergamot translator | `extras/translate/bergamot-translator-worker.js`, `.wasm` | npm `@browsermt/bergamot-translator` 0.4.9 (engine v0.4.5+4917c11) | MPL-2.0 (`extras/translate/LICENSE`, downloaded with it) | https://github.com/browsermt/bergamot-translator | Translate this (`frontend/js/translate-worker.js`), WORLD_CLASS_PLAN 28.5 row 10 |
| Firefox Translations model, English to Spanish | `extras/translate/model.enes.intgemm.alphas.bin`, `lex.50.50.enes.s2t.bin`, `vocab.enes.spm` | `retrain_hr_fix_names` export, 2026 registry | MPL-2.0 (the `mozilla/translations` README) | https://github.com/mozilla/translations | the same |
| marian-nmt (inside the Bergamot WASM) | compiled into the `.wasm` | browsermt fork, as pinned by bergamot-translator v0.4.5 | MIT | https://github.com/browsermt/marian-dev | the translation engine |
| intgemm (inside the Bergamot WASM) | compiled into the `.wasm` | as pinned by marian-dev | MIT | https://github.com/kpu/intgemm | its 8-bit matrix routines |
| SentencePiece (inside the Bergamot WASM) | compiled into the `.wasm` | as pinned by marian-dev | Apache-2.0 | https://github.com/google/sentencepiece | splitting text into the model's word pieces |
| ruy (inside the Bergamot WASM) | compiled into the `.wasm` | as pinned by marian-dev | Apache-2.0 | https://github.com/google/ruy | matrix routines |
| ssplit-cpp (inside the Bergamot WASM) | compiled into the `.wasm` | as pinned by bergamot-translator v0.4.5 | Apache-2.0 | https://github.com/browsermt/ssplit-cpp | splitting a passage into sentences |

## Board library (`frontend/board-library/`)

| Library | Files | Version | Licence | Source | Used by |
| --- | --- | --- | --- | --- | --- |
| draw.io stencils | `drawio/` | converted by `scripts/build_board_library.py` | Apache-2.0 (`drawio/LICENSE`, `drawio/NOTICE.txt`) | https://github.com/jgraph/drawio | the whiteboard's shape library (basic, flowchart, arrows, BPMN, networks) |
| Phosphor Icons | `icons.json` | glyphs converted to paths by `scripts/build_board_library.py` | MIT (`../vendor/phosphor/LICENSE`) | https://phosphoricons.com | the whiteboard's icon shapes |

## Data

- `ai/data/taxonomy/` is the Tessellate taxonomy pack, 5.0.0-consolidated
  (527 categories, 6,478 phrase assignments, 1,109 roles, 44 institutions,
  facets and 30 context rules), commissioned by the project's owner and
  generated with Perplexity from the owner's own uploaded taxonomy; it ships
  under the project's licence. Its original vocabulary is kept in
  `tests/fixtures/taxonomy/original_taxonomy.json`, and its tests in
  `tests/test_taxonomy_pack.py` (WORLD_CLASS_PLAN 23, decision 1).
- `ai/question_noise.py`'s misspelling table (the block added 2026-10-10)
  appears to be drawn from Wikipedia's "Lists of common misspellings", which
  is CC BY-SA 4.0. Its origin is not recorded in the commit that added it;
  until it is confirmed or replaced, it is credited here as that list.
  https://en.wikipedia.org/wiki/Wikipedia:Lists_of_common_misspellings

## Elsewhere in the repository

- `.claude/skills/`: vendored design skills, MIT, credited in
  `.claude/skills/README.md`. They are tools for working on the app and are
  not shipped in it.
