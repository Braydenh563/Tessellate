# Composer spoke, PR 216 (branch claude/pr216-composer)

Batch from the hub, in order. Update at each step.

## Done
- (1) INBOX 1749 social turns and review fixes, CodeQL 2169 to 2179: 3ca4a0c.. af35ef7 (`ai/composer_remark.py`, `tests/test_composer_remark_1749.py`, `tests/test_composer_remark_review_1111.py`).
- (2) Owner answers: Q5/Q6 17d5d14, Q24 c5af6df, Q1 517ee90; Q2, Q7 verified pinned (test_engine_identity, test_composer_cfix_1031:694); Q3, Q4, Q8 already built.
- (3) Base failures: 619bd2f; `test_codeql_shapes` 157af17.
- (4) comp1743: honest pool count 517ee90 (`composer_overview.read_pool`); framed path over 40 notes is by design (`comp1743-1111.md`).
- (5) W9: B29 and B21 built (tests/test_composer_w9b_1111.py), B23 built in batch 2 (below); W7/W10 and W8 rows with agents (see OPEN.md rows).
- Audit rows: 1030 Z7 fixed (`insights._plan_phrase`); 1031-composer C1, C4 stale (rechecked); `audit-1031-code.md` is the code editor (documents), not the composer's.

- Batch 2 (hub, 2026-11-11): base failures (engine_dialogue x3, gold_answers x2, reply_variety x2) fixed at their cause, no test changed, none pins owner-decided behaviour (the woven path is 1743; the plain digest is reached by the fall-back); found-not-fixed: a date's own figures (`source_check._day_gaps`), "are we meeting on Tuesday" (`composer_event_verdict.day_question`), "Rung mum" (`composer_digest._as_you`), latest-on ties (`search_manager._latest_about`, outside the composer's files), "books" count (`composer_likeness._COLLECTIVE`); B23 (`composer_talk._note_offer_sentence`, `task_acts._checklist_items` keeps a quoted item whole); Guide text and `test_manual_parity`; smart-browser design entry in CHAT_PLAN (I4).

## Remaining
- Gather and Track-in-a-table offers cannot be taken up by a typed yes: they carry notes' words the next turn does not hold. Needs the offer sent back with the turn (a server-held id like `consent_store`); small, not started.
- Merge the W7/W10 and W8 agents' branches; strike their OPEN.md rows with shas.

## Decisions made here (not asked)
- A hello is "formal" only when written out ("good morning", "hello", "greetings"); "hello there", "hey", "hi", "yo", a stretched "hellooo" are casual.
- A turn that names the notebook (note, reminder, task) is never a remark.
