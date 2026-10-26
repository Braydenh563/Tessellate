# triage-1010: the Gemini branch, judged and repaired

Branch `agent/triage-1010`, cut from `gemini/composer-improvements` (12 Gemini
commits, 16a3262 to e00aed0). Commits: 18670d4 (step 1), 6629333 (vendor and
composer), 5fe8c2f (cited names, shapes), a5b9154 (filing), 04059e2 (routing, imports,
tables, search_help), then this file.

## Measured

| Measure | main | Gemini head | now |
| --- | --- | --- | --- |
| Showcase grounded | 1.0 | 0.25 | 1.0 |
| First line answers | 25 | 23 | 25 |
| Connectives distinct | 41 | 32 | 47 |
| Mean words a sentence | 6.9 | 12.5 | 6.8 |
| Noisy set, hand / derived | 83/85, 301/303 | n/a | 83/85, 301/303 |
| `import memorymap.ai.composer`, cold | 0.75 to 0.94 s | 0.76 to 0.85 s (from the repo root only) | 0.08 to 0.15 s |
| Filing top-1, 40 labelled notes, leave-one-out (wrong) | 0.05 (2) | 0.225 (14, into categories nobody made) | 0.15 (2) |
| Vendored Python | none | 15 MB, 1,031 files | FlashText, one file |

## Left, one line each

- "Study and university tags are suggested on the top note if it has no tags no matter what the note is about" (the owner, 2026-10-10): not reproduced with no model; the no-model path is now pinned by `tests/test_filing_accuracy.py`. Suspected cause is the model path: `librarian.suggest_tags` lists the notebook's tags most used first and says "Prefer one of those" (src/memorymap/ai/librarian.py:1052), which a small model reads as "use the first two". Needs a real model to confirm.
- "Gemini might have removed the spell checker??" (the owner): it did not touch the editor's speller (its frontend diff is skills.js, index.html, 02-chat-graph.css); the pyspellchecker it added to the composer was removed here (decision 2). Nothing to restore.
- `_stem` turns "news" into "new", which its own comment says it must not (src/memorymap/ai/composer.py:453); found writing the stemmer test, not changed.
- Tool schemas at 32,762 of 32,768 characters for a 32k window (tests/test_prompt_budget.py): the next tool added trims every description.
- Boot CSS 3 bytes under its cap, boot JS about 100 bytes under (tests/test_boot_budget.py, tests/test_static_compression.py): the cited-name code went into ask-compose.js for this reason.
- Unit conversion (Gemini's pint) and the "what time is it" / "reading time" shapes were dropped, not rebuilt: "convert 5 km to miles" is read as a notes question with no model.
- Gemini's light rewrites ("I" to "you", CHAT_PLAN decision 23) were dropped because they changed quoted text and broke grounding; a marked rewrite would need the grounding rows to carry the original span.
- intent.py's `_NOTE_WORDS` gained "think", "plan", "idea" and more on the Gemini branch (src/memorymap/ai/intent.py:65), so "I think so" routes to the notes; not measured.
- Rail nodes (frontend/css/02-chat-graph.css:732): 0.75rem kept, measured on a synthetic run: thinking and plan rows 0.12px from the first line's centre (3.3px at 0.55rem), tool chips 4.1px high (7.3px at 0.55rem); not measured against a real agent run.
- `search_help` found nothing for "what is agent mode" and "how does search work" (2 of 10; `help_block_for`, src/memorymap/ai/help_chat.py:2467).
- The Gemini misspelling table looks drawn from Wikipedia's lists (CC BY-SA); its origin is unrecorded (docs/THIRD_PARTY.md, Data).
