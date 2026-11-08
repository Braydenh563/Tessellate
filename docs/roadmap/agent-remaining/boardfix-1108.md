# boardfix-1108 remaining (whiteboard and mind map "need fixing")

Open rows re-checked on head 2026-11-08 (audit-1031-board BD1 to BD14 and audit-1028-board B1 to B40; ranked rows 5, 7, 20, 27, 28, 30, 31 are marked fixed in audit-1031-ranked.md):
- BD7 / B1, B2, B5, B6, B22 (file sizes, listeners vs removeEventListener): open, arch, L; not a user break.
- BD3 items-in-view-first and wbpress edge cache: left on purpose (board2-1101, board1518-1101), needs a quiet machine.
- B7 to B9, B15, B16, B21, B31 to B33, B39, B40 (static reads, never runtime-confirmed): not re-driven yet.
- Driven in Chromium (1440 and 390, light and dark): board core flow, map core flow, exports (PNG, SVG, JPG, Outline, draw.io download; PDF opens print; Mermaid copies), present, phone layout: no console errors, no 4xx/5xx, no targets under 24 px.

- done: leave flush (open editor saved on pagehide, keepalive)
- next: drag a branch, switch layout, map export, Present exit focus (lands on BODY), Mermaid export feedback
