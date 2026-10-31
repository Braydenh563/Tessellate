# composer-1031 (agent composer-1031, branch agent/composer-1031)

Done: INBOX 1459 (was 1453), all four classes: stretched words, frustrated lines and follow-on subjects, the "you're in Chat" line, reminders wished for in passing.
Next: INBOX 1461 (was 1455), a question about an attached note: `src/tessellate/ai/composer_this.py` (new), hooked in `routes_chat._app_first_events`; tests `tests/test_composer_attached_1461.py`.
Then: fable-fix-1030 leftovers Z57, Z58, Z70, Z46 recast, Z23, Z26, Z27, F13 to F15 partials.

Done: 25a533a (INBOX 1459), edefe15 merge.
Next: INBOX 1461 parts: attached-note questions (composer_this.py), time words against the note day, title-less naming, list counts; INBOX 1466 chips.

Done: INBOX 1461 (attached-note questions, time words by register, diary-line names, group "and N more", count once, no hobby on study) and INBOX 1466 first part (digest `next` chips, `composer_digest._next_asks`).
Next: fable-fix-1030 leftovers (Z57, Z58, Z59, Z70, Z46 recast, Z23, Z26, Z27, F13 to F15 partials).

Left, found and not fixed (owner's words, file:line):
- "Booked flights to Lisbon" still named "the Booked flights to Lisbon": a regular past before a bare noun reads as a title (`composer_frame._DIARY_VERB`).
- "the Cloud computing", "the Speed reading tips": a title with "the" and its own capital (`composer_frame._titled`).
- An overview of ten notes says every note inline; the LINES budget is not a fold in Ask (`composer_digest._framed`).
- "Group project meeting moved to Friday": "Friday" is not pinned to the note's own week (`composer_digest._pin`, weekdays are not `_DEICTIC`).
- The stray "[Current Commitments]" bracket (1461) did not reproduce in the server text: every bracket was a markdown link; likely the client's render.
- Awareness closing "I can see you've been working on ..." with no screen; "notes in october" lower case; "list my notes oldest first" fails.
- The model-up path for attached-note questions (dates reach the model via `_note_dates`) is unverified against a real model.

Done: 4cf2cf8 (INBOX 1461, 1466 first part). Then Z26 (past-told lines not upcoming, weekday plus date read as the date: `recognise.told_as_past`, `composer_plan._sentence_day`) and Z70 (no "[Uncategorised]" label in model prompts: `librarian.category_hint`).
Next: Z27 (one due window: `composer_lists._due_window` and `composer_plan` "Coming up, the next 7 days" disagree), Z46 recast ("what's in mum's lentil soup" says one item then "**Also:** Carrots; red lentils; cumin", digest fact path), Z57, Z58, Z23, Z59, F15.

Done: Z26, Z46 recast (a list note asked "what's in", "what goes in", "what do I need for" is answered by its whole list, `composer_digest._named_list`; "what is in my notes about" stays a search), Z70, F15 guard (does not reproduce on head; 20 cases kept as a guard).
Left for the hub (not started): Z27 one due window, Z57, Z58, Z23, Z59, F13 and F14 partials.
Pre-existing, not mine: `tests/test_ask_focus.py::test_a_greeting_gets_a_hint_not_an_answer` reads the real clock ("Good night") and fails at base 301e03c too.

## composer2-1031 (agent composer2-1031, branch agent/composer2-1031)

Done: 5c0892e (item 5: the Ask greeting test failed at every hour, not by the clock: the Z71 stand-in added a welcome after the hint; fixed, test on a fixed clock with five greetings).
Done: items 1 to 4 (register table with echo, "ago" and "distant" rows; no article before a title; overview summary line and fold; weekday pinned to the note's week) in `composer_digest._SAY_WHEN`, `_echoed`, `_summary_names`, `_pin_weekdays`, `composer_frame._titled`, `_DIARY_VERB`.
Next: Z27 one due window (`composer_plan._due_reply` default 7 days vs `composer_lists.window_of` 14; "soon" leftover sends "what's due soon" to lists), then Z57, Z58, Z23, Z59, F13/F14.
