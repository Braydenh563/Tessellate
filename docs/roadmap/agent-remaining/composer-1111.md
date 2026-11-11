# Composer spoke, PR 216 (branch claude/pr216-composer)

Batch from the hub, in order. Update at each step.

## Done
- (1) INBOX 1749 social turns: `ai/composer_remark.py`, `tests/test_composer_remark_1749.py` (see git log).

## Remaining
- (2) Owner answers 2026-11-11 (OPEN.md Q1 to Q8, Q24).
- (3) Composer tests failing on base (test_composer_form_1301 to test_composer_ranker_1029).
- (4) Overview leftovers (`comp1743-1111.md`): the 24-note retrieval cap says "You have 24 notes" for a 30-note topic; more than 40 notes or an undated note takes the framed path.
- (5) OPEN.md W7, W8, W9, W10, row by row.

## Decisions made here (not asked)
- A hello is "formal" only when written out ("good morning", "hello", "greetings"); "hello there", "hey", "hi", "yo", a stretched "hellooo" are casual.
- A turn that names the notebook (note, reminder, task) is never a remark.
