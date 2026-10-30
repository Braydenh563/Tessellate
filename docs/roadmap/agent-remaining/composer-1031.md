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
