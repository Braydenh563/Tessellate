# Brief: the composer, extended (Opus, owner 2026-10-17)

Owner: "use opus on the composer improvements ... improving and extending
capability, understanding and response improvement and integration across the
app ... cover the things logged for next pr ... in the handover, OPEN.md and
backlog and roadmap". INBOX 904 is the verbatim list (B02, B03, B07, B08,
B10, B11, B30, B33, B48, B69, B83, B84, B85, B86 are the composer's).

Done already (a9d427c, do not redo): recency asks ("What have I saved
recently?"), key mashes (`intent.is_mash`) and test messages (`intent.is_test`)
with their social kinds, "Atlas's assistant" identity (CHAT_PLAN decision 76),
the composed capability rundown (`capability.overview`), "what do my notes
cover" (`notebook_stats._coverage`). Tests: `tests/test_composer_owner_1017.py`.

Method per item: reproduce through `/chat/stream` with no model (the
`_ask` helper in that test file; `answer_from: notes, notes_only, use_tools:
false`), write the failing test, fix, verify against a running app, commit.
`pytest tests/test_composer*.py tests/test_reply_variety.py
tests/test_gold_answers.py` is the targeted set; `scripts/gate.sh --staged`
before each commit. House style: no exclamation marks, no em-dashes, sentence
case; every reply family holds 8+ phrasings in both voices.

## Order

1. **Chat and the needle path use Ask's answer engine** (BACKLOG "Composer quality outside Ask"; owner: Ask is great, Guide decent, Chat and needle sub par for web searches, specific note questions, how-to). Route Chat's no-model turns through the same digest; `tool_say` results carry their own sentence of finding (BACKLOG "Tool results are always readable").
2. **Guide intent** (B11, B86; BACKLOG "Guide answers what can I do in the chat"): a query may not relate to the current page; detect intent from the words, not the tab; for "what should I ask" give three to five concrete asks. Files: `ai/help_chat.py`, `ai/help_topics_more.py`, `ai/intent.py`.
3. **Understanding** (B02 residue, B08, BACKLOG "Type tolerance everywhere", "Composer understanding"): fold the owner's typos into fixtures (Brief 90 list), generalise one-edit keyboard slips and run-together words, feed the repaired text to search, tools and commands. Files: `ai/question_noise.py`, `ai/spelling.py`, `ai/composer.py` `rephrase`.
4. **Wording** (B85, BACKLOG 1299): dates ("A week on, by 9 August, you mentioned that you had ..."), past-tense reported speech, then the vendored Harper rules as a test-time lint over composer output and a post-pass (lead capitals, missing articles). Files: `ai/composer_digest.py` (complexity: split rows before adding, `python scripts/complexity.py`), `ai/composer_voice.py`.
5. **Variation and life** (B07): replies composed from parts, not whole stored lines, where a family is still stored; generalise what `capability.overview` does to the other families that read as canned.
6. **Slash commands and natural-language equals commands** (BACKLOG "Slash commands", "Composer: natural language equals slash commands", the palette above the chat input, bare commands guide, creation commands): one registry feeding `/help`, autocomplete and the router; start with `/recent`, `/count`, `/made`, `/untagged`.
7. **Composer does the AI actions when no model runs** (B33, B69): Tag and file, Improve writing, Generate title, Summarise, skills; name them honestly in the UI when the composer did them ("Composer" not "AI action"). Files: `ai/commands.py`, `ai/skill_runner.py`, `frontend/js/ai-tools.js`.
8. **Magic add** (B03, B91-class): reminders' wording and intent through the composer (`ai/magic_add*.py`, grep the CODEMAP).
9. **Digest and patterns** (B83, B84): the composed digest sentences must not render as a button; the "Patterns: university, 4 times since 16 July" chip explains itself and opens the notes behind it. Files: `ai/composer_digest.py`, `ai/insights.py`, `frontend/js/dashboard.js` (grep "Generate this week's digest").
10. **Tool names and ranking** (B48; BACKLOG "Composer ranks the tools the model is offered", "A tool to list the tools"): human names for tool calls ("Read note #65 in full" is fine; "Failed due to error" is not), a ranked toolbox, `list_tools`.
11. **Facts change over time** (BACKLOG): a newer note supersedes an older one on the same fact; `ai/factgraph.py`.

Write `docs/roadmap/agent-remaining/composer-1017-progress.md` (done: hash; next) after each commit. Do not edit CHANGELOG.md, INBOX.md or docs/CODEMAP.md by hand. Final report: five lines.
