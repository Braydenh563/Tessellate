# Composer subject extraction (audit 1029 rank 20)

Built: command verbs and their filler off the subject (`composer._without_command`), whole-stem note lookup (`composer_study._body_matches`), name questions in the "who is" shape (`composer_digest._one_name`), `define X` as `what is X` (`composer.what_is`), instruction words skipped by the missing footer (`composer._INSTRUCTION_STEMS`). Tests: `tests/test_composer_subject_1029.py`.

Remaining, in order:

1. `_one_name`: fixed 2026-10-29. A name the notes travel to, stay in or fly from and never speak with is a place, answered as a topic ("tell me about Lisbon"); a person met or called keeps the who shape (tests/test_composer_place_not_person_1029.py).
2. C15 residue, part fixed 2026-10-30: "the plan for December" keeps the plan (tests/test_composer_topic_owned_1030.py). Was: "compare my running notes and my baking notes" and "tell me about books I am reading" still stem to run/bake/book/read in `_subject`; "what is the plan for December" drops "plan" as an asking word (`_ASKING_WORDS`).
3. Fixed 2026-11-04: `_without_command` strips a command verb wherever it leads a clause (after a comma, semicolon, "then", or "and" before a command's object); a verb inside a clause stays (tests/test_composer_clauses_shape_1104.py).
4. Fixed 2026-11-04: footer frame words also come from the answer shape (`composer_unfound._SHAPE_ASKED`, `_ORDER_SHAPE`: "as a table", "in two snippets", "top three memos", "explain X in a nutshell"); `_INSTRUCTION_STEMS` stays for bare words.
5. Rank 22 (sentence frames) is untouched.
