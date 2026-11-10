# spell-1110 remaining (INBOX 1731, DOCUMENTS_PLAN)

- done (a) to (e): see HISTORY.md "Moved from the plans, 2026-11-10 (spell-1110: the spelling second opinion)". Fixture false flags 16 to 5 (no dialect), 14 to 5 (Australian).
- done (f): LanguageTool optional download, see lag1726-1110.md.
- not verified: the documents editor's spelling hold (a word is held as known until the worker answers, `docSpellLookup`) and the note menu's Add to dictionary row were not driven in a page, only the worker was (real Chromium under the CSP: `harper-worker.js` loads `spell-second.js`, nspell and the dictionaries, 2.8 s cold lint, 174 ms first spell answer, no page errors); run `scratchpad/ui-sweeps` against a document with "arvo" and "teh".
- check: LibreOffice's en_GB is LGPL (its README), so `vendor/spelling/en_GB.*` is SCOWL's own en_GB-ise 2020.12.07 instead; the brief named the LibreOffice one.
- check: `tests/test_every_route_is_locked.py` failed for POST /auth/hello/begin and /auth/hello/unlock on the integration branch before this work (hello-1110), not touched here.
- idea: the diagnosis list in `documents-prose.js` (`DOC_GRAMMAR_FILES`, held equal to the worker's `vendor/harper` imports by `tests/test_prose_tools.py`) does not name `spell-second.js` or `vendor/spelling`; a worker that fails to start on those would say "did not start" with a shorter reason.
