# Vault gate, INBOX 1437 (audit 1029 rank 8): remaining

Done: `manager.note_is_sealed` / `shown_tags`; export and history 409 "Unlock first"; Graph label, words and tags; `/tags` counts; tags dropped in the note list, exports (json, csv), Library, Timeline, Insights; the frontend retries after the password prompt (`skills.js` `downloadFromApi`, `note-history.js`); `tests/test_vault_read_surfaces.py`.

Left, one line each:
- Not driven in a browser: the unlock prompt on a locked export and History (frontend/js/skills.js downloadFromApi, frontend/js/note-history.js line 19); node --check only.
- Tag reads that remain on the raw column for non-response uses (AI tools, notebook_stats, slash commands): the AI already excludes private notes; not re-audited here (src/tessellate/ai/notebook_stats.py).
- The walk covers GET routes with one private note and the `q`, `query`, `text` params; POST read-like routes (search bodies, `/entries/query`) are not walked (tests/test_vault_read_surfaces.py).
