# Composer, audit 1029 rows 49, 53, 54, 55 (agent ab5c3e21)

## Done (one commit per row, none pushed)

- 49, 0c30151: citation numbers by first mention (`sourcesByFirstMention` in chat-agent.js; Ask, Chat, palette and the capture view pass the grounded sentences). `tests/test_citation_order_1029.py`.
- 53, 97d3c65: offers from cited notes, honest review kinds (book vs film), one clip (`realise.cut_title`), date prepositions (`recognise.adverbial`, `mid_sentence`). `tests/test_composer_offers_1029b.py`.
- 54, 9b6e683: frame grammar C6, C7, C11, C12, C13, C14 (zero before "of", doubled hedges, "And N more.", empty-day answer, `realise.mend_stops`, greeting in kind). `tests/test_composer_grammar_1029b.py`.
- 55, 2d3584b: summaries and the digest skip a properties block, never echo a title or a bare label, end label lines with a stop, and summarise a list note by its items and counts (`study.list_gist`). `tests/test_composer_summaries_1029b.py`. The extract preview's Save moved to the lazy gesture-kit.js to win back the gzip ratchet rows 49 and 53 had passed (by 406 bytes).

## Fixed in the follow-up (agent c1029c, tests/test_composer_leftovers_1029c.py)

- A function word is never a topic (`query.is_topic_word`; the hello's "touched on about").
- A CRLF properties block is a block (fence rule takes a CR; a blank line after the fence no longer unnames the note).
- A checklist-only note asked for by name is shown as the checklist (`composer_digest._show_checklist`; `composer._term_weights` counts "list" a quarter beside a naming word).
- "Summarise my week" is the week's recap (`activity.as_recap`, `chat_extra.events`).
- The lead note: a doing word no longer picks the note (`composer_digest._members`: "what should I buy for my sister" led with Guitar). "What did I think of The Overstory" leading with "Thinking, Fast and Slow" was not checked here and stays open.

## Remaining (found, not fixed)

- A plain summary opens with "Let me check." (`composer_compose.opener` for `study_summary`). Adding it to `_NO_AROUND` fails `test_twenty_distinct_surfaces_per_ability[study_summary]`, which pins the opener variety; the owner decides.
- C13 "I called mum was on 24 October" was not reproduced.
- C11: boards counted as notes was fixed in `_recall`'s list, not in the activity recap's wording.
- `src/tessellate/mcp_server.py` has an unrelated, unstaged modification (duplicated lines) in this worktree; it is not part of any commit here.
- All composer tests run against a fake transport; no real-model check, and no browser check of the JS beyond `node --check`, the lint tests and node-driven tests.
