# writing2-1031 (INBOX 1488: the Writing room with no model)

Branch agent/writing2-1031. Measured with `scratchpad` script outside the repo
(`drafter.composed`, 10 inputs: diary lines, a one-line "I am japanese", bullet
list, numbered steps, a paragraph, a long jargon sentence, typos, a grocery
line, a heading with slang, one tidy sentence; plus Use notes with four dated
notes). Echo = the text came back the same bar spacing or a final full stop.

## Measured before (HEAD): chips and Refine with no model

| Control | Ran | Echoed or barely changed (sim 0.95 or more) | Verdict |
| --- | --- | --- | --- |
| Write up my notes | 10 of 10 | 4 | useful on prose and dated notes; echoed lists; named a note with its whole text; dangling `**.` |
| Carry on writing | 0 of 9 | n/a | needs a model, was on offer |
| Say it plainly | 9 of 9 | 7 | useful only on jargon |
| Bullets to prose | 9 of 9 | 7 | useful only on bullet lists |
| Prose to bullets | 8 of 9 | 4 | useful on 2+ sentences |
| Make a diagram | 6 of 9 | 0 | useful on lists and steps |
| Translate | 0 of 9 | n/a | needs a model, was on offer |
| Refine shorter | 8 of 9 | 4 | useful on prose with filler |
| Refine add a summary | 9 of 9 | 1 | summary of one sentence was the sentence; "Key words" noise |
| Refine as bullets / as a list | 8 of 9 | 4 | as Prose to bullets |
| Refine formal, spelling, tidy, friendlier, conclusion | 0 of 9 | n/a | refused ("needs a model") or unknown |

Sum of echoes or near-echoes: 35 of 77 runs that did something.

## After (same inputs, no model)

Exact echoes (text back the same bar spacing or a last full stop): 0 of every
pass that ran. A pass with nothing to change keeps the draft and says why in one
line (`composer_write.NOTHING_TO_DO`). Runs that changed the text, of 9 inputs
(10 for Write up my notes, which also takes the dated notes):

| Control | Before ran / echoed | After changed / said why |
| --- | --- | --- |
| Write up my notes | 10 / 2 | 9 / 1 (one tidy list: nothing to add) |
| Say it plainly | 9 / 3 | 6 / 3 |
| Bullets to prose | 9 / 7 | 2 / 7 |
| Prose to bullets | 8 / 2 | 6 / 3 |
| Make a diagram | 6 / 0 | 6 / 3 (nothing to draw) |
| Refine shorter | 8 / 1 | 7 / 2 |
| Refine add a summary | 9 / 1 | 4 / 5 (under three sentences) |
| Refine formal | 0 / 0 (refused) | 7 / 2 |
| Refine fix the spelling or tidy it up | 0 / 0 (refused) | 6 / 3 |

Screen (Playwright, port 8837, `room.js` in the scratch dir): no model, 7 chips
(Write up my notes, Tidy and spellcheck, Say it plainly, Make it formal, Bullets
to prose, Prose to bullets, Make a diagram), kind menu 7 rows, tone 3, length 2,
rule line 34 px tall and shown, Refine placeholder names the commands. With the
status poll patched to a model: 7 chips (Carry on writing, Translate back), kind
menu 25 rows, tone 5, length 3, rule line height 0. "I am japanese" with Tidy:
"I am Japanese." Boot gzip total 320,268 to 319,669 (cap 320,600); app.js 14,286
to 14,290 (cap 14,300).

## Done and next

- done: backend 790e8e4 (tidy, formal, no echo, write-up by day).
- done: page (chips moved to writing-desk.js, data-gate options, rule line, help, Guide topic).
- next: nothing open for 1488.

## Found, not fixed

- `tests/test_composer_mermaid_1466.py::test_chat_turns_the_text_given_into_a_flowchart` (the numbered-steps-after-a-colon case) fails on the base commit too: the chat reads "make this a flowchart:\n1. ..." as a mind map.
- A diagram from a plain list roots its mind map on the list's middle item and repeats it as a branch (`composer_mermaid`); a neutral root would read better.
- Say it plainly turns "must approximately purchase" into "must about buy": an adverb between a modal and its verb needs the swap table to know position.
- Writing room: a refused pass leaves the previous pass's "From your words" chip showing (the draft is unchanged, so it is still true, but it reads as if this pass wrote it).
