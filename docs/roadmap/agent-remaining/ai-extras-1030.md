# ai-extras-1030: remaining list

Agent ai-extras, branch agent/ai-extras-1030. Rows are in `audit-1030-ai.md` (A) and `audit-1030-extras.md` (Y); a fixed row carries `**Fixed <hash>.**` with its measurement.

## Done

- Extras Y1 to Y4, Y6 to Y18: 881588c, a9f6aea, 62d0289.
- AI A1 to A8, A10 to A14, A16 to A23, A26 to A29, A31 to A34, A38 to A41: ff5ac76; A36, A42: 6254337; A15 partly: 1d3da33 (A25 and A35 closed as not bugs).

## Done since

- A15 (1d3da33, 0ba1a33), A18 (5f41de7), A2 second half (d5d83b6), complexity splits (d5d83b6).

## Open

- Y5 (L, perf): see its row; the board view cannot leave the DOM while the Library bundle is preloaded at 3 s.
- A37: reproduced, not fixed (row has the numbers).
- A9, A1 second half (`composer_web.search_down`), A6 (`composer_web.web_off`), `composer_digest.web_query`, A44, A26 greeting: composer-owned, left for the composer agent.
- A24: by design. A30: needs a driven run. A43: needs a real provider.
- A29, A38, A42, A36, A10 timing: fixed by reading and unit tests, not driven with a model.
