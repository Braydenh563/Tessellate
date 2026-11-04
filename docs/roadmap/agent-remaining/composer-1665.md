# Composer 1665: what is left

- Meaning floor (h): `search_manager.meaning_floor` is tested with synthetic scores only. The owner's 16-record list and the 95% badge on the social skills guide could not be reproduced with the fixture; the badge may show a cosine where the ranked score is a fused rank (check the frontend badge against `match_info`).
- Real-model check: run `scratchpad/llama-dev.sh serve`, then `pytest -m evals`, on the courses question with the model on (CHAT_PLAN decision 75 parity).
- `composer_brief` cuts at a clause break of 12 words or more; a note with no such break is kept whole up to the sentence.
- The "Elsewhere" list was not driven in the app with the fixture; confirm the guide, the party and the joke are gone.
- INBOX 1668 (golf): done are the weak-cue rule and the dating (redate VERSION 3 re-reads wrong stored days). Not done: saying each note's day for "golf notes". Forcing days when notes are 7+ days apart broke the standing INBOX 1441 rule (no day unless the question asks; tests in test_composer_relevance_1310 and test_composer_hobbies_1512), so it was backed out; the owner decides.
