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
Done: Z27 one due window (`composer_plan.AHEAD_DAYS`, `ahead_default`, read by `composer_lists.window_of`; "soon" is filler), Z59 learning reader and ask (`personal.py`; `routes_chat._personal_unsearched` when search finds none), streak said as "writing streak"; hub gold fixes (name keeps its capital in `_fragment` via `_a_name`; part-of-day weekday not pinned; summary outside the told budget).
Next: Z57 plan-the-week spread (`composer_plan.py` near 466), Z58 compare picks and relations (`composer.compare_sides`), Z23 how often / how many counts events and sums units (`composer_slots.py` 490 to 528), F13/F14 partials.
Found, not fixed: (1) gold `test_hashtags_and_today_are_tidied` expects the pottery note undated ("You trimmed your first bowl."), the owner's newer 1461 decision says date and distance; the hub decides, test left unchanged. (2) `test_composer_today_1030::test_no_composer_module_reads_the_servers_clock` fails on `composer_write.py:623` (`date.today()`, from 9136ec2, writing room), not this agent's file. (3) "show me my study notes" and "what do my notes say about university" route to a fact, not the overview. (4) The closing "Since you've been in “I just missed...” lately" quotes a line as a place. (5) "Here is the answer." lead on some list replies. (6) "myers chapters" lower-cased in a fragment.
