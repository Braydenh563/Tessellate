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
| A | 9/10 | |
| B | 3/10 | |
| C | 0/11 | |
| D | 1/6 | |
| E | 5/7 | |
| F | 0/8 | |
| G | 4/8 | |
| H | 6/7 | |
| I | 4/7 | |
| J | 3/4 | |
| all | 34/77 (some passes only because the old checks were loose; tightened before counting) | |

Next: K closers (G, J fail on it), then C recap (K20), B tool words, F kinds, D Also lines, I lists, A, E.
