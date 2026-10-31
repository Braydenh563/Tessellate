# Notes deep audit, 2026-10-31

Scope: notes end to end (made, written, viewed, managed, found, linked, filed, and shown on every other surface).
Head: `claude/sharp-thompson-45hngp` merged at 7ebddaf on `agent/audit-notes-1031`. Server on port 8851 (8850 was
held by another agent's server), data dir `/tmp/claude-0/a-notes-data`: the showcase seed (75 notes, 3 documents, 2
boards) plus 124 filler and edge notes (title-less, 1,000-word, CJK, private, math, table, wiki, hostile markdown,
frontmatter, 316-character title, duplicates, nested lists) = 199 notes at the start, 207 by the end of the API probes.

**Caveat, said first:** every provider runs on a fake transport and no model ran (CLAUDE.md 4). Everything model-on
(AI filing wording, tag suggest, Tidy repairs, entity pages, meaning search, model-on chat) is unverified. Rows are
`run` (reproduced on this head by driving the app or the API) or `code` (read, not run).

(Work in progress: the coverage table and the findings fill in below as the drives finish.)
