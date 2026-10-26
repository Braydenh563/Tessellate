# composer9-1026 (INBOX 1357: fix the class, not the case)

Eval: tests/test_composer_classes_1357.py (77 cases, 10 classes plus one
invariant on every answer). A failing case is a strict xfail in `OPEN`; a fix
removes its id.

## Owner reports, harvested (INBOX, HISTORY "INBOX resolved", CHAT_PLAN, owner-1026b, archive composer*)

| Class | Reports (owner's words, short) |
| --- | --- |
| A capability question in any wording | 1300 "Wat cna u do??" answered from notes; K20 "whaty can u do??" card's Try line must work here |
| B bare tool or command word | 1334 "timer\" got "Your notes don't mention timer. Which note"; 1333 `/categories` as one prose line |
| C activity recap by window | K20 "should have looked for any notes, documents or boards or maps I used or made or deleted ... show my history"; K20a "what did I do last week?" went to the web; 441 "What have I saved recently?"; 1333 "/today ... nothing written today" with no graphic |
| D note time words said as dates | 1339 "it is not this week anymore like said at the top of the composer" |
| E first, oldest, newest | 1345 "what was the first note I ever wrote?" |
| F boards, maps, documents as sources | 744 "a board must say board and open the board"; 491 picture text not read; K20 kinds |
| G topic answer picks the right note, counts right | 724 "closest match is my gary sketch, even though it is the 3rd match"; 112 grounded the Shakespeare note for bubble tea; 1310 hobbies fragment; 1301 run-on social connections; K30 "a lot more than just the two notes" |
| H nothing found names the thing | 1334; decision 24 |
| I lists of the notebook's shape | 1333 categories as prose; 1324 "five notes" showing one, compare as a table |
| J follow-ups keep topic and window | 741 turn-aware follow-ons; dog2 context bleed |
| K closers state true facts (found here) | the closer said "Your latest note is Hello" (the oldest) under a gym answer; the 1324 fix made it name the cited note but its frames still say newest or latest |
| L AI-only roles | K3 "is it possible to have the composer fill more roles the ai usually would?? like the weekly digest" |

## Pass counts (before -> after)

| Class | Before | After |
| --- | --- | --- |
| A | 9/10 | 10/10 |
| B | 3/10 | 10/10 |
| C | 0/11 | 11/11 |
| D | 1/6 | 6/6 |
| E | 5/7 | 7/7 |
| F | 0/8 | 8/8 |
| G | 4/8 | 8/8 |
| H | 6/7 | 6/6 (one case moved to B) |
| I | 4/7 | 7/7 |
| J | 3/4 | 3/4 |
| all | 35/77 (checks tightened before counting) | 76/77 |

The fixes, each in the shared layer rather than for its case:

- K closers: the closing line says "newest" only of the newest note (`close_cited` frames, `routes_chat._with_next_step`); a cited document resolves in its own table (`_cited_titles`, (kind, id)).
- C recap (K20): `ai/activity.py`, first in `_computed_answer`; `composer_notes._read_recent` defers to it.
- B tool words: `_feature_instead` (a two- or three-word message naming an app feature that is in the help line) and `composer_suggest._app_tool` (an imperative for a tool chat cannot run); reminders listing cue.
- F kinds: `_named_sources` puts a board, map or document named by its title first; `activity.boards` lists boards or maps; `_from_source` and `_your_kind` say a source as its kind; `decap` keeps IaaS.
- D: `composer_digest._pin` says a past "tomorrow" as its date.
- E: `slash._inferred` reads "oldest note" as one.
- I: `realise.named_lead` names every category or tag while six or fewer; `tools._list_categories` counts the notes `_visible` counts (boards were in it); "what's still to do" is the open checkboxes.
- A: `capability._OVERVIEW` takes "even", "actually", "else".
- H: `vocative._tail` keeps a subject word after "about X" ("chromodynamics"); `composer._as_phrase` names the words as one phrase.

## Remaining

- J "what have I saved about the gym?" then "tell me more": answers "That's all your notes say on gym so far". Both notes were already told, so this may be right and the case's check wrong; judge before fixing (`tests/test_composer_classes_1357.py` J_FOLLOW).
- K3, the other AI-only buttons with no composer fallback, in order of use (`data-needs-model` in `frontend/index.html`): `draft-compose` 1876, `draft-title` 1853, the extract buttons (`draft-extract` 1856, `extract-commit` 9493, `doc-extract` 5043, `wb-extract-notes` 7705), `draft-refine` 2035, `doc-ai`/`doc-ai-run`/`doc-ai-instruction` 4934/5629/5626, `chat-plan` 3184, `template-draft` 10687, the code panel's explain, tests and refactor 5427-5435. Recommendation: title (first line or top terms) and extract (one note per paragraph or heading) first; drafting and refining stay model-only with their popover.
- when_words does not read "over the weekend" or "last fortnight" (the recap answers neither).
- "summarise my uni notes" mislabels a map's node as a heading ("**Service models:**"); seen in the dump, not in a class.
- "0 distinct tags" in the stats wording; seen once, not cased.
- Not verified: no browser run of the dashboard's composed digest or the recap's links; the API and tests only.

