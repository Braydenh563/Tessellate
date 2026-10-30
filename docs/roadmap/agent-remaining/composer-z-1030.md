# composer-z-1030 (agent composer-z, branch agent/composer-z-1030)

Done: b2bccba (Z1-Z6, Z8-Z10, Z13, Z14, Z44, Z54, Z55; part Z21, Z25, Z33), 13df2e9 (Z15, Z17, Z20, Z22, Z24 part), b404434 (`_since`, K22 start), 07d7194 (Z28, Z29-Z32, Z34-Z38, Z41, Z42, Z45, Z47, Z48, Z50, Z53, K22: user's day in every composer module).
Fixed on the base before this run: Z11, Z12, Z16 (partial), Z18, Z19, Z60, Z65.

Found, not fixed (each needs a decision or a bigger change):
- Z39 (design choice), Z40 (needs a browser), Z49 (pinned by the engine-plan "Read as" test; owner decision), Z50 persona wording for "what is your name".
- Z36 people/places/ideas lists and "find untitled notes" (the find tool answers first); Z37 "show my reminders"; Z45 tight bullets and the "show the rest" chip; Z32 shopping-to-Groceries map.
- Z28 a week's recap is still the creation log; Z22/O11 `_current_notes` drops the Sara note; Z17 "9/10" read as a date, "bought" not folded to "buy"; Z25 oven temperature; Z21 "when did I last" in chat; Z20 "what makes me happy"; Z23 counts and sums of runs; Z26/Z27 past lines listed as upcoming.

Next: Z43, Z46, Z51, Z52, Z56-Z59, Z61-Z64, Z66-Z71, then Z23, Z26, Z27.
Probe: `bash scratchpad/probe.sh <questions file> [1 for chat] [1 for dialogue]` (tests/_zprobe.py, never committed).
