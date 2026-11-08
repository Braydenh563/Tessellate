# Composer round 3 left-overs (agent composer-r3-1108)

Built: R3-6, R3-8, R3-9, R3-14, R3-15, R3-22, R3-23, R3-27, R3-28 (tests in `tests/test_composer_r3b_1108.py`). R3-26 answered correctly on HEAD; pinned by a test only.

Open:

- R3-15: the "[your note, today]" citation (`composer_answer.cite`) of a title-less note is still day-based (design C40, six test files assert it); the Open chip now carries the clipped name (r3fix-1108).
- R3-27: the chips under a narrowed follow-on ("and the flights") are still built from the old ask; the pronoun case ("what does she like" after "what do I know about Sara") still repeats the Anna answer and keeps the old chips. Only the "and <part>" form was fixed (`composer_dialogue._follow_part`).
- R3-22: the "from your list of 7 November" naming variant did not reproduce.
- R3-28: "what is X" now leads with the opening line only for a note titled X; an untitled definition and a "how much" over a quantity (not a price) are unchanged.
- Single-word proper-noun list items are lower-cased by `_sentence_case` ("It also lists three: piranesi, dune and middlemarch").
- "[**your note, today**]" bold versus plain citation across answers is by design within one answer (C40) but reads inconsistent across answers.

Tests whose wording moved with R3-15 (name kept, form changed): `test_composer_cfix_1031` C31 (link text is the quoted name), `test_composer_classes_1026e` C_LABEL_NAMES (the quoted name is an accepted form), `test_composer_frames_1029` (six words, not seven), `test_composer_z_fallback_1030` (fallback listing link text). `test_composer_r3_1107` r3_10 now asks "what do I know about buy" because "shop" no longer joins the "buy" note through a synonym (R3-9). `tests/_composer_eval.py` accepts `name_of(note)` as a term of that note.

Unverified: every check runs on the fake transport and the no-model path; the model-on path reads the same lines but was not run.

## Review fixes (agent r3fix-1108, on 0d32bfd1)

- One name: `composer_frame.name_of` (quoted) over `clipped_words` (bare, for the Open chip and sums). `short_name` is a title, a picture or `name_of`; the diary, label, subject and "the note that starts" forms are gone. A one-line note is never a title (the views never said it was): `heading_title` is a first line over a body.
- `name_of`: "Dr. Smith" and initials do not end a clause, list, task and heading marks are dropped, an empty note is `“An empty note”`.
- Money keeps naming the thing (a subject before its verb: "your phone"; the words up to a figure: "Order"), not quoting it; a name it cannot make is `name_of`.
- Shop and buy: the literal-hit filter in `_members` and `_filed_text` are removed (the tags term was inverted and the join already adds tags). `test_r3_9` no longer asserts the Pixel and perfume notes are absent for "shop" (the reviewer's call: a buy-only note is kept); r3_10 asks "shop" again.
- `_which_list` reads a list with up to two intro lines; counts of a thing no note gives a figure for are "Three of your notes mention phones."
- Not done: "what is on my list" with exactly one list that has an intro line and no "list" in its title still answers "couldn't find anything on list" (the rewrite has to be at the route, two call sites); "what's on my todo" with an intro line did not reproduce the "Nothing in the notes" answer (pinned by a test).
