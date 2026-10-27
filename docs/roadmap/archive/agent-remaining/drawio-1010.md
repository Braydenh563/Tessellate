# drawio-1010: the draw.io catalogue, converter and shape data (Brief 44 part 1)

Worktree `wt-drawio`, branch `agent/drawio-1010`. The owner, 2026-10-10: "deep
analyse and catalog everything in draw.io as well, use, replicate, take and
implement it and then build on it and make it the best editor the world has
ever seen."

## Landed

- `7983f71a7`: `scratchpad/stencils/convert_stencils.py`, `render_compare.js`,
  five converted libraries and the Apache-2.0 NOTICE and LICENSE in
  `frontend/board-library/drawio/`, five comparison PNGs in
  `scratchpad/stencils/out/`.
- `c18ce1fa3`: WHITEBOARD_PLAN "The draw.io programme, 2026-10-10" (18 areas,
  288 table rows, Build first, Decisions).

## Third-party notice (no THIRD_PARTY.md exists in this tree)

The five converted libraries (basic, flowchart, arrows, bpmn, networks) are
derived from jgraph/drawio stencils, Apache-2.0, Copyright JGraph Ltd; the
notice and licence sit beside the data. Upstream's `stencils/LICENSE` bars
use in Atlassian products and the Atlassian marketplace; MemoryMap is
neither. draw.io's `templates/` are CC BY 4.0 (attribution needed when any
is converted). If a THIRD_PARTY.md is started, these two entries go in it.

## Left, one line each

- **Nothing loads the converted sets yet.** They sit in
  `frontend/board-library/drawio/`, outside the non-recursive glob in
  `routes_board_library.py` and outside `index.json`. Phase 2 of "Build
  first" (a "Shape libraries" dialog) owns it; not verified: that the board
  draws a converted set end to end (only a Chromium canvas draw of the same
  `d` strings was measured).
- **`wbPortFractions` does not read `data.ports` yet** (whiteboard.js 2457);
  the converter writes it (rebased to the first row's box). Phase 1.
  `frontend/js/whiteboard*.js` belongs to the boardmap agent, so no frontend
  code was touched.
- **UML and "network" libraries.** Upstream has no UML stencil library (UML is
  drawn by `Shapes.js` classes); `networks.xml` stood in for network. The
  `Shapes.js` classes (99) need a path-generator port, not a converter.
- **Stroke width fidelity**: the converter writes 2 board pixels per
  stencil unit; draw.io's `strokewidth="inherit"` follows the cell's width.
  Not compared against draw.io's own render (it cannot be made offline).
- **Bare `<rect/>` ops** (2,378 across all libraries, zero area): faithful to
  `stencils.min.js`, counted, drawn as nothing; if a shape looks short a
  stroke is the likeliest cause.
- **Not converted**: the other 199 libraries (24.1 MB of JSON; run
  `convert_stencils.py --min-js <fork>/src/main/webapp/js/stencils.min.js
  --out DIR`, about 100 s) and the `.drawio` templates (need the cell
  importer, phase 10).
- Known failures this worktree inherits, none from this work:
  `test_scratchpad_size.py` (1,018 tracked files over a cap of 1,003 before
  this branch; this adds 8), `test_plan_hygiene.py` networkx marker,
  `test_readme_freshness.py` tool count, ruff on `src/memorymap/vendor`.
