# Composer subject extraction (audit 1029 rank 20)

Built: command verbs and their filler off the subject (`composer._without_command`), whole-stem note lookup (`composer_study._body_matches`), name questions in the "who is" shape (`composer_digest._one_name`), `define X` as `what is X` (`composer.what_is`), instruction words skipped by the missing footer (`composer._INSTRUCTION_STEMS`). Tests: `tests/test_composer_subject_1029.py`.

Remaining, in order:

1. `_one_name`: fixed 2026-10-29. A name the notes travel to, stay in or fly from and never speak with is a place, answered as a topic ("tell me about Lisbon"); a person met or called keeps the who shape (tests/test_composer_place_not_person_1029.py).
2. C15 residue, part fixed 2026-10-30: "the plan for December" keeps the plan (tests/test_composer_topic_owned_1030.py). Was: "compare my running notes and my baking notes" and "tell me about books I am reading" still stem to run/bake/book/read in `_subject`; "what is the plan for December" drops "plan" as an asking word (`_ASKING_WORDS`).
3. Command words are removed only when they open the sentence; "can you please draft ..." works, "draft" after a clause ("and then draft ...") is left.
4. C37 footer words are a fixed list (`_INSTRUCTION_STEMS`); a rule from the answer shape would cover new ones.
5. Rank 22 (sentence frames) is untouched.
