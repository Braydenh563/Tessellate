# composer-r5-1108: remaining list

Round 5 of the composer audits (rows left open in `composer-r4-1108.md`). Branch
`agent/composer-r5-1108`. Probed through `/chat/stream` (fixed clock, no model) on the
`tests/_seed_r2_1107.py` notebook plus a Sara, Gym and Atlas set (`tests/_r5_1108.py`), so
some differences from the auditors' answers are seed artefacts.

## Done

- Counting family R3-6, D4: the topic pool was built only for "how many notes about X"
  (`composer_overview._ASKS`), so "number of notes about X" counted the five likest notes;
  "count notes about X" ran the count tool (`act_registry` cue); "how many words in my longest
  note" fell to the notebook total (`notebook_stats.answer`).

- D3: `vocative` stripped "Atlas" as an assistant name before the compare reader saw it; "vs", "versus" and "or ... which" now read as a compare (`composer_tables`).
- D2: `commands._resolve_one` matched titles by prefix, so an exact title that was also a prefix asked "Which note"; an exact title wins.
- E5/D6: `composer_dialogue.follow_on` carries the subject for a question that asks only a property.
- E23: `composer_calc` no longer echoes the answer as its "Read as" line.
- Context leak (coordinator row): `answer` had lost `_isolated` in a split; `tests/conftest.py` resets the digest's context variables per test.
- E22: `_name_said` (my landlord is Your landlord) and `_titled_names` (Tokyo capitalised in two titles) in `composer_digest`.
- D21: `composer_help._short_line` caps the help line a feature word gets.
- R3-35 measured: "tell me about the dentist", "dentist" and the count question now agree (three; Sara seven).
- R3-2: `_names_whose` in `composer_digest._property_lead` (a phone number held by a note that never names the person is not theirs) and `composer_property._HAS_PHONE` ("does Sara have a phone number"). "Sara's number" was already denied correctly. The table, seat and car exclusions were already in `_NOT_PHONE`.
- R3-18 measured: "when is the dentist" leads with "Dentist check-up on 11 November".

## Left (not started or not finished)

- E7 untick (needs an `uncomplete` act beside `task_acts.plan_complete`; today `composer._cannot_untick` says so) and "undo that" after a tick (`composer_help._undo_lead` answers with the keys, the act card already carries Undo).
- D10 multi-tick ("tick email landlord and call plumber" finds no task named the whole phrase) and offers that carry their act.
- E10 per-subject split for "what do I know about Tom and Sara" (one pooled count today).
- R3-20, R3-22, R3-33, D22 (probe: "list my checklists" now answers with two unrelated notes), D19, R3-36, D25 not probed.
- "put it in today's note": parsed as a move of "these" with no target (`commands._no_notes_to_tag_or_move`); needs a design call (append to the daily note, not a category move).
- The r3fix single-list intro-line route.
- "what is the table number" answers a dinner-booking line (no table-plan note in the seed).
