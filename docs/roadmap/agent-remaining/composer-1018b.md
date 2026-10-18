# composer-1018b (Sonnet, Python only)

Steps: 1 Harper over composer output; 2 INBOX 1298 complexity seed rows; 3 "ghose" and "happyer"; 4 test_owner_typos intent cases alone.

- Step 1 done: eb9e089. `composer_digest.polish` and `_polish_out`, tests in `tests/test_composer_polish.py` (28).
- Step 2 done: c1e3be0. 17 composer_digest rows split and deleted from the seed; composer tests pass unchanged.
- Step 3 done: 73c4934. `spelling._slip_penalty`, `_y_to_i`; four fixtures; `_app_counts`, `_fix`, `_repair_by_speller` back under 15 (they were failing `test_complexity` on the base).
- Step 4: no code needed; bb57120 (already on the branch) fixed it. `tests/test_owner_typos.py` alone: 421 passed serially.

Left:
- INBOX 1298: the 18 seeded functions that grew (`_stream_lines` 93 to 106, `_generate_diagram` 27 to 47, `mcp_server.handle_request` 17 to 30; the other 15 first-seed values were never recorded), `tests/complexity_seed.json`.
- A bare "ghose" before a verb-like word at the second place still reads as the asking word "whose" (`question_noise._at_asking_place`, "enable ghose mode").
