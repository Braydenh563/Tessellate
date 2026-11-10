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
- Merge and delete a category: the category's description is not restored by Undo; binned notes in it are not filed back.
- g13 G1 not done: "when did I last see the dentist" (reads the next booking; `composer_slots`, "last" as past), "how far did I run" (`composer_money` goal line), "has the launch date changed". Probed: all three still answer as before.
- g1014 G11 (`composer_amounts` label lookup across notes, "whose birthday is next", note_rank lead), G12 Patterns template (pins in five test files), G14 a, e, f, i and the composed list rows in JS (dashboard.js, statistics.js, reminder-notify.js, avatars.js): not started. The JS rows go in lazy files (boot scripts sit at the gzip cap); each needs a server line.
- s10 F4 (composition layer, INBOX 1353, CHAT_PLAN Phase 5 a to g, "X versus Y"): not started.
- B33 (proper noun lowercased in a quoted line): not reproduced; `composer_digest._capitalised_inside` counts only mid-sentence capitals, titles are not passed to `_begin`.
- B34 ("tell me a joke" against a note titled Jokes): owner decision, skipped.
- Pre-existing red on the base, not touched: `tests/test_ai_name.py`, `tests/test_lazy_bundle_calls.py`, `tests/test_error_toasts.py::test_expected_situations_are_plain_toasts`, `tests/test_no_import_cycles.py` (`core.extras` and `core.languagetool`), `tests/test_static_compression.py` (gzip ratchet).
- Not verified: the browser (the Run the skill card and the Was/Now card items were not driven in Playwright; `node --check` only); real model inference (every model-on row used the fake transport).
