---
name: orient
description: Start a Tessellate session or agent task with the fewest tokens. Use at the start of every session and every agent brief before reading any plan or source file.
---

# Orient (read this, then only what it points at)

1. Read `CLAUDE.md` section 2 (standing orders) once per session; nothing
   else in it unless a rule is in question.
2. Read the first "**Now (" paragraph of `docs/roadmap/HANDOVER.md` and the
   owner notes above the first heading. Stop there.
3. In `frontend/js`, `src/tessellate/ai` or `src/tessellate/core/overlay`, read the folder's `CONTEXT.md` first (which files hold what, which tests guard them). Find code through `docs/CODEMAP.md` (every function, route, CSS section
   and plan heading with its file and line; regenerate with
   `python scripts/codemap.py` if `tests/test_codemap_fresh.py` fails).
   Grep the map, then `sed -n 'A,Bp'` the lines you need. Never `cat` a
   file over 300 lines; never read a plan whole, grep its headings.
4. A brief names files, selectors, line areas and numbers: start at the
   change, not at orientation. If a brief lacks them, grep the map and add
   them to the brief before working.
5. Decisions are in each plan's "Decisions made" section: grep for the
   noun, read the one numbered item.
6. Report in five lines; no transcript, no narration; numbers over prose.
