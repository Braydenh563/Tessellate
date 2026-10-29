# Composer ranker and slot-first answers (audit 1029 ranks 18 and 19)

Built: `ai/note_rank.py` (one ranker: exact title, defining note, title holds the subject, rest; newest first inside a tier; `recency` for "latest about X" and counts) and `ai/composer_slots.py` (did-I with a tick verdict, what is left on a named list, how long since from a dated line, compare the two X notes), then a slot table (`SLOTS`: temperature, date, quantity with a unit) with a `_value` reader beside `_did`, so a value question is answered by the sentence that holds the value or says none does and cites the nearest note (C21); verb and noun synonym pairs (`composer_tables.VERB_NOUN_PAIRS`, C21); how often by notes titled or tagged and how old by the note's start date (C23); kind questions, "which notes have checklists / dates / lists" and "open checklist items" (`composer_lists.holding_ask`, `list_pool`, C34). Tests: `tests/test_composer_ranker_1029.py`, `tests/test_composer_slots_1029.py`, `tests/test_composer_slots_1029b.py`.

Remaining, in order (items 1 to 4 are built, above; numbers kept):

5. C36: "compare sourdough loaf one and two" (prefix expansion: "sourdough loaf" + "one", "two"), "how are Deep Work and The Overstory different" (a `compare_sides` pattern), "which is longer, the budget or the Lisbon trip" (state both lengths), "what changed between the two".
6. C33 residue: "what do I need to do before the Lisbon trip" with no task list in the trip note falls through to the generic list lens; it should say which notes hold dates or tasks for the trip.
7. `composer_plan._until` prefers the exact-title note only when it counts down to a later day; a Dentist note dated today still loses to a later "Dentist booked for Friday" line (kept for `test_plan_phrasings`).
8. C47 (one confirmation template, no ids shown) was not started.
