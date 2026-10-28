---
name: deep-audit
description: Full clean-eye audit of every Tessellate surface, element, function and route for bugs, missing features, UX, UI, accessibility, copy, performance, complexity, security and AI quality. Use when the owner asks for a deep scan, a full sweep, or "find everything that is wrong or missing".
---

# Deep audit (orchestrator)

The scans of 2026-10-28 (about 313 rows, `docs/roadmap/agent-remaining/audit-1028-*.md`)
saved as agents. Every agent reads `.claude/skills/deep-audit/checklist.md`.

## Surfaces and agents

| agent | scope |
| --- | --- |
| `deep-audit-shell` | shell, lock, notes list, library, dashboard, graph, timeline, reminders, settings, search, import, export, backup, notifications, palette, phone shell |
| `deep-audit-board` | whiteboard, mind map, maps, present mode, board library |
| `deep-audit-docs` | document editor, code editor, spell and prose, find and replace, export |
| `deep-audit-ai` | chat, composer, acts, Ask, Guide, Atlas, companions, help chat |
| `deep-audit-backend` | every route and module in `src/tessellate`: security, races, data safety, migrations, jobs |
| `deep-audit-ux` | cross-surface design and WCAG 2.2 pass, measured, both themes, every width |
| `deep-audit-perf` | lag, long tasks, forced layout, per-frame loops, boot size, slow routes, complexity ratchet |

## Steps

1. Run at most the agent cap (HANDOVER tier line; three on `max`) at once,
   each in its own worktree, port and data dir; rounds until all seven ran.
   Rung: Sonnet for each agent (they drive the app), Haiku only for a pure
   inventory, Opus for the ranking if rows conflict.
2. Brief each with: the date, its port (8794 up), "read the checklist",
   and the ids already open (`audit-*-ranked.md`) so it re-verifies rather
   than re-lists.
3. Rank: merge the seven files into `audit-<date>-ranked.md` (severity,
   then security and data loss, broken, UX and a11y, perf, polish); mark
   each row planned or new against the plans; rows already fixed leave.
4. Commit the files, then fix in rank order, the class not the case.

Standing order 8: these files are findings, not plans; built rows move to
HISTORY at the step boundary.
