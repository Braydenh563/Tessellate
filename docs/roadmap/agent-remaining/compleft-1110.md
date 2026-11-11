# compleft-1110: composer leftovers (consent2, parity, g13, g1014, left, s10, s58left)

Done (see `git log`):

- consent2 left item 1: an unworded card (starter, model proposal, typed yes on a tool call) is confirmed in the composer's frames (`acts.plain_say`, `acts.done_line`, `tests/test_consent_voice_1110.py`).
- parity: delete or merge a category, delete a tag, replace a note's text (Was and Now on the card), open checklist lines to reminders (asks when, never guessed), run a skill; Undo for the category delete and merge (`move_notes`, now runnable) and the tag delete (`tag_note` batch); model tools already park for Confirm (`tests/test_parity_acts_1110.py`, `ai/parity_acts.py`). The skill hand-over, from the composer or the model, now shows the plan card ("Run the skill" / "Not now") before the run (`chat-turn.js`, `planProposalCard`).
- left-1110 F13 j: "what links to the dentist note" (`composer_openlinks._NAMED`); B31's "which notes link to Mum" when a note has that title.
- g1014 G10: "call mum on sunday about christmas plans" (`commands._BARE_CALL` takes a day or about; `recognise._names_a_topic`).
- Voice: "Last weekend, you wrote four notes:" (`composer_lines` recent_any).

Left, one line each:

- A typed yes does not reach the skill and plan cards (only a press does): they are page cards, not parked server cards (`ai/consent_store.py` parks act and confirm cards only).
- "make reminders from my todo note": the sentence normaliser turns "todo" into "to do" before the note is looked up, so a note titled Todo is not found by that word (`commands.read` upstream of `parity_acts`).
- Edit text replaces the whole body (heading kept); an in-place find-and-replace ("change Bluegum-5G to 6G in the wifi note") is not built.
- (done in compleft4: category Undo restores description and binned notes; find-and-replace built.)
- g13 G1 not done: "when did I last see the dentist" (reads the next booking; `composer_slots`, "last" as past), "how far did I run" (`composer_money` goal line), "has the launch date changed". Probed: all three still answer as before.
- g1014 G11 (`composer_amounts` label lookup across notes, "whose birthday is next", note_rank lead), G12 Patterns template (pins in five test files), G14 a, e, f, i and the composed list rows in JS (dashboard.js, statistics.js, reminder-notify.js, avatars.js): not started. The JS rows go in lazy files (boot scripts sit at the gzip cap); each needs a server line.
- s10 F4 (composition layer, INBOX 1353, CHAT_PLAN Phase 5 a to g, "X versus Y"): not started.
- B33 (proper noun lowercased in a quoted line): not reproduced; `composer_digest._capitalised_inside` counts only mid-sentence capitals, titles are not passed to `_begin`.
- B34 ("tell me a joke" against a note titled Jokes): owner decision, skipped.
- Pre-existing red on the base, not touched: `tests/test_ai_name.py`, `tests/test_lazy_bundle_calls.py`, `tests/test_error_toasts.py::test_expected_situations_are_plain_toasts`, `tests/test_no_import_cycles.py` (`core.extras` and `core.languagetool`), `tests/test_static_compression.py` (gzip ratchet).
- Not verified: the browser (the Run the skill card and the Was/Now card items were not driven in Playwright; `node --check` only); real model inference (every model-on row used the fake transport).

## compleft2 (second pass)

Done:

- "turn my todo note into reminders": the lookup tries the title as typed (`parity_acts._source_note`).
- A typed yes or no reaches the Run the skill and Run the plan cards: `consent.attach` parks the hand-over (`ask_label`, `consent_id`), `chat_agent.consent_events` replays it with `consented` and settles the card, `planProposalCard` and `chat-turn.js` carry the id (`tests/test_consent_cards_1110.py`; the skill event test in `test_parity_acts_1110.py` now ignores the two added keys).
- g13 G1: "when did I last see the dentist" (`composer_digest._behind_if`), "has the launch date changed" (`supersede.changed`, `routes_chat._changed_line`), "how far did I run" already excludes the goal line (`tests/test_ask_facts2_1110.py`).
- g1014 G11 label lookup: "which is cheaper, free or plus", "how much more did I spend eating out in october" (`composer_amounts._which`, `_more`).

Left:

- Not started: g1014 G12 Patterns template (five test files pin it), G14 a, e, f, i and the JS composed rows, s10 F4 "X versus Y" (composition layer, `composer.compare_sides` before the digest), "whose birthday is next".
- The tiers case needs lines of "Label number"; a prose line ("Plus tier at $5 a month") is not read by the label lookup.
- Not verified: the browser (a typed yes starting a skill from the page was not driven in Playwright; `node --check` only), real model inference.

## compleft3 (third pass)

Done:

- "whose birthday is next": one birthday answers ("Anna's is next, on 3 December, 23 days away"), "who has the next birthday" and "when is the next birthday" read it, "Birthday: December 3" and "the 9th of February" are read (`composer_figures._birthday_of`, `_BIRTH`; `tests/test_birthday_next_1110.py`). A model up is handed the note and its distance in the prompt; the figures reader is not a facts turn (`chat_turn._facts_turn` takes stats and tool reads only), so the model writes this one from the notes.
- g1014 G12 Patterns template: "Golf has come up four times since 5 September, three of them after work; that may be a hobby forming." (`composer_tables.INSIGHT_TEMPLATES["recurrence"]`, `insights._shown`), the hedge said once in a list (`insights.listed`, used by `chat_extra.notebook_events`). Pins moved with it: `tests/test_insights.py` (sentence; the capital-start copy rule now accepts the subject slot), `test_engine_phase6_spec.py` ("four times"), `_composer_eval.py` (fills the template through `insights.shown`), `test_composer_cfix_1031.py` (reads "has come up N times" so the one-count check does not go vacuous). `tests/test_patterns_g12_1110.py`.
- s10 F4 "X versus Y": `composer_amounts._VERSUS` ("A versus/vs/compared to/against B") sets two notes of "Label number" lines side by side (differences, then what is the same), reads a line of sentences ("Rent 650. Groceries 140.") only for this ask, and gives two labels of one note ("free versus plus") with the gap (`tests/test_composer_versus_f4_1110.py`). Read-only, so no consent; a model with tools reads both notes.

Left:

- G14 a, e, f: probed again on the audit notebook with reminders seeded and still not reproduced ("what are my reminders" is a two-column table; "what do I know about harbor" says four and lists four, then "More loosely related to harbor"; the "Ask" chips for "the harbor launch" come back with no offer on this path). Need the owner's real notebook.
- G14 i and the composed list rows in JS (`dashboard.js:526`, `:633`, `:3018`, `:4229`, `statistics.js:121`, `reminder-notify.js:92`, `avatars.js:2731`): not built. Dashboard, `statistics.js` and `avatars.js` are boot scripts and `tests/test_static_compression.py` is already red on the base, so each byte must be won back; and the page's dates follow the reader's locale (`whenText`, WORLD_CLASS_PLAN "every date and time follows one setting") while composed text is English day-month, so "one formatter" is an owner decision (locale versus fixed English) before it is code.
- F4 beyond labelled notes: "harbor versus japan" (topics of several notes each) still prints two columns with the ranker's lead, not the defining note (`composer_body._compare`, `note_rank.lead`); the tiers case still needs "Label number" lines (a prose line "Free and Plus at $6 a month" is not read).
- "what's most important right now" still unrouted.
- Not verified: the browser (no JS changed), real model inference.

## compleft4 (fourth pass)

Done: items 1, 2 and g13 G1 were already built in compleft2 (verified by their tests); in-place find-and-replace ("change Bluegum-5G to 6G in the wifi note", `parity_acts._find_replace`, Was/Now card, Undo); category delete and merge Undo restores the description and files binned notes back (`categories._filed_back`, `move_notes` `include_binned`/`description`).

Left: not verified in the browser; real model inference (fake transport only). Find-and-replace matches the text as typed (case-insensitive only when no exact match) and needs the note named "... note".
