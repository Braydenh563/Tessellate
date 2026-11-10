# Composer audit, 2026-11-10: conversation, voice, follow-ons (INBOX 1729, 1730)

Read-only. Head: `claude/next-queue-1102`. Method: `/chat/stream` through TestClient (no model, `client` fixture), fixed clock Tuesday 10 November 2026 09:00, a seeded notebook of 36 notes (6 title-less, 1 title-only, near-duplicates: two budgets, two dentist notes, four Harbor notes, four Japan notes; a defining note per topic). History sent as the page sends it: last four turns, `objects` from the sources, `pending_act` from an open card.

Driven: 85 dialogues, 469 turns with no model, plus 18 turns with the fake model up. Every answer read. Harness and raw answers (not in git): `/tmp/claude-0/-home-user-Tessellate/4f1165b8-dfbe-57d9-b2ee-276812e0a5f3/scratchpad/probe/` (`seed.py`, `probe.py`, `d1.json`, `d2.json`, `out1/`, `out2/`, `show.py`). The seed and dialogues are worth keeping as the 1730 (d) eval.

Numbers over the 469 no-model turns:

| measure | count |
| --- | --- |
| answers that end with the subject-blind chips "What did I write this week?", "Notebook statistics", "What can you do?" | 72 |
| answers with no chip at all | 97 |
| answers carrying a `**Also:**` block | 80 |
| answers citing with the bracketed `[**Title**]` (decision D25 says it goes) | 57 |
| answers that end by naming the words it could not match ("None of these notes mention “very” or “helpful”") | 30 |
| answers that are the previous answer again, character for character | 9 |
| the notebook overview given for a question that only contains "stats" or "statistics" | 8 |
| "That's general knowledge" said to a follow-on about the person's own notes | 6 of 7 uses |
| "Your five newest notes" given to a short reply ("really?", "by how much", "maybe", "and then") | 6 |

Single questions with a named subject mostly work ("when is the car service due", "what's her number", "how long until the japan trip", "have I booked flights"). The second turn is where it breaks: in the 20 dialogues a01 to a20, 61 of 104 later turns were wrong, off-subject, or a non-answer (hand count).

## Coverage

| area (CODEMAP rows) | state |
| --- | --- |
| `composer_dialogue.py` (35) | driven (28 direct `follow_on` probes, all dialogues) and read |
| `composer_talk.py` (29) | driven (chips on every turn, chart follow-ons), read 30 to 170, 255 to 382 |
| `composer_smalltalk.py` (12), `composer_social.py` (12), `question_noise.py` (49), `repair_turn.py` (5) | driven (b01 to b12, a09, a18, a36, a46, a47); `social_kind`, `is_repair` probed on 21 inputs |
| `personal.py` (26) | driven; `general`, `_SELF` read |
| `notebook_stats.py` (66) | driven; gate and `_whole_notebook` read |
| `composer_plan.py` (58) | driven (due, today, week, month, plan, until); `_note_days`, `_item_chips` read |
| `composer_digest.py` (362), `composer_frame.py` (53), `composer_threads.py` (25), `composer_body.py` (65), `composer_tables.py`, `composer_lines.py`, `composer_phrases.py` | driven through every answer shape; read only at the lines cited |
| `composer_versus.py` (23), `composer_slots.py` (81), `composer_study.py` (42) | driven (compare, summarise, open); not read beyond cited lines |
| `commands.py` (117), `task_acts.py` (50), `acts.py`, `act_registry.py` | driven for add, remove, tick, delete, rename, move, remind, undo, new note; `_delete` read. Confirm cards were not pressed (no browser) |
| `composer_chip_subject.py` (7), `composer_follow.py` (10) | driven; chip text read in output only |
| `composer_voice.py`, `composer_write.py`, `composer_mermaid.py`, `composer_money.py`, `composer_calc.py`, `reading.py` | not reached beyond one or two turns each (maths, "summarise"); out of this brief |
| Browser (chip rendering, Stop, regenerate, 390 px, dark, keyboard) | not reached: route probes only |
| Model on (decision 75) | 18 turns against the fake transport only; real inference not verified |

## Findings, ranked by owner impact

Each has exact turns, the cause, and a fix sized for one Sonnet step. "Overlap" marks W9 rows another agent is building.

### F1. A follow-on is word surgery on the previous question, not a reading of what the last answer showed (high, ai)

The only state a turn carries is the previous question, the answer text and up to five titles. `composer_dialogue.follow_on` (`composer_dialogue.py:275`) pastes a word from the old question into the new one and searches for the result. Direct calls:

| turns | rewritten as | what the owner saw |
| --- | --- | --- |
| "how much is the budget" then "and kyoto?" | `how much is the kyoto` | the budget answer again, character for character |
| "when is her birthday" then "what does she like" | `what does anna's birthday like` | leads "Anna's birthday is 3 December"; the answer sits third in Also |
| "when is my dentist appointment" then "who is it with" | `who is dentist appointment with` | "You wrote: Dentist said floss more, next clean in six months. cost was $180" (wrong note; the answer "Dr Patel" was in the answer above) |
| "summarise it" then "what about yesterday" | `summarise first yesterday?` | "Your notes don't mention “first”. Want to try a different word?" |
| "what do I do if it stops working" then "thanks that's all" | `thanks stops working's all` | "Router is in the hallway cupboard. [**Wifi**] None of these notes mention “stops” or “working”." |
| "are you sure" then "where did you get that" | `where did you get sure` | "I couldn't find anything on “sure”. Could you put it another way?" |
| "when is she visiting" then "remind me about it a week before" then "what about mia" | subject `it about Mia before` | "On it about Mia before you've written two notes, 3 September to 6 November." |
| "and mia" then "when is that due" | `when is mia due` | "You noted this date: Her birthday is 9 February. [**Mia**]" |
| "the first one" then "and the other" | chart reader | "Here are your notes per tag. I can also draw notes per category or per weekday." (`composer_talk.py:40` `_BARE_OTHER`; line 109 marks any dated question as having shown a chart) |

Not recognised at all (`follow_on` returns None, the turn is searched cold): "who am I going with", "and the week before", "which is higher", "by how much", "how many days until then", "what temperature", "how long", "how fast", "have I read it?", "which comes first", "really?", "times 12", "add butter", "go back", "what else is coming up in december".

Cause: `_follow_pronoun` (`composer_dialogue.py:558`), `_follow_swap` (453), `_follow_window` (376), `_carried_source` (534), `_standing` (309). The readers know the old question's words, never the note, entity, date or list the answer was built from.

Fix (the class), three steps:
1. A turn frame. Each composed reply already knows its notes, entity, slot, dates and list items. Emit `frame = {kind, subject, note_ids[<=5], entity, slot, dates[], items[<=12 {text, note_id, kind}], window, act}` on the `grounding` (or `done`) event; store it on the turn in `chat-turn.js:1062` and `ask-compose.js:1201`; accept it as `ChatTurn.frame` (`chat_request.py:70`, capped, ids re-checked against visible notes server-side: it is client input). conv-1110's remaining list asks for the same thing as `shown`.
2. Bind before searching. A turn with a pronoun, "the first/other/pricing one", or no subject of its own is answered from `frame.note_ids` first: run the slot question ("who", "where", "how much", "what does she like") over those notes only, and fall back to search only when they hold nothing. No words are pasted into the question. Interim without step 1: restrict candidates to the notes named in `last.objects` (already sent).
3. Bare slots. "what temperature", "how long", "what room", "where", "how fast" after an answer are slot asks on `frame.note_ids`, not searches for "temperature".
Test: the nine rows above plus the fifteen unrecognised asks, each asserting the cited note and the lead sentence.

### F2. Any question containing "stats" or "statistics" gets the notebook overview (high, bug)

- "when is the stats exam", "what's the stats exam worth", "when is the stats exam on", "statistics lecture", and a 35-word question that mentions the stats exam all answer "You have 36 notes in 9 categories, 20 May to 10 November. Most of your notes are filed under Life, with 8. ..." First turn, no history. "um when's the exam again" answers correctly, so the note is findable.
- With the fake model up the Statistics tool card is attached to the same question.
- Cause: `notebook_stats.py:229` (the gate) and `notebook_stats.py:340` (`_asks(text, r"\bstat(?:istic)?s\b")` in `_whole_notebook`): the word alone is enough.
- Fix: the overview only when "stats/statistics" is the subject: the whole message is the word, or it follows show/open/my/notebook/note with nothing after it but a filler. A noun after it ("stats exam", "statistics lecture 2") or a when/where/who lead means a note question. conv-1110 saw the mirror case ("show my statistics" read as a note search): one rule fixes both. Test: the five asks above and "statistics", "show my statistics", "notebook stats".

### F3. After a list or an act, the next instruction does not know what it is acting on; two readings propose deleting a whole note (high, bug)

| turns | answer |
| --- | --- |
| "what's on my shopping list" then "add butter" | "I could not tell which note to add, or what to change. To add a line to a note, say it like this: add buy chalk to the gym note." |
| then "and cheese" | "I did not catch what “and cheese” was after. Should I look in your notes?" |
| then "remove milk" | "Move the note “Shopping” to the bin. Confirm to do it." |
| "what reminders do I have" (one reminder, "Call anna") then "delete the first one" | "Move the note “Call with Anna” to the bin. Confirm to do it." |
| "what do I need to do" (six items listed), "which is most urgent", then "mark the first one done" | "I do not have a list in front of me to count from. Name the task, like: tick buy stamps." |
| "new note called packing list" then "add socks to it" / "rename it to Japan packing" | "Which note do you mean? Attach it with the paperclip, or name it, like: delete the boiler note." (twice) |
| "remind me to call anna tomorrow at 5" then "make it 6" | "Call with Anna wants to try the new ramen place, written a week ago, on 1 November." |
| "when is my dentist appointment" then "remind me the day before" | "When's good for a reminder about the day? Tomorrow at 9, Friday afternoon, in an hour?" |
| "when does the rego expire" then "remind me a week before that" | "What time should I remind you about a week before that?" |
| "what does my car service note say" ... "move it to the 16th" | "Move 1 note about “Car service” to 16th (a new category). Nothing changes until you press Confirm." |
| "note: bought new running shoes, $140" then "add that to my running log" | "Add “That” to the end of “Running log”. Confirm to do it." |
| "delete it" (card open) then "undo" | the Help text for Undo, not the act (overlap B24) |

Causes: `commands.py:844` `_delete` takes "remove X" and matches X against note bodies (`_one_target(rest, bare=True)`); `task_acts.py:761` `NO_LIST` reads only the turn directly before; `commands.py:1797` has no "it" from the previous act; the remind reader does not resolve "the day before" / "a week before that" against the date the last answer gave; `commands.py:1597` reads "the 16th" as a category.

Fix: with F1's frame, `items` and `act` answer all of these. Without waiting for it: (a) "remove/delete X" where X is a line of a checklist note, or the previous answer was a list, is a line removal (never a note deletion by body match; a note is binned only on a title match or an explicit "note"); (b) "add X" / "and X" with no target after a list answer adds to that list (owner decision 2026-11-10: list adds happen at once with Undo); (c) an ordinal is counted against the last answer that showed a list within four turns, and against reminders when that answer was the reminders table; (d) "it" after a created, opened or named note is that note; (e) "make it 6", "actually 9am" after a reminder was set or asked for changes that reminder; (f) "the day before", "a week before (that)" take the date in the last answer and name the subject ("Remind you on 20 November about the dentist check-up?"); (g) a day ordinal after "move it to" is a date, not a category.

### F4. Social turns and turns about the last answer are searched as notes (high, ai; the owner's "social skills")

| turns | answer |
| --- | --- |
| "hi" then "how are you" | "This is how you put it: Feeling pretty tired today, slept badly. need to prep for the stats exam this week [“feeling pretty tired today, slept badly”]" (alone, "how are you" answers "Steady and ready. How are you getting on?") |
| then "what can you do" | "Your own words: Feeling pretty tired today, slept badly. ..." |
| "thanks for listening" | "Your notes don't mention “listening”. Which note might it be in?" |
| "you're not very helpful" | "Jr pass is not worth it under 7 days apparently. sam says get a suica card instead [“jr pass is not worth it…”] It looks like these notes omit “very” or “helpful”." |
| "i feel sick" | "Much appreciated. Anything you want to look up?" (`social_kind` says `compliment`) |
| "yep" then "nope" | "Sorry, I took “yep” for small talk. What were you after?" |
| "i can't focus" | "Your notes don't mention “focus”. Do you remember roughly when you wrote it?" |
| "i'm stressed about the exam" | "... No note found brings up “stressed”." |
| "i love you" | "On love you've written two notes. **How it went:** you loved the House and the tides; the ending felt rushed. ..." |
| "i miss anna" | "... Did you mean **Call with Anna** or **Anna**?" |
| "say that again" | the notebook overview again (after F2), or `say harbor launch again` searched |
| "shorter" / "more detail" after "summarise my harbor notes" | the same three paragraphs, headed "3 notes match. The short version of each:" both times |
| "in one sentence", "in bullet points" | "I did not catch what “in one sentence” was after. Should I look in your notes?" |
| "give me the short version" | "I am not sure how to do that one. Cool how? Here are some things worth trying, or tell me what you are after." (`composer_suggest.py:294`; the comment at 157 says this was fixed) |
| "are you sure" | "Not sure what you mean by “are you sure”. Do you want your notes on it, or something else?" |
| "what did you just say" | "This is what you saved: Idea: an app that reminds you to water plants ..." |
| "do you remember what I asked before" | "I am not sure I can do that exactly. The closest I can do is to set a reminder. Want one of those?" |
| "what should I ask" (after the dentist answer; the note says "Ask about the night guard") | "Short version: I'm Atlas. I also set reminders, tag, pin and move notes, and work out sums." |
| "what do you think" | "This is Atlas's assistant speaking. With no model running I answer from your notes in their own words." |
| "really?", "maybe", "and then" | "Your five newest notes, from 7 November to today: ..." |
| "can you learn" | "It doesn't say exactly, but the closest is: Piranesi [**Reading list**] ..." |

Causes: `question_noise.social_kind` is a closed word list tried before and after the follow-on reader in an order that lets a pronoun or a carried subject win (`composer_dialogue.py:288` drops social turns from history but the current turn is still rewritten); nothing reads a turn about the answer itself; `personal.py:380` to `399` and `composer_phrases.py:154` are the fallbacks.

Fix: one "about the conversation" reader ahead of retrieval, with four small classes: (a) meta on the last answer: again/repeat (resend it), shorter/in one sentence (lead sentence only), more detail/in bullets (the full note as bullets), "are you sure"/"where did you get that" (the source note, its date and the quoted line), "what did you just say"/"what was my first question" (from history); (b) feelings and second-person remarks ("i feel ...", "i'm ...", "i can't ...", "you're ...", "thanks for ...", "i miss/love ..."): acknowledge in one line, then offer one thing tied to the subject if a note fits ("The exam is on 24 November, two weeks off. Want the list of what it covers?"), never a quote dump and never "No note found brings up “stressed”"; (c) bare reactions with no content word ("really?", "maybe", "and then", "hmm ok") never reach search or the newest-notes list: a short reply plus the last subject's chips; (d) "sick/ill/unwell" out of the compliment list, and a "no/nope" after an ack is not a repair of it. Test: the 21 rows above.

### F5. The chips do not continue the conversation (high, ux; the owner's "buttons I could click to proceed")

- 72 answers about a named subject end with "What did I write this week?", "Notebook statistics", "What can you do?" (`composer_talk.py:329`, the default of `acts_for`). Seen under "when are the flights", "what does she like", "when is it" (the exam), "where" (the car service).
- 97 answers have none: every small-talk reply, every clarifying question ("When should I remind you to call ana?" has no time chips), every act card, "Nothing is overdue."
- Chips built from the question's words are often not English: "What else have I saved about the Kyoto?", "When did I write about finish piranesi?", "What is the latest on read?", "What's the latest on badly?", "When did I write about Priya working?", "When did I write about revise?", "What is the latest on great run?", "Remind me about feeling pretty tired today, slept badly today", "Open the feeling pretty tired today, slept badly note" (`composer_dialogue._next_questions`, line 91; `composer_chip_subject.clean`, line 65; `composer_plan._item_chips`, line 467).
- Chips loop. Walk a21: "What's the latest on the japan trip?" then "What else have I saved about the japan trip?" returns the first answer again, and offers the first chip again; five presses, two distinct answers. Walk a22: "What's the latest on Harbor?" and "When did I last write about Harbor?" give the same text, and the second never states a date.
- A chip after a list is one "Open “Title”" for the first row only (conv-1110 left this).

Fix: chips come from the frame (F1), by answer kind: a fact answer offers the note's other facts as questions ("Who is it with?", "What should I ask?"), a dated answer offers "Remind me the day before" and "What else is on that week?", a list answer offers per-row picks and "Add to this list", a person answer offers "When is her birthday?", "What did we last talk about?", a clarifying question offers its answers ("Tomorrow at 9", "Friday afternoon", "In an hour": the sentence already lists them). Rules: a chip already pressed in this chat, or one whose answer was already shown, is not offered again; a chip's subject must be a title, tag, entity or noun phrase from the notes, never a verb or adverb from the question; the generic trio only on a first turn or after a stumped turn. Eval: press every chip of every answer in the 85 dialogues once; none may be stumped, repeat an earlier answer, or fail the grammar check.

### F6. Comparing, counting and sums over what was just shown are refused or searched (med, ai)

| turns | answer |
| --- | --- |
| "compare october and november budget" then "which is higher" | "That's general knowledge, and with no model running I only know what your notes say, and none of them covers it. Turn on web search in Settings to look it up." |
| also "which is most urgent", "which one is quicker", "what's important", "what's related", "why are they linked" | the same sentence |
| "by how much" | "Your five newest notes, from 7 November to today: ..." |
| "how much did I spend on groceries" | "I found no amounts spent on groceries in your notes." (the two budget notes say Groceries 140 and Groceries 120) |
| "total for november" | "On November you've written five notes, 14 August to 7 November. ..." (a digest of every note containing the word) |
| "how many nights in total", "which is longer" | the sentence quoted back, no sum (5 + 4 + 3) |
| "compare my two runs" then "which was faster" | "Running log is the longer, 24 words to 11." then the note quoted |
| "whose birthday is first" | the Todo checklist |
| exam, dentist, car: "which comes first", "how many days between them", "how many days until then" | the landlord note; "Jr pass is not worth it under 7 days apparently..."; the same |
| "what's 650 plus 140" then "times 12", "minus 100"; "what's 15% of 4500" then "split that between 2" | the Japan trip note; the banana bread note; the car service note |
| "how many notes do I have" then "how many about harbor" | the Harbor launch plan quoted, no count |

Causes: `personal.py:380` `_GENERAL` plus line 399 call any what/which/why question without "I/my/you/note" a question about the world; `composer_phrases.py:154` and `composer_body.py:1045` give the newest notes when no term is left; `composer_calc` has no running value; `composer_money` reads "spent" verbs and misses "Groceries 140"; `composer_slots.py:693` compares word counts.

Fix: (a) `general()` is false when the question has no noun of its own or history holds a subject; (b) a comparative or "total/sum/difference/first/next/between" after an answer with two or more numbers or dates (frame `dates`/`items`) is computed from them and said with both values ("November is higher on groceries, 140 against 120; eating out fell from 160 to 90"); (c) the calculator keeps its last result for "times 12", "minus 100", "split that between 2", "half of that"; (d) "Label number" lines in a note titled budget, costs or spending are amounts; (e) drop the word-count comparison of notes.

### F7. The sentences sound generated: phrase tables, stacked stat lines, labels on the wrong line (high, copy; the owner's "robotic", "generated")

Bad sentences verbatim, grouped by the rule that made them:

1. Paraphrase tables picked by seed (`composer_tables.py`: openers near 346 to 363, missing-word tails at 194, `NEXT_STEPS_EXTRA` at 1457 to 1482; `composer_phrases.py`). The register changes every turn and none of it is how a person talks: "Here is your exact note:", "This is how you put it:", "Your own words:", "This is what you saved:", "According to your notes:", "Looking through your notes:", "This seems to be the closest record:", "In a different spot:", "On another note:", "Elsewhere,", "Separately:", "Across your other entries,", "In another entry,", "You previously noted:". After thanks: "Need any further clarification on “car service due”?", "I can check for other mentions of “dentist”.", "Let me know if you'd like me to continue searching for “anna visiting”.", "Should we explore “anna” further?", "Would it help to see more notes on “japan budget”?", "If you want, I can look for more details on “calculator”." Tails: "None of these records discuss “far”.", "It looks like these notes omit “very” or “helpful”.", "No note found brings up “stressed”.", "These notes do not talk about “good”.", "I don't see any mention of “worried”."
2. Verb rotation in overviews (`composer_digest.py` near 198; `composer_frame.py`): "You wrote “...”. You noted down “...”. You put down “...”. You said that ..." Four verbs for the same act, in a fixed order, quoting half-sentences ("You wrote “Rent 650”. You noted down “Rent 650”.").
3. Stat and system lines appended to answers: "Only one note has those words; search by meaning could find others." (`composer_digest.py:499`, 9 times), "The app has a tool by that name too. Open its Help topic for the steps." (`composer_phrases.py:250`, after "is it this week", "the second one", "what's in it"), "So far this is your only note on it.", "It's your only book review so far.", "That keeps coming up.", "That's about one every three weeks, the newest written a few days ago.", "The newest is from a day ago, so it's current.", "Read as 650 + 140.", "Read as next Friday as Friday 20 November 2026.", "Running log is the longer, 24 words to 11."
4. The Also block (80 answers; `composer_tables.py:322` `ov_also`): every fact question returns the whole note as "**Also:**" lines, sometimes two blocks in a row, in three layouts (bullets; semicolons; two paragraphs). "how much is the budget": "Budget is $4,500. **Also:** Flights booked for 12 March, returning 26 March; Tokyo for 5 nights, then Kyoto for 4 nights, then Osaka for 3. **Also:** Travelling with Sam."
5. A label carried onto lines it does not belong to (the "Label: value" reader in the same block): "Six, from your Banana bread note: 3 ripe bananas, ... **Ingredients:** mash the bananas, mix everything, bake at 175 degrees for 50 minutes."; "**Two tiers:** decision due by 20 November."; "**Two tiers:** Priya wants an annual plan at $60"; "**Harbor standup:** Priya is waiting on legal for the annual plan."; "**Monday:** three sets of eight."; "From your Gym routine note, on Monday: squats and rows."; "**How it went:** you loved the House and the tides" (a label the note never had).
6. Articles and number (`composer_threads.py:105` `with_article`; count frames): "also has a three gates before then:", "has a goals for the half:", "1 dated item for today", "Here are your 1 note this morning:", "0 reminders and 6 unticked checklist items are waiting.", "Your note **Reading list** lists four: Piranesi, Thinking, Fast and Slow, The Overstory and Klara and the Sun." (a title with a comma split into two items, and "lists three items" elsewhere for the same note).
7. Frames filled with the wrong kind of thing (`composer_digest.py:132` `still_list`, the dated-narrative frames, `_your_note` at 1052): "Last Saturday, you still need to renew passport by 30 November.", "Back in August, you booked the Check-up for 21 November at 2:30pm with Dr Patel.", "Three weeks later, on 28 October, you finished it.", "Call with Anna wants to try the new ramen place, written a week ago, on 1 November." (the note's title put where "She" was), "Your note Harbor pricing notes has two tiers: decision due by 20 November.", "On coming up you've written two notes, 14 August to 9 November.", "On more worth you've written three notes.", "There are two notes about wait room.", "Two notes about between.", "I found four notes about “japan then”.", "More loosely related to harbor." (a heading said as a sentence), "42 testers so far." (alone in a paragraph), "35 notes do not mention tennis at all:" (to "nothing on tennis at all?").
8. The person's words rewritten: "Mia says the android build was flaky, retry Friday 6 November" (the note says "is flaky, retry friday"), "Need to prep for the stats exam the week of 9 November" (the note says "this week", written today), "free and Plus at $6 a month" (Free is a tier name), "Jr pass", "Dr patel", "sam says" beside "Sam says" for the same note in two answers.
9. Same question, same answer: "when is the harbor launch" three times in one chat differs only in "from your Harbor launch plan note" against "as your Harbor launch plan note has it", which alternate through all 469 turns like a tic.
10. Greeting (`composer_lines.py:256`, the joiners at 70): "Good morning, and welcome back. That is 10 days of writing in a row. Also, you last wrote [feeling pretty tired today, slept badly]. Also, nothing is due today. Anything you want to look up?" Six greetings in one chat gave the same three facts six times, reordered, joined by "Also," "And", "On top of that," twice in a sentence. "good evening" at 09:00 is answered "Good evening."
11. Identity: "I'm Atlas." / "Atlas here." / "This is Atlas's assistant speaking." / "I'm Atlas's assistant. Connect a model and you can talk to Atlas itself." / "I'm a program, not a person: Atlas, reading your notes on this computer." Three different speakers in one chat.

Fix: see the voice section. The class fix is fewer, hand-written frames per answer shape with the facts chosen first, and the tails deleted, not more paraphrases.

### F8. The defining note does not lead; a short title-less note outranks it (med, ai)

- "when is the dentist": "Dentist said floss more, next clean in six months. Cost was $180, written on 20 May, about six months ago." The note titled Dentist holds "Check-up booked for 21 November at 2:30pm with Dr Patel."
- "do I have a dentist appointment": "This seems to be the closest record: Dentist said floss more, ... Elsewhere, check-up booked for 21 November ..."
- "what's in my budget": "Budget is $4,500, from your Japan trip note." (two notes are titled Budget)
- "what am I reading": "Check-up booked for 21 November at 2:30pm with Dr Patel, from your Dentist note." (matched "reading" to nothing and fell to an unrelated note; Reading list and Piranesi exist)
- "what did I plant" / "how often should I water them": "From “idea: an app that reminds you…”: an app that reminds you to water plants based on the weather forecast." (the Garden note says "Planted tomatoes and basil", "Water every second day")
- "what did mia say": Mia's profile, not "Mia says the android build is flaky".
- "wats on my shoping list": "Your note **Reading list** lists four ... Did you mean **Reading list** or **Tokyo food list**?" (the note titled Shopping is offered third, as a chip)
- "who is anna": "Anna comes up in three notes." then three dated facts; the note titled Anna is not used as her description.
- "what time is it": "You wrote this on 5 October: Water every second day. [**Garden**] ..."

Fix (ranker, `composer_select.py` / `composer_ask.py`): a title match on the subject (exact, stemmed or fuzzy) outranks any body match; a title-less note never leads over a titled note on the same subject unless it alone holds the asked slot; a "when is X" prefers a sentence with a future date over an old dated remark; "who is NAME" leads with the note titled NAME. "what time is it" belongs to the clock reader, which already answers "what day is it".

### F9. The agenda lists a mood note and misses the plumber (med, bug)

- "what's on today", "what's due this week", "what should I do today": "1 dated item for today, Tuesday 10 November: - feeling pretty tired today, slept badly. need to prep for the stats exam this week" with chips "Open the feeling pretty tired today, slept badly note" and "Remind me about feeling pretty tired today, slept badly today".
- The note written the day before, "landlord called back, plumber is coming thursday between 8 and 10", is in no agenda for this week.
- "anything else?" after "what's on today" repeats the same list under a new head.
- "what about tomorrow": "Nothing is planned for tomorrow." with a "Notes per week" chart.
- "what's the next thing": "- 20 November: Dentist said floss more, next clean in six months. Cost was $180" (the six months worked out from 20 May, shown as the note's sentence).
- "can you help me plan the trip": this week's plan, with the shopping list.

Causes: `composer_plan.py:28` splits sentences only at a full stop before a capital, so a lower-case comma-joined line is one sentence; `composer_plan.py:327` drops the whole line when any clause is told as past ("called back"); the same whole line is shown for the mood note because "today" dates it. `_item_chips` (467) builds chips from the first row's name.

Fix: split unpunctuated lines at ", " and " and " clause boundaries when a clause has its own verb; judge past-ness and the date per clause; show the dated clause ("Plumber is coming Thursday between 8 and 10", "Prep for the stats exam this week"); a feeling with "today" and no task verb is not an agenda item; a derived date says so ("Next dentist clean is due about 20 November, six months after your 20 May note"); chips name the clause's subject.

### F10. A title-less note has five names (med, copy; owner decision 2026-11-10)

For the same notes: “feeling pretty tired today, slept badly” (quoted, no ellipsis), [feeling pretty tired today, slept badly] (bare link), “harbor standup: Mia says the android…”, "Your Harbor standup note", "your harbor standup note", [landlord called back, plumber is coming thursday between 8…], "- landlord called back, plumber is coming Thursday between 8 and 10, 9 November" (whole line), "From “idea: an app that reminds you…”", "idea: an app that reminds you to water plants based on the weather..." (three dots), and in "what have I forgotten": "[Anna Anna's birthday is 3 December.](#/notes/8), no words". Helpers: `composer_frame.py:400` `note_title`, `composer_frame.py:498`, `composer_answer.py:176`, `composer_digest.py:1052` `_your_note`, `composer_write.py:462` `note_name`, `composer_lists.py:557`, `tool_say.py:73`, `day_digest.py:46`. Fix: one function (first line, about six words, cut at a word, an ellipsis) used by all eight; "Your X note" only for a real title. W8 or W10 holds the decision; this is the call-site list.

### F11. The bracketed `[**Title**]` citation is still on 57 answers (med, copy; decision D25)

"Check-up booked for 21 November at 2:30pm with Dr Patel. [**Dentist**]", "Rent 650. [**Budget October**]". The same fact on the next ask is cited "from your Dentist note". Extractive path (`composer.py` near 816 and the openers table). Fix: the extractive path uses the same source clause as the slot path, or none when the Sources list shows it.

### F12. An offered reminder cannot be accepted, and it is offered where nobody asked (med, ux; overlap B23, B26)

- "how much is the budget": "... Remind you each week to log your spending?" (`composer_digest.py:98`). "what do I know about anna": "... Remind you to buy Anna a birthday present?" "total for november": "Remind you to renew passport by 30 November?"
- "yes": "Noted. Ask whenever you like. Should we explore “anna” further?" "sure": "Good. Ask whenever you like. Would it help to see more notes on “japan budget”?" "ok do it": the budget answer again. "no": "Sorry, I read “ok do it” as a search of your notes. What were you after?" "no thanks": "I found at least three notes of yours that mention “anna” ... That keeps coming up."
- Not in B23's row as written: the ack reply itself appends a second question from `NEXT_STEPS_EXTRA`, so a "yes" is answered with another offer; and "no thanks" is searched. Fix with B23: an offer is a pending act in the frame; yes/sure/ok/do it/please accept it, no/no thanks/not now drop it with one line and no tail. Offer a reminder only when the question was about a date or a task.

### F13. Smaller, each verified

| id | turns | answer | cause, fix |
| --- | --- | --- | --- |
| a | "who am I going with", "who am I going to japan with" | "Only what your notes say, and none of them says anything about you yet. Write a note about yourself and I'll know it." | `personal.py:142` matches the prefix "who am i"; anchor it to the end of the question |
| b | "do I have anything on france" | "Nothing matched “france”; here are your eight newest notes." | `tool_say.py:257`; say nothing was found and stop |
| c | "open it" after an answer from Kyoto ideas | "The closest note about “Kyoto ideas” is [Kyoto ideas](#/notes/12): Fushimi Inari at sunrise ..." | `commands.py:1930`; an exact title is "Here it is:" and opens it, as "open my japan trip note" does |
| d | "what have I forgotten" | "5 notes have gone more than 90 days without an edit. The 5 oldest are listed below. - [Statistics lecture 1 Mean, median and spread.](#/notes/15), no words" | title and body joined; ", no words" on every row |
| e | "what notes are empty" | "I found no mention of “empty”. Which note might it be in?" | the title-only reader is not reached ("Gift ideas for mum" is one) |
| f | "/week" | the whole command list, 18 lines | suggest /made week or /due week, two lines |
| g | "make a study plan" | "Writing that needs a model: connect one in Settings, Models. Until then I can find what your notes already say about it." | the plan reader answers "what should I do today"; offer the exam's dated plan from the notes |
| h | "what did I write last week" then "and the week before" | the mood note quoted | `_follow_window` (`composer_dialogue.py:376`) has no "the X before/after" |
| i | "summarise my japan notes" | one note, one line, "Say “more” for the rest." while "summarise my harbor notes" gives three paragraphs | two summary paths with different shapes (`composer_study.py:324`, `349`) |
| j | "what links to it", "what's related", "why are they linked" after opening a note | "These notes do not mention “links”." then "That's general knowledge" twice | link reasons are not reachable by a follow-on; bind "it/they" to the opened note |
| k | "how are you" alone | "Steady and ready. How are you getting on?" then any answer to that question is searched | a question the composer asks must be one it can hear the answer to |

### F14. Model on (decision 75): what could be seen with the fake transport

18 turns with `ai_client`. Every turn went to the fake model, including "hi", "thanks", "remind me to call anna tomorrow at 5", "add butter" and "remove milk"; only arithmetic and the statistics card were composed, and the Statistics card was attached to "when is the stats exam" (F2 holds with a model up). No composed facts or chips could be judged: the fake returns one canned line. Real inference is not verified.

## Voice: what would make it sound like a person, without a model

1. Decide the facts first, then say them once. One lead sentence that answers the question in the question's own terms, at most one more that a person would add, then stop. "When are the flights?" is "You fly out on 12 March and back on 26 March." The rest of the note stays in the card or behind a "More from this note" chip. Delete the Also block from fact answers.
2. Answer the question's verb. The lead is built from the slot asked, not lifted whole: "Who is it with?" gives "Dr Patel."; "Where?" gives "Room B204."; "How much flour?" gives "250 g."; yes/no questions start "Yes" or "No" ("Yes, on 21 November at 2:30pm with Dr Patel."). The note's sentence follows only when it adds something.
3. Delete the tails. No "Only one note has those words", "The app has a tool by that name too", "So far this is your only note on it", "That keeps coming up", "None of these notes mention “very”", "Read as 650 + 140". A miss is one sentence: "I can't find anything about tennis."
4. One citation style, light: "from your Dentist note" on the first mention in a chat; on later turns about the same note, nothing (the Sources list has it). Never alternate "as your X note has it".
5. Variety from the conversation, not from a table. Keep two or three hand-written openers per shape and choose by what happened: a first answer is plain; a follow-on acknowledges it ("She likes pottery and Japanese food."; "Kyoto: four nights, after Tokyo."); a repeat question says so ("Still 14 December, 34 days off."); a correction says so ("Right, the pricing note: ..."). Track the openers used in this chat (the last four answers are in history) and never reuse one in consecutive turns. Remove the long paraphrase lists (`NEXT_STEPS_EXTRA` and the opener tables): they are the "generated" sound.
6. Contractions and second person: "you've", "there's", "it's", "I can't find", "nothing yet". Not "I did not catch what “and cheese” was after", "I do not have a list in front of me", "You are welcome".
7. Counts in words up to twelve, the right number and article, and no zero clauses: "one thing dated today", "your one note from this morning", "six open items" (not "0 reminders and 6 unticked checklist items").
8. Keep the person's words as written when quoting; change tense or dates only in the composer's own sentence ("Mia said on Friday that the Android build is flaky").
9. Small talk answers in kind and stops: "Morning. Ten days in a row now." once per chat; a second greeting is "Hello again." Thanks is "Any time." with no appended search offer. One name: Atlas.
10. Feelings get one human line and one useful thing: "That sounds rough. The exam's on the 24th, two weeks away; want what it covers?"
11. End on the next step as a chip, not as a sentence ("Say “more” for the rest." becomes the chip "More").

Libraries (all approved in CHAT_PLAN "Placed from INBOX, 2026-11-10"):

| library | where it helps here |
| --- | --- |
| `inflect` | F7.6: `a`/`an`, plural agreement ("1 dated item", "Here are your 1 note", "a three gates", "a goals"), number words, ordinals in "the second one" |
| `rapidfuzz` | F1, F3, F8: binding "the beta one", "the november one", "the pricing" to the last answer's titles and items; "shoping list" to the Shopping title before a body match; "ana" to Anna |
| word-frequency list | F5, F7.1: a chip subject must be a rare content word or a title ("badly", "read", "time", "back" are refused); a common word is never reported as missing ("very", "good", "far") or used as a topic ("between", "more worth") |
| `textstat` | the 1730 (d) eval: a reading-ease floor per answer, sentence length ceiling of about 22 words, flagged per shape |
| `holidays` | not needed for anything seen here ("how many days until christmas" already answers); useful for "what's on over Easter" |

Eval to gate this (1730 d), from the probe files: per dialogue, (1) no answer equals an earlier answer in the chat unless asked to repeat; (2) no opener phrase used twice in a row and none more than twice per chat; (3) no sentence from the banned list in F7; (4) every answer has two or more chips, none generic after turn one, none already pressed, each grammatical and answerable; (5) the cited note is the expected one for each follow-on in F1, F3 and F8; (6) `textstat` ceiling.

## What is already good

- Named single questions: "when is the car service due" ("... in 35 days"), "what's her number", "how long until the japan trip", "have I booked flights" ("Yes, “Book flights” is ticked off in Todo."), "did I pay rent" (honest miss with the nearest line).
- Typos repaired and said once: "I read that as “when is my dentist appointment”."
- Dates: "what day is it", "how many days until christmas", "what week is it", "what's due this month" (six right rows).
- The chart and statistics follow-ons conv-1110 built hold on this notebook too.
- Acts that name their target work and confirm: "tick off eggs", "undo" after it, "add 'call mum' to my todo", "new note called packing list", "delete that" after a save.
- Honest refusals: weather, jokes, "what's the capital of france".
- "going back to anna, what does she like" and "back to the exam, what room" find the right note.

## Not verified

- Real model inference (fake transport only); the browser (chips as drawn, Stop, regenerate, phone width, dark, keyboard, screen reader); pressing Confirm on any act card; the Also panel and link reasons as rendered; voice input; performance. The plumber miss was traced to `composer_plan.py:28` and `:327` by reading, not by a patched run. The hand count in F-intro (61 of 104) is one reader's judgement.
