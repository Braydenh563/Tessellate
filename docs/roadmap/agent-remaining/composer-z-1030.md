# composer-z-1030 (agent composer-z, branch agent/composer-z-1030)

Done: b2bccba (Z1-Z6, Z8-Z10, Z13, Z14, Z44, Z54, Z55; part Z21, Z25, Z33), 13df2e9 (Z15, Z17, Z20, Z22, Z24 part), b404434 (`_since`, K22 start), 07d7194 (Z28, Z29-Z32, Z34-Z38, Z41, Z42, Z45, Z47, Z48, Z50, Z53, K22: user's day in every composer module), c2de394 (Z43, Z46 part, Z51, Z56, Z66), 53a4bb6 (Z52, INBOX 1334 open half: `composer.offered`), 7f37151 (merge of d406a52: composer_sum reads `recognise.measures`; mixed currencies stay with composer_money).
Fixed on the base before this run: Z11, Z12, Z16 (partial), Z18, Z19, Z60, Z65.

Found, not fixed (each needs a decision or a bigger change):
- Pinned by tests that state an owner intent: Z61 and Z62 (the act card label "Remind you on Friday at 9: call the dentist" is INBOX 734, tests/test_acts.py), Z49 (engine-plan "Read as" test), Z39 (design choice), Z63 (a note made by an act is a title-less one-liner by design; the ranking of such notes is a policy), Z40 (needs a browser).
- Z67 fuzzy name pool: "what does Sara want for her birthday" lists Tokyo trip (Nara) and Books; restrict the overview members to notes holding the exact name when the notebook has it (composer_digest overview path).
- Z36 people/places/ideas lists and "find untitled notes" (the find tool answers first); Z37 "show my reminders"; Z45 tight bullets and the "show the rest" chip; Z32 shopping-to-Groceries map; Z50 persona wording for "what is your name".
- Z28 a week's recap is still the creation log; Z22/O11 `_current_notes` drops the Sara note; Z17 "9/10" read as a date, "bought" not folded to "buy"; Z25 oven temperature; Z21 "when did I last" in chat; Z20 "what makes me happy"; Z23 counts and sums of runs; Z26/Z27 past lines listed as upcoming; Z56 "what have I finished".
- Not started: Z57, Z58, Z59, Z64, Z68 (a model-up Ask run), Z69, Z70, Z71, Z46 recast list sentence.

Next: Z57-Z59, Z64, Z67, Z68-Z71, then Z23, Z26, Z27.
Probe: `bash scratchpad/probe.sh <questions file> [1 for chat] [1 for dialogue]` (tests/_zprobe.py, never committed).
