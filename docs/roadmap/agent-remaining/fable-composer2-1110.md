# Composer audit 2, 2026-11-10: the composer everywhere except chat conversations

Read-only. Head: `claude/next-queue-1102`. The first audit (`fable-composer-1110.md`, F1 to F14) covered chat dialogues and is not repeated; where a finding here touches one of its rows it says so.

Method. TestClient route probes (no model: `client`; model on: `ai_client` with the fake transport), fixed clock Tuesday 10 November 2026 09:00 UTC, the first audit's 36-note notebook plus 5 notes (two from this day in 2025 and 2024, a note that supersedes the Harbor launch date, a meeting note, a title-less "call mum"), 5 reminders (2 overdue, 1 due tonight, 2 later), `display_name` "Alex". Also an empty notebook and a one-note notebook. One browser pass on a live server (port 8797, own data dir, 1440x900 and 390x844) for the dashboard as drawn. Every answer was read.

Driven: 343 single questions through `/chat/stream` (the Ask tab posts there, `frontend/js/answer-kit.js:1201`), 58 more for acts and re-checks, 130 Guide questions (`/help/ask`, 9 tabs, one dialogue), 32 `/statistics/ask`, 15 `/reminders/suggest`, 14 `/reminders/when`, 4 `/reminders/parse`, 28 other routes on three notebooks, 168 composed greetings (7 days by 24 hours), 30 chat turns and 6 Guide turns per model-on run (two runs: profile switch off and on). Harness and raw output (not in git): `/tmp/claude-0/-home-user-Tessellate/4f1165b8-dfbe-57d9-b2ee-276812e0a5f3/scratchpad/probe2/` (`common.py`, `seed.py`, `t_*.py`, `dash.js`, `out/*.json`). Run one with `probe2/run.sh t_ask.py`.

Every provider ran against the fake transport (CLAUDE.md 4): real inference is not verified anywhere below.

Counts: 14 findings (5 high, 6 med, 3 low; 6 bug, 5 ai, 2 copy, 1 missing), plus a parity table (19 gaps), a name section and a "should be composed" list (16 rows).

## Coverage

Inventory from `docs/CODEMAP.md`, by file (700 rows). `run` is driven through its route or called directly and its output read; `code` is read only.

| area | CODEMAP rows | state |
| --- | --- | --- |
| `api/routes_insights.py` (greeting, today-line, remarks, day, patterns, on-this-day, digest, stats, tag-cloud, confirmed) | 56 | run for the 11 GET and 2 POST routes named; confirm, dismiss, done, the confirmed-fact routes and heatmap not reached (they write no sentences) |
| `ai/greeting_compose.py` | 8 | run (168 composes, `gather` on three notebooks), read whole |
| `ai/composer_voice.py` | 29 | run: `remarks`, `today_line` (14 seeds, 5 days), `week_review`, `one_line`, `suggested_searches`; `VOICE` table read whole; `title_for` code |
| `ai/day_digest.py`, `ai/activity.py` (`week`, `_summary`, `_week_reminders`) | 53 | run through `/insights/day`, `/insights/digest`, "summarise my week", "what happened this month"; `boards` and the made, edited, binned readers not reached |
| `ai/insights.py`, `ai/tensions.py`, `ai/supersede.py` | 86 | run through `/insights/patterns`, `/entries/tensions` (no model and fake model); read at the lines cited; the confirm and memory paths not reached |
| `ai/help_chat.py`, `ai/guide_intent.py`, `ai/help_topics_more.py`, `api/routes_help.py` | 67 | run (130 questions with no model, 12 with the fake model); `composed_answer`, `offline_answer`, `topics_for` read; the stream route, sample notebook routes and each of the topics' text not reached |
| `ai/stats_ask.py`, `api/routes_statistics.py` | 20 | run (32 questions, empty notebook too) |
| `ai/reminder_suggest.py`, `api/routes_reminders.py` | 61 | run: suggest, when, parse, counts, list; ics, calendar links, notification token, recurrence not reached |
| `api/routes_resurface.py`, `ai/resurface.py` | 22 | run: compute, list, all, near |
| `api/chat_extra.py`, `ai/composer_smalltalk.py`, `ai/personal.py`, `ai/vocative.py`, `ai/composer_aware.py` | 77 | run through chat ("good morning", name questions); `welcome_line` and `personal.py:136` read; `composer_aware` not reached (the probe sent no `actions`) |
| `frontend/js/dashboard.js` | 131 | run for the hero (greeting, sub line, glance tiles) and 11 widgets' text at two widths; edit mode, widget dialog and drag not reached |
| `frontend/js/companion-remark.js`, `avatars.js` poke lines | 1 (+ the line tables) | code; the bubble was not watched in a browser |
| `frontend/js/help-chat.js`, `statistics.js`, `reminder-notify.js`, `desk-companion.js` | 89 | code at the lines cited only; not driven |
| Chat composer files (`composer*.py`, `commands.py`, `task_acts.py`, `acts.py`) | first audit's table | run again for single questions and 38 act phrasings; not re-read beyond cited lines |

Not reached, and why: the desk companion window (needs the desktop shell), notification popups (need permission and a due time), the Guide panel as drawn, dark mode, keyboard and screen reader, the accessibility, performance and security lenses beyond what a route probe shows (one privacy note in G6). This is a text audit; those lenses belong to the surface audits.

## Findings, ranked by owner impact

`verified` is `run` unless marked. Effort: S under an hour for a Sonnet step with its test, M one step, L needs a short design first.

### G1. Ask says yes to things the notes do not say, and leads with a fact a newer note replaced (high, ai)

| asked | answer (verbatim) | truth in the notes |
| --- | --- | --- |
| is the pricing page signed off | "Yes, your note of 3 September says so: Three gates before then: beta feedback closed, the pricing page signed off, and the app store review passed (Harbor launch plan)." | it is a gate still to pass; today's note says "Pricing page still not signed off" |
| have I called mum | "Yes, your note of 8 November says so: Call mum on Sunday about christmas plans" | a to-do; "did I call mum" answers "Not yet ... only plans it" |
| when is the launch, when does harbor launch | "Ship the Harbor mobile app to the public on 14 December, from your Harbor launch plan note, in 34 days." | today's note: "Legal says the launch slips to 11 January"; "how many days until the launch" answers 11 January, so two answers disagree |
| has the launch date changed | "The closest your notes come is this: ... None of these notes say anything about “changed”." | yes, from 14 December to 11 January |
| when did I last see the dentist | "Check-up booked for 21 November ... in 11 days." | 20 May (the past visit) |
| how far did I run | "Your notes record 16 km run: Running log 10 km and ran 6 km." | the 10 km is a goal; the log has two 5 km runs |
| what do I know about the gym | "Your Gym routine note also has Monday: three sets of eight." | not Monday's (first audit F7.5, same label reader) |

Causes. (1) `composer_slots.py:395` `_imperative_of` compares the note's first word with the question's verb as typed ("call" is not "called"), so the perfect tense falls through to "Yes ... says so" at `:408`; compare stems. (2) The yes branch takes the first ranked sentence that holds the words; it never asks whether a newer note negates it (`_UNDONE`, `:403`) and a noun phrase in a list ("the pricing page signed off") counts as a statement. (3) The date reader takes the best-ranked note, not the newest that names the same event; `supersede.older_line` exists (`routes_chat.py:1082`) but this path does not reach it. (4) "last" and "next" are not read as past and future for a when-question. (5) the distance sum counts any "N km" (`composer_money`/the run reader), goal lines included.

Fix (M): one rule in the fact readers: when two notes answer the same slot for the same subject, the newest leads and the older is said once ("11 January; your launch plan of 3 September said 14 December"). In `_say_did`: stem the verb; a yes needs a past-tense or ticked statement, a list item or a "before then" clause is "planned"; scan all matching notes for `_UNDONE` before saying yes, newest first. Exclude sentences with "goal", "by", "aim" from sums. Tests: the seven rows above.

### G2. Questions and settings requests create notes with no confirm; snooze crashes with a Python error (high, bug)

- "note about suica" answers "All set, created “Suica” in Travel." (a search for the Suica note; "find the note about suica" works). "make a note private" answers "All set, created “Private” in Uncategorised." "write a packing list for japan" answers "All set, created “Japan packing list” in Travel." with an empty checklist. Notebook went from 41 to 44 notes in the probe. Reproduced on an unpatched clock.
- "snooze the bins reminder to tomorrow", "snooze take bins out until friday", "move the bins reminder to 8pm": the answer is `Something went wrong: TypeError("can't compare offset-naive and offset-aware datetimes")`. Cause: `task_acts.py:679` `plan_snooze` compares a stored naive `due_at` with the aware clock; `chat_turn.py:580` prints the exception text to the person.
- "edit the wifi note: the network is Bluegum-6G" returns the Harbor overview; "create a category called Hobbies" returns the "call mum" note; "make a document about harbor" returns a search.

Fix: (S) normalise both sides in `plan_snooze` as `day_digest._naive` does, test with an aware clock; `chat_turn.py:580` says "That did not work. Nothing was changed." and logs the exception. (M) in `commands.py` (the new-note reading near `:831` and the bare "note ..." head): "note about X", "the note on X" with no content after it is a find; "make a note private" is the privacy act or its hand-off; a create with no body asks "What should it say?" instead of saving an empty note. (M) add the three missing acts to the act registry or hand them off by name (see Parity).

### G3. Reminders are invisible to Ask's readers, and four surfaces give four counts for the same reminders (high, ai)

With "Take bins out" due today at 19:00 and "Pay phone bill" and "Email landlord" overdue:

- "do I have any reminders today": "There's nothing in your notes about “reminders”. Want to try a different word?"
- "did I pay the phone bill": "I found nothing in your notes about the phone bill."
- "when do the bins go out": "Your notes do not say a date for the bins go out. The nearest is Budget October: Eating out 160."
- "what bills are due": "Decision due by 20 November. ... It looks like these notes omit “bills”."
- "what's the agenda deadline": the whole two-week agenda.

The same morning, the counts: chat greeting "you have 3 reminders due today" (`chat_extra.py:112` counts overdue as due today); dashboard digest "One reminder due today and two overdue." (`day_digest.py:72`); dashboard sub line "1 reminder coming up" beside the tile "1 due today" (`dashboard.js:526` to `:532` against `:633`); statistics "5 open reminders, 2 of them overdue".

Fix (M): one function for "what is due" (`repo/reminders` plus a tiny `due_summary(now)` returning today, overdue, next) used by `welcome_line`, `day_digest._due`, `/reminders/counts` and the dashboard sub line, with one wording: "one due today, two overdue". The did-I, when-is and do-I-have readers search open and done reminders by their words before notes ("Not yet: “Pay phone bill” was due yesterday."; "Tonight at 7pm, from your reminder."). Tests: the five questions and the four surfaces agreeing.

### G4. "Weekly review", "daily review", "how was my week" are searched as words; the digest that does exist is a creation log (high, ai)

- "weekly review": "You wrote this: Actions: Priya drafts ... None of these notes say anything about “weekly”. The app has a tool by that name too. Open its Help topic for the steps."
- "give me a daily review": "Your own words: Goals for the half ... There is nothing in these notes regarding “daily”."
- "summarise my day": summarises the note titled Moving day. "how was my week": the mood note.
- "summarise my week" and the dashboard's digest (`/insights/digest`): "From your notes, no AI. In the last 7 days (4 to 10 November) you made 16 things. Overdue: ...; Coming up this week: Take bins out (due 10 November). - **Today:** set the reminder Pay phone bill; set the reminder Take bins out; set the reminder Dentist check-up; set the reminder Email landlord about the leak; set the reminder Renew passport; and two more." The two notes written today are the "two more"; every later line repeats "made the note". A thing due today is "coming up this week (due 10 November)".
- Statistics' version of the same question: "This week so far: 5 notes, 74 words, no reminders done. Most used tag: harbor (1 note). That is 2 more than by the same point last week."

Three writers answer "my week" with three shapes. The best one is not wired: `composer_voice.week_review` (`composer_voice.py:591`) gives "You wrote eleven notes in the last seven days, from 4 November to today. Most went under Life (five), then Work (four). What stands out: ... Still open: ..." and is called only from `tests/test_week_review_paths.py` and `tests/_voice_eval.py` (grep: no caller in `src`). Its own bugs: "your note from 5 November (5 November)", the title-less name is "your note from 10 November" (the owner's rule is the first six words), and Still open lists three shopping items and no reminder.

Cause: `activity.py:620` to `:643` (`week`), `_summary` at `:390` ("things"), `_by_day` clause per event; the review phrasings are not in the summary gate (`chat_extra.py:51` to `:57` knows "summarise my week" only).

Fix (M): make `week_review` the one writer for the Digest widget, "summarise my week", "weekly review", "how was my week", and a daily form for "summarise my day", "daily review", "how was today" (today's notes, what was ticked, what is due tonight and tomorrow). Order: what was written (by subject, not by event), what was finished, what is overdue and next, one stand-out quote. Reminders made are a count, never a list. Drop "From your notes, no AI." (the widget already labels the source). Delete `activity.week` once the widget reads the new one (replace, do not layer).

### G5. The Guide with no model leads with the wrong sentence, and its miss line blames the missing model (high, copy)

Of 97 single questions, 15 led with a wrong topic or a sentence that does not answer, and 9 were misses although a topic exists or a hand-off would answer (hand count). Verbatim:

| asked | lead | cause |
| --- | --- | --- |
| how do I make a private note | "Press Forgot your password? on the lock screen ..." | keyword "private" ranks the recovery topic; `_guide_lead` (`help_chat.py:1008`) takes the best word-overlap sentence |
| what is Tidy | "The layout picker: tree, radial, logic chart ...; Tidy lays every unpinned topic out again." | a "what is X" must lead with the topic whose title is X, first sentence |
| what is on this day | "Atlas is the assistant inside Tessellate." | same |
| what is the daily note | "Kinds chooses notes, boards and maps ..." | same |
| weekly review | "A map's twenty-seven, among them Lecture notes ..." | a template list matched on the words |
| do I need a model | "Connect a model in Settings, Models ..." | a yes or no question gets no yes or no; the answer is "No" |
| why is the AI slow | "... turn on Performance mode in Settings, Appearance: it switches off the glass ..." | answers "the app is slow" |
| how do I scan a page | "A pinch, two fingers on a touch screen or Ctrl and the wheel zooms the page ..." | |
| nothing happens when I click save | "While the app is locked nothing is announced; a timer that ran out speaks after you unlock." | "nothing" matched |
| how do I stop the AI changing my tags, how do I make a checklist | "Enter sends, Shift+Enter starts a new line; Escape or Ctrl+. stops the answer ..." | "stop", "checklist" matched Chat controls |
| is there an app for android | "On an iPhone, press Install the certificate ..." | |
| what is tessellate; what does this page do (Whiteboard, Settings open) | "Tessellate has seven tabs along the top." | `TAB_TOPICS` (`help_chat.py:170`) has no `whiteboard`, `settings`, `statistics` keys |
| what does this page do (Notes open) | "A formatting toolbar, here or in a document, is one Tab stop ..." | the tab's topic body is ranked by words, not led by its first sentence |
| what does this page do (Chat open) | "Changing or removing asks first, and after it reads a web page or a clipped or imported note, so does every change and web request." | same; the sentence has no subject |
| help | "Yes. I'm the app's guide ..." | `guide_intent.py:127` answers "can you help" and a bare "help" alike |
| how do I record a meeting | "Press Record there (Ctrl+Shift+R opens it too)." | a lifted sentence keeps its "there" |
| where is the bin | "It's in the bin: the Library's Include the bin, or Ctrl+Z right after." | `_guide_opening` (`:1030`) prints the path after "It's in" |
| how do I turn off the companion | "It takes three steps ..." and none turns it off | the topic's steps are for turning it on |
| what is my name, how do I change the greeting | the Profile paragraph | never says the name (see Name use) |

Misses: "what's the weather", "when is my dentist appointment", "how many notes do I have", "how do I see my week", "what should I do first" (a First steps topic exists), "what's new", "who made this", "how much does it cost", and the dialogue follow-on "where do they show up" after two reminder answers. All get "The local model is not running, and nothing in the app's own help text matches that. Try a word from the feature's own name, a tab name, or open Settings, Help, which lists every topic." (`help_chat.py:838`), sometimes with "Did you mean: Mind map keys and controls, Chat keys and controls, ...?".

Every how-to opens "It takes three steps, from the Reminders tab:" (`help_chat.py:1032`), then a "**Related:**" line that often repeats the topic just given ("Related: Set a reminder").

Fix (M, one step each): (a) lead rule: "what is X", "what does X do" lead with the first sentence of the topic titled X, and a tab question with the tab topic's first sentence; the word-overlap pick is only the second sentence. (b) yes or no questions get "Yes" or "No" from a small per-topic `answers` map (model needed, data leaves, sync, cost, Android) as `capability.privacy_line` already does for privacy. (c) the miss line never mentions the model: "I don't have help on that. Try a tab or feature name, or browse Settings, Help." (d) a question about the person's notes or reminders ("when is my ...", "how many notes ...", `_MY_ITEMS`) hands over: "That is one for your notebook" with an "Ask it in Chat" chip (`asks_to: "chat"`). (e) the follow-on keeps the last topic when the new question names nothing ("where do they show up" stays on Reminders). (f) add `whiteboard`, `settings`, `statistics`, `library` rows to `TAB_TOPICS`. (g) drop "It takes N steps, from X:"; the numbered list says it. (h) remove a Related entry equal to the lead topic's own act. Eval: the 130 questions in `probe2/t_help.py` with the expected topic id per row.

### G6. The dashboard greets twice, contradicts itself, and names you every time (med, copy)

Seen in the browser (1440 and 390, no model): "Afternoon check-in, Alex." over "Today has five notes so far, the latest Shopping. · 1 reminder coming up", beside the tile "1 due today".

- Headline against the line under it. At 09:00 with two notes written today the headline was "A fresh page." and the line under it "The page has filled a little: two notes". `greeting_compose.py:36` to `:41`: "A fresh page", "Welcome back", "Hello again" are in the plain morning list whatever `facts` say; on an empty notebook half the picks are plain, so a first visit can read "Welcome back, Alex." or "Hello again, Alex." Fix (S): tag each phrase with what it needs (`fresh` only when `today == 0`, `back` only when `total > 0 and days_since_last >= 1`), filter in `compose` (`:110`).
- Empty notebook: the sub line greets again under the greeting: "Good morning, and welcome back. Welcome. Write your first note and I will start filing it." and "Good morning. Nice to see you. Welcome. This notebook is empty, so the first note starts everything." (`composer_lines.py:256` joined to `:262`, through `routes_insights.py:498` to `:505`). Fix (S): the dashboard asks `welcome_line` for the notebook clause only (no greeting, no "Welcome."), and "welcome back" is never said of an empty notebook.
- Title run into the sentence: "the latest Harbor launch date." reads as the date of a launch; "the latest Shopping." Fix (S): the dashboard keeps the title marked (it strips `**` at `routes_insights.py:507`): quote it, "the latest is “Harbor launch date”".
- Size words chosen by seed, not by count: "A busy page today, two notes"; "The page has filled a little: five notes"; one note written two years ago gives "It has been a little while." and "The page is fresh." (`composer_voice.py:565`, `:583`). Fix (S): pick the opener by the number (one, two to three, four or more) and by the gap (days, weeks, months, "two years").
- The line never says what matters today. With two overdue reminders, bins tonight and an exam in two weeks, all 14 seeds talk about how many notes were written. Fix (M): `today_line` leads with the day when there is one ("Bins tonight at 7. Two things are overdue.") and falls back to the notes line; the count bits appended in `dashboard.js:526` to `:532` go (G3's one count).
- The name is appended to every composed greeting (`routes_insights.py:187` `append_name: True` always; `dashboard.js:278`), every hour, while the model path uses it 75% of the time (`NAME_USE_CHANCE`). See Name use.
- Privacy, code only: `greeting_compose.gather` (`:169`) and `_recent_category` (`:143`) do not filter private or archived notes, so "Therapy on your mind lately?" could come from private notes; `voice.SHOWN` is the filter the today line uses. Not reproduced. Fix (S): use the same filter.

### G7. The composer does not know your name (med, ai; the owner's question)

With `display_name` "Alex" saved:

- "what's my name": "“Name” is one of the app's own tools, not something in your notes. Open its Help topic for the steps." (`composer_help.py:97`)
- "do you know my name": "I am not sure I can do that exactly. The closest I can do is to rename a note. Want one of those?"
- "who am I": "Only what your notes say, and none of them says anything about you yet. Write a note about yourself and I'll know it." (`personal.py`)
- "call me Alex", "my name is Alex", "what do you call me": note searches ("Call mum on sunday ...", "Call with Anna wants to try the new ramen place.").
- Guide, "what is my name": the Settings, Profile paragraph.
- "good morning" in chat: "Good morning, and welcome back. That is 10 days of writing in a row. Also, you last wrote ..." with no name.

Design and fix in "Name use" below.

### G8. Companion remarks repeat themselves inside one bubble and miss what is coming (med, copy)

`/insights/remarks`, verbatim:

- "On this day in 2024, you wrote “first frost this morning, covered the…”: “First frost this morning, covered the tomatoes”": the title-less name is the quote, so the note is said twice, and the person's words are recapitalised. Same in "A blank page so far today. The last thing you wrote, in “first frost this morning, covered the…” on 10 November 2024, says: “First frost this morning, covered the tomatoes”". Cause: `composer_voice.py:357` `_on_this_day` and `:476` `_empty_day` always emit name then quote. Fix (S): an untitled note is quoted once ("On this day in 2024: “first frost this morning, covered the tomatoes”"), as written.
- "Two months ago today, you wrote Gym routine: “Monday: squats and rows.”", "Five months ago today, you wrote Quarterly review ...", "A month ago today ...": a month-versary of an ordinary note is said like an anniversary, most days. Fix (S): months-ago only for one, three, six months and only when nothing better is queued; years always.
- "A blank page so far today. The last thing you wrote, in Harbor launch date Yesterday, says:" (capital Y mid-sentence; `v_empty_b_mid` " on " is dropped for a relative day).
- "Three of your notes this week mention “priya”" (a name in lower case: `_surface`, `:405`, returns the stem's first surface form).
- "Shopping has three of four items still open, the first: “Milk”" (the item is "milk").
- "“Email landlord about the leak” was due 8 November." then "“Pay phone bill” was due yesterday." then "“Take bins out” is due today.": three bubbles for one fact a person would say once, and nothing for tomorrow or this week from the notes (the dentist on the 21st, the exam, Anna's visit, the plumber on Thursday).
- The poke lines are a fixed table in the page (`avatars.js:2731`, two per mood; "Hi there.", "Good to see you.") and never use the notebook or the name.

Fix (M): remark kinds ranked by use: due soonest (one line for all overdue: "Two things are overdue: the landlord email and the phone bill."), a dated thing in the next three days from the notes (`composer_plan`'s day reader), an open item, then looking back. Keep the "never twice" key.

### G9. Statistics' ask box misreads tags as features and cannot say what the page shows (med, bug)

- "what's my most used tag": "Nothing is counted yet. Uses are counted on this computer as you move around the app." Cause: `stats_ask.py:30` `_USAGE` matches "most used" before the tag reader (`:218`). The chat answers the same question correctly.
- "how many links", "how many orphans", "what's my streak", "average words per note", "what's my busiest day", "did I write yesterday", "what haven't I used": the capability line ("I can count your notes, words, tags ..."), though the page shows links, notes with no link, the busiest day and unused features, and "when do I write the most" works.
- "this week vs last week": "Not so far. This week so far you have made 5 notes ..."; "compare this month to last month": "Yes. This month so far ...". A yes or no for a question that asked for neither (`stats_ask.py:146` `_compare`).
- "summarise my week": "... Most used tag: harbor (1 note). That is 2 more than by the same point last week." ("2 more" of what; a tag used once is not worth a clause).

Fix (S each): order the readers so a noun (tag, category, link) wins over the usage verb; add links, orphans, streak, average, busiest day, unused features from the numbers `notebook_stats.page` already returns; the yes or no lead only when the question opens with "am I", "did I", "have I"; "two more notes than by this point last week"; drop the tag clause under three notes.

### G10. The "make this a reminder" chip misses most intentions and cuts one mid-phrase (med, bug)

`/reminders/suggest`: of 15 messages, 2 offered a reminder. No offer for "don't forget to buy milk", "remember to take the bins out tonight", "call mum on sunday about christmas plans", "must book the venue next week", "todo: submit the report by 5pm", "exam on 24 november at 9am", "the plumber is coming thursday between 8 and 10". "I have to renew my passport before 30 November" offers the text "Renew my passport before".

Causes: `reminder_suggest.py:27` `_INTENT` needs "I/we" before "must" and has no bare imperative or "todo:" head; "don't forget to" with no time is refused at `:70` (no due time) although "tonight" parsed for the bins did not either (verify `reminder_parser.read_by_rule` on "take the bins out tonight"); the parser strips the date and leaves its preposition. A dated fact ("exam on 24 November at 9am") is never offered.

Fix (M): add bare "must", "todo:", "need to", an imperative with a time, and a dated event ("X on DATE at TIME") as "Remind you about X on ...?"; strip a trailing "before", "by", "until", "on" after the date is removed; no time gives an offer with tomorrow 9am marked as a guess. Tests: the 15 rows.

### G11. Topic summaries are one line of one note; totals and comparisons do no arithmetic (med, ai)

- "summarise harbor" (six notes): "Right, here you go. Harbor launch plan, boiled down: - Ship the Harbor mobile app to the public on 14 December. Other notes that match: ... Say “more” for the rest." All 20 "summarise X" answers have this shape and end on the chips "Show notes per week", "Show notes per tag", "What did I write this week?". "summarise my travel notes" gives the dated bullets (first audit F13 i named the two paths). "summarise the plumber": "... has too little in it to summarise." (say the sentence). "summarise priya" summarises the standup note and names it by its whole first line.
- "total budget for november": "Rent 650, from your Budget November note ... **Also:** Groceries 140. **Also:** Eating out 90." (the total is 955). "what's my total spending in october": "Nothing says that was paid yet; your notes price it: last service $420." "how much more did I spend eating out in october": the note's lines, no 70. "which is cheaper, free or plus": the tiers line. "what's the difference between the two budgets": "Budget October: Rent 650. Budget November: Rent 650." "compare the october and november budgets": headings "October" and "November budgets", three lines each, the two lines that differ (Groceries 120 and 140, Eating out 160 and 90) not shown.
- "whose birthday is next", "what should I read next", "what's next", "what are the next steps for harbor": "Dentist said floss more, next clean in six months. Cost was $180." ("next" matched as a content word.) "what did I think of piranesi": "Thinking, Fast and Slow, from your Reading list note."
- "what did I do in 2025", "what did I write in 2024": "Your notes don't mention “2025”." (a note exists in each year; "in june" works). "notes per month": a search; "draw a chart of my notes per category" works.
- "what keeps coming up", "any patterns in my notes", "any contradictions in my notes", "what am I forgetting", "what's most important right now": searches or "That's general knowledge"; the Patterns line, the supersede reader and the plan reader hold the answers.

Fix: (M) one summary path: a subject with several notes gets the `composer_study.py:349` shape, leading with the defining note, capped at six bullets; chips name the subject. (M) a labelled-amount reader for notes of "Label number" lines: total, one label's value, the difference between two notes line by line (only the lines that differ). (S) "next", "last", "first", "think", "per" are function words in a question, never the search term; "whose birthday is next" is the dated-people reader. (S) a bare year is a time window. (S) route "patterns", "keeps coming up" to `insights.from_session`, "contradictions", "changed my mind" to `supersede` and the insights "change of mind" rule, "what am I forgetting" to overdue plus open items.

### G12. Patterns, resurfacing and starter chips are counts and templates (low, copy)

- Patterns: "You have written about harbor 5 times since 3 September; that keeps coming up." (three in a row with the same hedge; subject in lower case; digits). `insights.py:271` to `:290`. Fix (S): the subject's surface form with its capital, number words to twelve, the hedge once per list, and a reason to care: "Harbor has come up five times since September, most recently today."
- Resurfacing reason: "72 days old, no links, never opened" (`routes_resurface.py:61` to `:68`), the same string on every row; an untitled note's title is its first 80 characters cut mid-word ("... get a suica card inste"). Fix (S): "From August; you have not opened it since." and the six-word name.
- Starter chips: "What have I saved about life?", "What have I saved about work?", "Summarise my notes in Life." (`routes_chat.py:138` to `:145`: category names said as topics). `composer_voice.suggested_searches` already writes "What is the latest on Harbor launch date?", "What is still open in Shopping?" and is not called by any route. Fix (S): `/chat/suggestions` uses it, with what is due first ("What's due this week?").
- Day digest: a title-less note is quoted whole (`day_digest.py:46` `_first_line`, 81 characters seen), and "And two more." has no noun.

### G13. The miss lines blame the model (low, copy)

"The local model is not running, and nothing in the app's own help text matches that." (`help_chat.py:838`); "The local AI isn't running, and I couldn't read a time from that." (`routes_reminders.py:667`); "Finding where notes disagree needs a model to read them, and none is running." (`tool_say.py:315`, while `supersede` finds dated changes with none); `/entries/tensions` returns `status: "no_model"` and an empty list; "That's general knowledge, and with no model running I only know what your notes say"; "From your notes, no AI." (`activity.py:627`). The owner's north star is that nobody needs to install a model; these lines tell every such person the app is missing a part. Fix (S): say what was not understood and what to try; mention a model only where the task is writing new prose.

### G14. Smaller, each verified

| id | where | seen | fix |
| --- | --- | --- | --- |
| a | Ask, "what are my reminders" | a table with an empty third column header ("| Reminder | When | |") | drop the column |
| b | Ask, "what do I need to do" | "What is left, as your notebook has it: 5 reminders and 6 unticked checklist items." then the same task twice (reminder "Renew passport" and the Todo item) | merge a reminder and a checklist item with the same words |
| c | Ask, "shortest note" | "Your shortest note is “Gift ideas for mum”, about 0 words." | "has only a title" |
| d | Ask, "notes without a title" | lists "Suica", a note whose only line is its title | a one-line note is titled |
| e | Ask, "the harbor launch", "the japan trip" | chips "What's the latest on the Harbor?", "When did I last write about the japan?" | the chip keeps the whole subject (first audit F5 class) |
| f | Ask, "what do I know about harbor" | "You have five notes about harbor." then lists six | count what is shown |
| g | Guide, "how do I export my notes" | second paragraph is about duplicate tidying | `_second_sentence` must come from the lead topic's own section |
| h | Meeting card, `/entries/40/meeting` | `attendees: [], decisions: [], actions: []` for a note with "Attendees: Mia, Priya, Jon." "Decisions: ..." "Actions: ..." inline, while Ask reads all three | let `meeting_summary` read "Label: value" lines |
| i | Dashboard dates | "Tue, Nov 10, 5:21 PM", "November 10", "Nov 9 to Nov 10" in tiles beside the composer's "Tuesday 10 November" (en-US browser) | one date formatter for composed and page text |
| j | Reminder parse, "something sometime" with the fake model up | a reminder "Something sometime" for tomorrow 09:00 | refuse a parse whose text has no time word |

## Parity (CHAT_PLAN decision 75), both ways

Model-on runs used the fake transport: which path a turn takes, what the prompt holds and which events come back are verified; what a real model writes is not.

### What the composer does that the model-on path does not

| surface | composer | model on | where | fix |
| --- | --- | --- | --- | --- |
| Chat chips | every composed answer has next-step chips | 26 of 30 model turns had no chip and no offer | the turn ends without the composer's `asks`; `/chat/followups` is a second model call | (M) hand the composer's chips with the facts (first audit F14) |
| Chat greeting | streak, last note, reminders due | "good morning" goes to the model with none of them in the prompt (system prompt 1,007 characters, no "bins", no streak) | `routes_chat.py:879` `_welcome` is not reached with a model up | (S) pass `welcome_line`'s facts as the turn's facts |
| Chat, "what's on today", "do I have reminders today", "did I pay the phone bill" | agenda card (with G3's gaps) | the agent round gets the ten newest notes; no reminder is in the prompt | first agent round inspected: no reminder text | (M) the composer's agenda facts go in before the agent runs |
| Chat, "weekly review" | (G4) | agent round, no week facts | same | with G4 |
| Chat, "what's my name" | (G7) | name in the prompt only when "Let Atlas use this profile" is on (`librarian.py:268` to `:279`); off by default | by design for the model; see Name use | none for the model; the composer answers it first |
| Dashboard greeting | "Day 10 of your writing streak", "Work on your mind lately?" | the prompt has the time of day and a flavour only (`routes_insights.py:105` to `:125`, `:248`) | `_ai_greeting` | (S) give it the same `NotebookFacts` as one line; or keep the composed line when it carries a fact |
| Weekly digest | overdue and coming reminders | the model's prompt is the week's notes only; its reply replaces the composed digest (`routes_insights.py:933`) | `_digest_notes` | (S) add the reminder lines to the prompt, or print the composed header above the model's prose |
| Guide | greeting and thanks replies, starter chips, "asks" chips | with the model up every Guide turn, "hello" included, is a model call; replies carry `badges`, `sources`, `system` and no `asks` | `help_chat.py:1275` `answer` | (S) social replies stay composed; run `with_asks` on the model's reply too |
| Reminders magic add | refuses "something sometime" | makes a reminder called "Something sometime" | `routes_reminders.py:622` | G14 j |
| Today line, remarks, day digest, patterns, statistics ask, resurfacing | composed | the same composed text; no model call (0 calls measured) | | parity holds; a model adds nothing here |
| Counts and sums ("how many notes", "650 plus 140") | composed | composed, model not asked for the answer | | parity holds |

### What the model-on path can do that the composer cannot

From the 73 tools in `/chat/tools` against 38 act phrasings with no model:

| ability (tool) | composer with no model | fix size |
| --- | --- | --- |
| snooze or move a reminder (`set_reminder` again) | crashes (G2, `task_acts.py:679`) | S |
| edit a note's text (`edit_note`) | "edit the wifi note: ..." returns an unrelated overview; append works with a confirm | M |
| categories (`create_category`, `rename_category`, `merge_categories`, `delete_category`) | "create a category called Hobbies" is a note search | M |
| documents (`create_document`, `list_documents`, `get_document`) | "show my documents" works; "make a document about harbor" is a search | M |
| contradictions (`find_contradictions`) | "needs a model" (`tool_say.py:315`), "any contradictions" is a search; `supersede` and the insights change-of-mind rule could answer dated ones | M |
| structure (`notebook_structure`, `path_between`, `related_notes`) | "which notes are connected to nothing" (Statistics shows 41), "how are japan trip and kyoto ideas related", "what are the clusters": searches | M |
| chat history (`search_chat_history`) | "what did we talk about last time": search for "talk" | S |
| the bin (`restore_note`) | "restore the last deleted note": "I found nothing in the bin about “last deleted”."; "what's in my bin": a search | S |
| skills (`run_skill`) | "list my skills" works; "run the weekly review skill" is a search | S |
| turning text into things (`set_reminder` many, `create_note`) | "turn the action items into reminders", "make a checklist from the three gates": searches (yet "what do I need to review" offers "Save it as a checklist note?") | M |
| planning (`make_plan`), drafting, translating | "Writing that needs a model" (honest; G13 wording) | L, or leave |
| multi-note summary (`summarize_notes`) | one line of one note (G11) | M |
| archive, merge, split, duplicate, export | honest hand-offs ("that is done in the app ... use Merge"), except "export my notes": "I am not sure how to do that one." | S for export |
| web (`web_search`, `read_url`) | says web is off and where to turn it on (good) | none |
| boards and maps (`add_whiteboard_card`, `create_mindmap`, ...), `rename_tag`, `delete_tag`, `save_user_preference`, `check_learned` | not driven | not verified |

## Name use

Today: the dashboard appends ", Alex" to every composed greeting; the model sees the name only behind the profile switch; chat labels show it. The composer never says it and cannot answer a question about it (G7).

The name is local data read by a local writer, so the composer may use it with the profile switch off (that switch promises what a model reads, `librarian.py:270`); say so in the switch's help line.

Rules (one helper, `ai/address.py`: `name()` from `display_name`, and `maybe(name, slot, seed, said)` that returns ", Alex" or ""):

1. Answer it. "what's my name", "do you know my name", "what do you call me", "who am I": "You're Alex, going by your profile." plus, for "who am I", what `personal.py` knows. No name saved: "I don't know yet. Tell me, or add it in Settings, Profile." with a chip.
2. Learn it. "call me Sam", "my name is Sam": a confirm card "Call you Sam from now on?" that writes `display_name` (the model's `save_user_preference` does this; parity). `vocative.py` already separates an address from a request.
3. Greet with it, once. The first greeting of a chat and the first dashboard visit of a day slot: "Morning, Alex." A second "hi" in the same chat: "Hello again." with no name.
4. Dashboard: the server decides, not the page: `append_name` true for about one greeting in three with no model, always for the first of the day, never on a question-shaped fact line where it reads as a challenge ("Work on your mind lately, Alex?"), never twice running.
5. Use it where a person would: after a gap of a week or more ("Good to have you back, Alex."), a milestone (streak of 7, 30, 100; the hundredth note), an apology or a refusal ("Sorry, Alex, I can't find that one."), thanks ("Any time, Alex." at most once per chat), and the companion's first remark of the day.
6. Never in a fact answer, a list, an agenda, a confirm card, an error, a Guide how-to, a notification title, or two turns in a row; never more than once in a message; never guessed from a note; cut at 40 characters as the dashboard does.
7. The Guide: "what is my name" answers with it and the Profile badge; nothing else there uses it.

Eval: over a 20-turn chat the name appears at most three times and never in consecutive turns; all six name questions in G7 answer; the dashboard shows the name on at most 40% of 168 hourly greetings.

Effort: M (the helper, the three readers, the dashboard flag, tests).

## Should be composed but is not

| where | today | composed instead |
| --- | --- | --- |
| Dashboard sub line counts (`dashboard.js:526` to `:537`) | "· 1 reminder coming up · 10-day capture streak" | part of `today_line`: "Bins tonight at 7. Ten days in a row." |
| Glance tiles (`dashboard.js:633` to `:683`) | "1 due today", "No meetings today / Nothing on the calendar", "5 to file / Atlas was unsure where these go", "Pick up where you left off" | one line each from the server with the thing named: "Bins at 7pm", "Five notes need a home, the newest is Shopping" |
| This week widget (`statistics.js:121`) | "Notes made 5 up from 0 last week", "Words added to older notes 0 the same as last week" | one sentence from `week_review` over the numbers; zero rows unsaid |
| Activity heatmap caption (`dashboard.js:3018`) | "5 notes in the last year · busiest day November 10 (5 notes)" | "Five notes so far, all of them today." |
| On this day, empty (`dashboard.js:4229`) | "Nothing from this date yet. What you write today comes back here next month." | fine as fixed copy; when there is a note, use the remark's sentence, not the raw note |
| Resurfacing reason (`routes_resurface.py:61`) | "72 days old, no links, never opened" | G12 |
| Patterns (`insights.py:271`) | "harbor came up 5 times since 3 September" | G12 |
| Weekly digest (`activity.py:620`) | the creation log | G4 |
| Day digest empty (`day_digest.py:169`) | "Nothing is due and nothing changed since yesterday." | add the next thing: "Nothing due today. Next up: the dentist on the 21st." |
| Chat empty notebook | "Your notebook has nothing today.", "Nothing was made, edited or binned this week." | "Nothing yet. Write a first note and I'll have something to say." (one line, same on every empty surface) |
| Starter chips (`routes_chat.py:138`) | category names in a template | `suggested_searches` plus what is due (G12) |
| Statistics ask miss (`stats_ask.py:46`) | the capability paragraph for "hello" and every unknown | nearest reader's answer, or two example chips |
| Reminder notification body (`reminder-notify.js:92`) | title plus "About <note title>" (code only) | "Bins out, due now. From your Todo note." (not driven) |
| Companion poke lines (`avatars.js:2731`) | 52 fixed lines | one in three pokes says a remark from `/insights/remarks` (what is due, an open item) |
| Guide starters and "Three to start with:" | fixed | the open tab's three most asked how-tos (the tab is already sent) |
| Tidy review rows (`/tidy`) | "Tags used once ... count 14" | the lead row said as a sentence on the dashboard: "Fourteen tags are used once; Tidy can merge the look-alikes." |

## What is already good

- The day digest's counts are right and said in words: "One reminder due today and two overdue.", "Four notes written since this time yesterday."
- `composer_voice.week_review`'s shape (G4) and `suggested_searches`' chips are better than what the routes serve; they only need wiring.
- The composed greeting's fact lines are true and short: "Day 10 of your writing streak", "It has been N days since your last note".
- Guide answers that hit are good and carry working badges: set a reminder, link two notes, undo, privacy ("No. Your notes stay on this computer ..."), web search state ("Web search is off now."), phone access, sync ("There is no sync between two copies.").
- Statistics ask: counts, month counts, first and newest note, busiest weekday and the month comparison are right.
- Acts with a named target confirm before changing: tag, untag, link, unlink, delete, rename, move, append; pin and tick act at once and say so; honest hand-offs for archive, merge, split, duplicate.
- Did-I questions over checklists: "Yes, “Book flights” is ticked off in Todo.", "Not yet: “Renew passport by 30 November” is still open in Todo."
- `/reminders/when` read 13 of 14 phrasings; "asap" is refused in plain words.
- No model call is made for the today line, remarks, day digest, patterns or statistics with a model up (0 calls measured), so those cannot hang on a slow model.
- An empty notebook never 500s on any of the 28 routes; the dashboard had no horizontal scroll at 390 (document width 390).

## Not verified

- Real model inference on any surface (fake transport only): the model's greeting, digest prose, Guide answers and tool use.
- The desk companion window, notification popups, the companion bubble and the Guide panel as drawn; dark mode, keyboard, screen reader; performance. The private-category greeting leak (G6) is from reading the code.
- `composer_aware` closing lines in the Guide (the probe sent no `actions`).
- Tool parity rows marked "not driven"; Confirm was never pressed on an act card.
- "don't forget to ..." with no time (G10): the refusal point was read, not stepped through.
- The hand counts in G5 (15 wrong leads, 9 misses of 97) are one reader's judgement.
- File name: the agent definition asked for `audit-<date>-composer.md`; the brief named this file, which is used.
