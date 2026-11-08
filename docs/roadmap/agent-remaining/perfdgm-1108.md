# perfdgm-1108 remaining

- done P2 (c0993790): empty kebab per row, real menu on first press (diagram-library.js lazyKebab). Done P3: relabel patch in the SVG and idle, typing-aware draw (diagram-picture.js patch, idle).
- left: delegate row shape/connect/chip listeners to one on S.tree (about 3 per row, 251 listeners on open); start the mermaid fetch in parallel with the document fetch (diagram-builder.js show); idle-slice rows past 40 blocks. The audit's 2,500 listeners and the 766/1,128 ms relabel long tasks did not reproduce here (host loaded).
- found-not-fixed: a real mouse press on a row's opener can land on .dgm-joins (pointerdown target differs from pointerup), seen in Playwright on the baseline too.
