# basered-1031: remaining

Branch agent/basered-1031. Done: every item below reproduced alone, then fixed in code.

- Complexity: `agent.run_agent`, `composer_study.open_named`, `composer_lists._counted`, `composer_digest._chip_subject` and `_when_gone`, `composer._compare` (gone from the seed), `question_noise.social_kind` (seed 18 to 17) split; lazy cycle was two groups (composer and composer_versus), now one.
- `link_counts_bulk` renamed `links_count_bulk`: a read matched the `link_` write prefix of test_events.
- `docFormatCode` guard was not lost: 7add0bf spelled it `docStr(view.state.doc) !== text`; the test's literal was updated.
- `ChatRequest.raw_question` capped at 20000 like `question`.
- Gold 11 fell 79 to 73 on the words-only line (5bf9b0a); the four wordings are shorter (76); none ends in " more.", which is a natural-voice phrase the voice test finds inside a professional answer.
- Clock: route gold test and test_ask_focus pinned. test_ask_focus passed alone; the greeting test was already pinned, the rest were not.

Left: none. Found, not fixed (all four fail on c181578 too, outside the brief): test_composer_classes_1357 `hmm what about knitting` (answers as general knowledge), test_composer_mermaid_1466 flowchart (gets `mindmap`), test_composer_slots_1029b `Departure` chat and ask ("Back in November 2025" for "14 November"); and tests/test_composer_route_688.py:23 reads `date.today()` (its notes are written the same day, so it holds).
