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

## Built (when_words, this agent)

- The this/last/past N unit forms, weekend, fortnight, since X, earlier this X, so far, to date, the other day and the part-of-day words read as spans in `ai/recognise.py`; 187 class phrases went from 47 to all passing, recap cases 5 to 15 of 15, L_NAMES 3 to 5 of 5. Feature fallback ignores a help line's examples (`tests/test_feature_instead_class_1026.py`).

- A map node or board card "Label: text" is its own text, not a heading (`composer_digest._node_split`; `tests/test_source_structure_1026.py`, 30 cases, 16 failing before). Found, not fixed: a map is read flat (parent and children as siblings, "lists four: service models, IaaS, PaaS and SaaS"); a board or map is not searched unless named ("tell me about IaaS" finds nothing).
- Count wording (zero, one, many) in `ai/notebook_stats.py`: `_plural(0, ...)` is "no ...", agreement for one, and "Every note has a tag" where nothing is true of none; `tests/test_count_wording_1026.py` (17 questions x 0, 1, 3 notes; 27 of 60 failing before). Found, not fixed: "how many notes are not linked" answers the note count; "how many notes are tagged work" with no such tag answers the tag count.

## Built (composer9 work list, this agent; tests/test_composer_classes_1026b.py, 49 cases; before the fixes M and N failed 11 of 14, R 8 of 9, Q 12 of 16 by probe; all 49 pass after)

- 1 Sources: `routes_chat._matched_rows` puts boards, maps and documents whose words hold the question's topic words first-class in retrieval (the one search index, then every topic word checked in the text); `created_at` on board rows so supersede does not drop dated notes; `composer_digest._best` breaks ties by search rank. Classes M (9), P (3).
- 2 Hierarchy: `Sentence.depth` and `ai/composer_tree.py` say a map or outline as parent: children (class N, 5).
- 3 Counts: `ai/notebook_filters.py` (link state, tag, category, window; a missing tag or category named with the nearest) and boards/maps counts in `notebook_stats` (class Q, 16).
- 4 Told by source: `routes_chat._told_sources` re-reads the earlier questions' grounding rows so "tell me more" skips by place, not wording (class O, 7); the "when" cue is the recogniser's, not a month pattern.
- Found, not fixed: pinned, archived, checklist and reminder counts ("how many notes are pinned" answers the total); "how many work notes" with no such category answers the total; the stats windows read `utcnow()` while the app reads `user_now` (tests patch `notebook_stats.utcnow`); item 5 built (ranges, "recently" 14 days, "this weekend" past; class R, 9 cases); seasons (spring, summer, needs a hemisphere from the locale), "first week of October" and "start of the month" not read.

## Remaining

- J gym "tell me more": judged, the code is right. The first answer already told both notes whole, so "That's all your notes say on gym" is true; the case now checks that (and a second, the essay). Found, not fixed: "what have I saved about uni?" then "tell me more" re-tells the timetable, because the first answer worded it differently from the note (told-tracking is by wording, not by sentence).
- K3 done (see Built below): title and the extract buttons work with no model; drafting, refining, doc-ai, plan, template draft and the code panel answer a press with why and Set up a model.
- when_words done (see below): the class is `ai/recognise.py` readers, cased in `tests/test_when_class_1026.py` (187 phrases, three ways each) and K_WINDOWS. Found, not fixed: "this weekend" is ambiguous in the past tense, ranges ("from Monday to Wednesday") and seasons are not read, "recently" and "lately" stay as they were.
- Not verified: no browser run of the dashboard's composed digest or the recap's links; the API and tests only.

