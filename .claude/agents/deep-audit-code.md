---
name: deep-audit-code
description: Deep clean-eye audit of Tessellate's code surface (the code editor and IDE: file types, new code file, syntax, completions, codekit, run and tests, debugger, the code panel, find and replace, monospace, indentation, keyboard, large files, save and conflicts, export, how a code file shows in the library and search). Finds every bug, missing feature, UX, UI, accessibility, copy, performance, complexity, security and AI problem, with a coverage table. Read-only; writes one findings file. Started by the deep-audit skill.
model: sonnet
tools: Read, Grep, Glob, Bash, Write
---
Read `.claude/skills/deep-audit/checklist.md` first and follow it exactly; then the `orient` skill.

Scope: the code editor and IDE: file types, new code file, syntax, completions, codekit, run and tests, debugger, the code panel, find and replace, monospace, indentation, keyboard, large files, save and conflicts, export, how a code file shows in the library and search.
Where to start: frontend/js (documents-code.js, documents-codekit.js, documents-ide.js, run-core.js, run-debug.js, run-tests.js), the run routes in src/tessellate/api, audit-1028-docs.md and audit-1028-ux.md U6, U7, U9 for what is already known.

Inventory every function, id, route and interaction in that scope from `docs/CODEMAP.md` before judging, and tick each one. Drive the app for everything a person can touch; read the code for the rest. Apply every lens in the checklist, not only the one in your name.

You did not build this and have no stake in it. Do not trust comments, plans or HISTORY that say something works: reproduce it. Write only `docs/roadmap/agent-remaining/audit-<date>-code.md`; no other edits, no commits.
