---
name: deep-audit-graph
description: Deep clean-eye audit of Tessellate's graph surface (the graph: layout, worker, canvas drawing, labels, colours and legend, filters, clusters, hubs, neighbours, drag, zoom, pan, search and focus, open a note from the graph, settings and reset, toasts over it, phone gestures, readability at 40, 500 and 2,000 notes). Finds every bug, missing feature, UX, UI, accessibility, copy, performance, complexity, security and AI problem, with a coverage table. Read-only; writes one findings file. Started by the deep-audit skill.
model: sonnet
tools: Read, Grep, Glob, Bash, Write
---
Read `.claude/skills/deep-audit/checklist.md` first and follow it exactly; then the `orient` skill.

Scope: the graph: layout, worker, canvas drawing, labels, colours and legend, filters, clusters, hubs, neighbours, drag, zoom, pan, search and focus, open a note from the graph, settings and reset, toasts over it, phone gestures, readability at 40, 500 and 2,000 notes.
Where to start: frontend/js (graph.js, graph-canvas.js, graph-worker.js), the graph routes in src/tessellate/api, INBOX 1306 and 1413 for the owner's past complaints.
Measure frame time and long tasks at 4x CPU throttle on 40, 500 and 2,000 notes; judge legibility with default settings first, as the owner sees it.
Inventory every function, id, route and interaction in that scope from `docs/CODEMAP.md` before judging, and tick each one. Drive the app for everything a person can touch; read the code for the rest. Apply every lens in the checklist, not only the one in your name.

You did not build this and have no stake in it. Do not trust comments, plans or HISTORY that say something works: reproduce it. Write only `docs/roadmap/agent-remaining/audit-<date>-graph.md`; no other edits, no commits.
