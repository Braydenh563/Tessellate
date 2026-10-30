# ai-extras-1030: remaining list

Agent ai-extras, branch agent/ai-extras-1030. Rows are in `audit-1030-ai.md` (A) and `audit-1030-extras.md` (Y); a fixed row carries `**Fixed <hash>.**` with its measurement.

## Done

- Extras Y1 to Y4, Y6 to Y18: 881588c, a9f6aea, 62d0289.
- AI A1 to A8, A10 to A14, A16 to A23, A26 to A29, A31 to A34, A38 to A41: ff5ac76 (A25 and A35 closed as not bugs).

## Open

- Y5 (L, perf): the idle preload of whiteboard.js and documents.js after unlock. Not started.
- A9, A1 second half (`composer_web.search_down`), A6 (`composer_web.web_off`), `composer_digest.web_query`: composer-owned files, left for the composer agent.
- A15: bare-verb table in `commands.py` (partly covered by the act matrix, the remainder is a table rewrite).
- A18: "what are my tasks" still reaches the mind-map topics in the Guide.
- A2 second half: show the query on the Web pill before it goes out.
- A24: `#web-search-history` is empty while results are on screen by design (shown only with an empty box); not changed.
- A30: the badge race after Clear history is not reproduced by reading; needs a driven run.
- A36, A37: companion menu focus return and phone offset, not started.
- A42 (M, perf): per-frame batching of streamed Markdown, not started.
- A43 (unverified): the context pop total; needs a real provider.
- A44 (M): a no-model Chat answer with an attached note lists recents; the decision is in `composer.py` (composer-owned).
