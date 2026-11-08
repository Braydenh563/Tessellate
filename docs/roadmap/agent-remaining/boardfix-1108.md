# boardfix-1108 remaining (whiteboard and mind map "need fixing")

Open rows re-checked on head 2026-11-08 (audit-1031-board BD1 to BD14 and audit-1028-board B1 to B40; ranked rows 5, 7, 20, 27, 28, 30, 31 are marked fixed in audit-1031-ranked.md):
- BD7 / B1, B2, B5, B6, B22 (file sizes, listeners vs removeEventListener): open, arch, L; not a user break.
- BD3 items-in-view-first and wbpress edge cache: left on purpose (board2-1101, board1518-1101), needs a quiet machine.
- B7 to B9, B15, B16, B21, B31 to B33, B39, B40 (static reads, never runtime-confirmed): not re-driven yet.
- Driven in Chromium (1440 and 390, light and dark): board core flow, map core flow, exports (PNG, SVG, JPG, Outline, draw.io download; PDF opens print; Mermaid copies), present, phone layout: no console errors, no 4xx/5xx, no targets under 24 px.

- done: leave flush (open editor saved on pagehide, keepalive)
- done: radial layout with several roots (overlaps 6 to 0)
- driven OK: drag branch onto another and Undo, all ten layouts (0 overlaps besides radial), map export PNG and SVG
- done: Present exit puts focus on the canvas (BODY to DIV#whiteboard-container); the first commit left the global-name cap at 9702 (cap 9701), fixed here by keeping the leave flag on wbCommitOpenEdit
- driven OK: delete linked sticky, Undo, Redo, Undo (server and client agree); phone map tap (targets 32x32, grip 24x24), 0 console errors
- left: phone opens a 5-topic map with 1 of 5 topics fully in view at 390 (known open-fit decision, not changed); Mermaid export gives no download (copies; not checked for feedback)
