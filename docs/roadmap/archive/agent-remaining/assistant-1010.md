# assistant-1010: the assistant catalogue (CHAT_PLAN "The assistant catalogue, 2026-10-10")

Research and specification only; no code, fixtures or tests were written. The
catalogue is in `docs/roadmap/CHAT_PLAN.md` (sections 0 to 5). Left, in order:

1. Section 0 finding 1 is unfixed: Gemini-branch utilities are discarded by `if not out.rows` in `ai/composer.py` (~2706 to 2795). Owner: "I want the composer to be more integrated, have more abilities, utilities, functions, and more."
2. Finding 2 unfixed: the `translate` rule at `ai/composer.py:292` ends in `to\s+([a-zA-Z]+)\b` and swallows "what do I need to buy", "how to cook rice", "what if I move to Lisbon".
3. Finding 3 unfixed: "summarise my gym notes" raises `UnboundLocalError` on `sides` (`ai/composer.py` ~2795).
4. `when.resolve("last friday")` returns the next Friday (`ai/when.py` `resolve`); recall must use `entry/timewords.find`, which is right; "since March", "the week before last" and a past "on 3 March" are read by neither.
5. A model that fails mid-answer leaves an error line, not the composed answer (`api/routes_chat.py` ~1963 to 1976); write `tests/test_chat_degrades.py` first (CHAT_PLAN section 3).
6. None of the 16 eval fixtures in section 4 exist; the five in decision 40 and the eight proposed ones need their rows written (645 rows), and the floors set from the first measured run.
7. Five proposed decisions (computed values, no archive verb, dated currency table, playful voice waits, model picks among readings) are for the orchestrator to take or drop; each wants an INBOX entry with its one-line recommendation (standing order 3).
8. Re-run the 37-question probe (section 0 method) on Brief 35's head, since the triage may already change findings 1 to 3.
9. Sources whose pages did not state a mechanism, to read from their repositories if the detail matters: Mycroft Adapt's confidence and `one_of` and context, Padatious' treatment of typos, Alexa's error-handling and reprompt patterns, how Wolfram Alpha shows assumptions, Apple Notes search (its support page was unreadable), Notion AI's autofill and citations.
10. Not verified: any real model's behaviour in the handoff (choosing among numbered readings, "reorder, do not add"); the taxonomy pack's size as a synonym source (policy 3 figures taken from ROADMAP, not opened).
11. Found, not fixed: `ai/tool_summary.py` is named by `commands.py` on `origin/wip/composer-acts` and does not exist on this branch; `entry.query` `entity:` finds nothing with no model because `EntityMention` rows are model-extracted (`ai/entities.py`).
