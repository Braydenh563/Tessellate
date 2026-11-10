# Parity agent, 2026-11-10 (remaining list)

Owner order (CHAT_PLAN decision 75): "everything the composer can do, the ai should be able to do", "and vice versa". Source: the Parity tables in `fable-composer2-1110.md` and F14 in `fable-composer-1110.md`. Every row below has a test on both paths in `tests/test_parity_1110.py` (model off is the composer; model on is the fake transport: what the prompt holds and which events come back; what a real model writes is not verified).

## Closed before this agent (marked with the test that proves it)

| gap | proof |
| --- | --- |
| Snooze crashed with a TypeError (G2) | `tests/test_consent_1110.py::test_snooze_the_bins_reminder_is_a_card_not_a_crash` |
| "do I have reminders today", "did I pay the phone bill" gave the model no reminder (G3) | `tests/test_ask_facts_1110.py::test_a_model_is_handed_the_reminders_as_facts` |
| Weekly and daily review, digest prompt without the reminders (G4) | `tests/test_review_digest_1110.py::test_the_digest_with_a_model_gets_the_reminders_in_its_prompt`; chat model on: `test_parity_1110.py::test_the_weekly_review_with_a_model_is_handed_the_week` |
| Guide: greetings, thanks and hand-overs composed with a model up; chips (G5) | `tests/test_guide_lead_1110.py::test_the_model_up_path_keeps_greetings_and_hand_overs_composed`; model chips: `test_parity_1110.py::test_the_guide_with_a_model_lifts_the_questions_it_suggests_as_chips` |
| "what's my name", "call me Sam" (G7, Name use) | `tests/test_address_g7_1110.py::test_a_model_running_answers_the_name_question_the_same` and the card tests above it |
| Counts and sums, today line, remarks, day digest | already equal on both paths (0 model calls measured in the audit) |

## Closed here

| gap | composer (model off) | model on |
| --- | --- | --- |
| Chat chips under a model's answer (F14) | the "Open it" and "What is left in it" chips of a cited note | `chat_turn.model_chips`: the same chips plus any question the model's words suggest; `test_a_model_answer_that_cites_a_note_offers_the_same_chip` |
| Chat greeting facts | `welcome_line` | handed over as facts (`chat_extra.hello_events`); the Ask box keeps its hint (`chat=False`) |
| "what's on today", agenda | the agenda card | `chat_extra.reminder_events` now also lays out the agenda (`composer_plan.answer`) and hands it over |
| Dashboard greeting | composed line with the streak and what is due | `_true_fact` puts the composed line in the model's prompt |
| Weekly digest | composed week | closed above |
| Make a category | "create a category called Hobbies": card, Confirm, Undo (`object_acts.read_make`, act `create_category`) | `create_category` tool needs the same Confirm (`tools.needs_confirm`) |
| Restore the last deleted note | `object_acts._LATEST`, `_binned_latest` | `restore_note` |
| Bin list | "what's in my bin" (`ai/parity_reads.py`) | handed over as facts |
| Earlier chats | "what did we talk about last time", "search my chats for X" (the `search_chat_history` tool) | handed over as facts |
| Export | hand-off to Settings, Import & export | handed over as a fact (no tool exists for it) |
| Notebook shape | "which notes are connected to nothing", "what are the clusters" (cue added to `act_registry.TOOL_CUES`) | handed over as facts |
| How two notes are related | "how are japan trip and kyoto ideas related" (`search_notes` then `path_between`) | handed over as facts |
| Contradictions, writing a document | say a model is needed and where to turn one on (the tool's own words) | the model keeps `find_contradictions` and `create_document`; never told none runs |

Pre-existing failures on the base head, not touched: `tests/test_realise.py::test_variety_floor_over_a_twenty_turn_chat[natural]`, `tests/test_typo_routing.py[call me Sam]`, `tests/test_ask_chips.py::test_a_question_with_no_act_keeps_its_usual_lead`, `tests/test_agent_context.py::test_a_read_is_run_again_after_something_is_written`.

## Remaining (one line each)

- ~~Edit a note's text~~ Built (compleft-1110.md, `ai/parity_acts.py`).
- ~~Turn text into things~~ Built (compleft-1110.md, `ai/parity_acts.py`).
- ~~Run a skill~~ Built (compleft-1110.md, `ai/parity_acts.py`).
- ~~Merge and delete a category, delete a tag~~ Built (compleft-1110.md, `ai/parity_acts.py`).
- Contradictions with no model: the composer only says a model is needed. Dated figures that a newer note replaces could be listed from `ai/supersede.py` (`current`, `older_dates`). "do my notes contradict each other" is read as an imperative and answered "I am not sure how to do that one" (`ai/composer_suggest.py:361` `_IMPERATIVE`). M.
- The model has no tool that lists the bin, so "what's in my bin" is the composer's and the model is handed its answer; a `list_bin` tool would change the "73 tools" numbers in README and ARCHITECTURE.
- Model chips are the cited note's two chips plus lifted questions; the composer's richer `result["next"]` chips are not carried to a model turn (`api/chat_turn.py` `model_chips`, `api/routes_chat.py:1361`).
- Planning, drafting, translating, multi-note summary (`summarize_notes`, G11): the composer says it needs a model; G11 is the other agent's.
- Not driven (still "not verified" in the audit): boards and maps tools, `rename_tag` and `delete_tag` by sentence, `save_user_preference`, `check_learned`.
- Reminders magic add makes "Something sometime" (G14 j, `api/routes_reminders.py:622`): the G10 to G14 agent's.
- Chips and compare code (F5 and F6) and `composer_dialogue.py`: the other agent's; code block colouring: frontend, not touched.
- Not verified: real model inference (every model-on row used the fake transport); the browser; pressing Confirm on the new category card in the page (the route was driven with TestClient).
