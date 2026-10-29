# Composer, audit 1029 rows 49, 53, 54, 55 (agent ab5c3e21)

## Done (one commit per row, none pushed)

- 49, 0c30151: citation numbers by first mention (`sourcesByFirstMention` in chat-agent.js; Ask, Chat, palette and the capture view pass the grounded sentences). `tests/test_citation_order_1029.py`.
- 53, 97d3c65: offers from cited notes, honest review kinds (book vs film), one clip (`realise.cut_title`), date prepositions (`recognise.adverbial`, `mid_sentence`). `tests/test_composer_offers_1029b.py`.
- 54, 9b6e683: frame grammar C6, C7, C11, C12, C13, C14 (zero before "of", doubled hedges, "And N more.", empty-day answer, `realise.mend_stops`, greeting in kind). `tests/test_composer_grammar_1029b.py`.
- 55, 2d3584b: summaries and the digest skip a properties block, never echo a title or a bare label, end label lines with a stop, and summarise a list note by its items and counts (`study.list_gist`). `tests/test_composer_summaries_1029b.py`. The extract preview's Save moved to the lazy gesture-kit.js to win back the gzip ratchet rows 49 and 53 had passed (by 406 bytes).

## Remaining (found, not fixed)

- The lead note is sometimes wrong: "what should I buy for my sister" answers from the Guitar note; "what did I think of The Overstory" leads with "Thinking, Fast and Slow".
- A greeting's "touched on about" or "what did I write about about" takes the word "about" as a topic when notes are titled "Note N about cats".
- "summarise my week" gives one note's summary, not a week recap.
- "what is the checklist note" answers as facts ("One, from your Checklist note. **Also:** two; three.") instead of the checklist.
- A plain summary opens with "Let me check." (`composer_compose.opener` for `study_summary`). Adding it to `_NO_AROUND` fails `test_twenty_distinct_surfaces_per_ability[study_summary]`, which pins the opener variety; the owner decides.
- C13 "I called mum was on 24 October" was not reproduced.
- C11: boards counted as notes was fixed in `_recall`'s list, not in the activity recap's wording.
- A properties block with CRLF line ends is not recognised by `properties.block_end` (the app's own rule); the title of such a note is "---".
- `src/tessellate/mcp_server.py` has an unrelated, unstaged modification (duplicated lines) in this worktree; it is not part of any commit here.
- All composer tests run against a fake transport; no real-model check, and no browser check of the JS beyond `node --check`, the lint tests and node-driven tests.
