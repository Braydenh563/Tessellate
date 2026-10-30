# Second eye 2026-10-30: the composer and its architecture

Read-only review on head of `main` as checked out. Method: the 60-note stress notebook (`scratchpad/stress/notes.jsonl`) run through `composer_digest.answer` and `composer.compose` directly (all 300 graded queries, plus about 60 probes of my own), the same questions on a live server (`serve.sh 8781`, the 59 non-empty stress notes loaded, then 420 filler notes), every compiled regex in the package timed on 3,000 and 20,000 character inputs, and the chat and notes routes read for injection and auth. Every provider ran on a fake transport; no model answered anything here. Rows already in `audit-1030-composer.md` (Z ids) and `scratchpad/stress/classes.md` are not repeated; where a class there has a different root cause than recorded, the row says so.

Counts: high 3, medium 7, low 5. Ranked by severity times reach.

## Findings

### F1 (high): the spending sum reads only the newest 400 notes and says "no amounts" past them

- Repro: live server, 483 notes, the ten notes with amounts older than 420 filler notes. `POST /chat/stream {"question":"How much have I spent?","answer_from":"notes","notes_only":true}` answers `I found no amounts spent in your notes.` With 63 notes the same question answered `$783 spent ... $753 net`. `What is my biggest expense?` becomes `None of your notes mention "biggest expense"`.
- Root cause: `src/tessellate/api/routes_chat.py:1691` `manager.list_entries(session, limit=400)` (pinned first, newest first) is the only scan for `records_amounts`; nothing past 400 is read, and `composer_money._spent` (`composer_money.py:280`) then states the absence as a fact.
- Class: every total, net, due, biggest and measure question (`composer_money.asks`) on a notebook over 400 notes, which is the ordinary case for a daily notebook. The oldest spending drops out first, so "this year" and "all time" answers go quietly wrong before "no amounts" appears.
- Fix: scan without a limit using an indexed filter (FTS or `content LIKE` on the spending verbs, private excluded) and read only the hits; if a bound must stay, say "in your newest 400 notes" instead of "in your notes".

### F2 (high): "who is X" cites one note for sentences taken from several

- Repro: `composer_digest.answer("Who is Sam?", notes)` on the stress notebook: six lines (`Sam comes up in nine notes.`, `Sam Patel is your manager...`, `Sam Hoyle is your cousin...`, `Sam wants PTO requests...`), one grounding row, `note_id` 1 only. The cousin line is note 2, the PTO line note 5.
- Root cause: `src/tessellate/ai/composer_digest.py:2891-2900` `_who` appends a line per found sentence in the loop but one row, for the lead fact, after it.
- Class: every person named in two or more notes; the sources column under the answer names the wrong note for most lines and `validate.report` cannot trace them.
- Fix: inside the loop append `_row(body, Fact(v, s2, "", ""))` (or the dict form used at line 2900) per line; test "who is X" over three notes expects three rows with three ids.

### F3 (high): "still on my list" says a box is ticked that is not, and contradicts "what is still open"

- Repro (stress notes 6 and 7): `Is renewing the library membership still on my list?` answers `No, "Renew library membership - due 28 October." is ticked off in Admin bits.` citing note 6, whose box is `[ ]`. The record of the doing is note 7 (`Renewed my library membership today`), which is not cited. In the same notebook `What's still open in Admin bits?` answers `2 still to do on Admin bits: Renew library membership ... Back up laptop`, and `When is the laptop backup due?` closes with `Remind you to renew library membership - due 28 October?`.
- Root cause: `src/tessellate/ai/composer_slots.py:395-400` `_is_still` folds `_done_later` into `done` and then words it as the checkbox state (`is ticked off in {title}`) citing the task line; the open-list reader at `composer_slots.py:110-127` and the digest's offers never consult `_done_later`, so three answers disagree about one item.
- Class: any checklist item done in a later note rather than ticked (the pattern note 7 is written to test); every `did I`, `still on my list`, `what is left` and `remind me` answer over it.
- Fix: when `done` comes from `_done_later`, say `Done: your note of 29 October (Membership sorted) records it; the box in Admin bits is still unticked` and cite that note; make the open-list reader and the reminder offer call the same `_done_later` so one item has one state.

### F4 (medium): mixed currencies are dropped from the total without a word

- Repro: three notes `Paid $100 for the lamp`, `Paid £50 for the train`, `Paid €20 for lunch`; `How much have I spent?` answers `You paid $100 for the lamp, going by Paid $100 for the lamp on 2 October.` The £50 and €20 are not mentioned. `What is my biggest expense?` also says the lamp.
- Root cause: `src/tessellate/ai/composer_money.py:283-284` keeps only items whose symbol equals the first item's symbol.
- Class: any notebook with two currencies (travel, a move, an overseas shop); "biggest expense" compares numbers inside one currency only.
- Fix: group items by symbol and say each group (`$100 and £50 and €20`); for "biggest" say the largest per currency or decline to compare across them.

### F5 (medium): month sums ignore the year; "this year" and "last year" are not read

- Repro: notes `Paid $100 for the lamp` (2026-10-02) and `Paid $400 for the boiler repair` (2025-10-11). `How much did I spend in October?` answers `$500 spent in October`; `How much have I spent this year?` and `How much did I spend last year?` both answer `$500`.
- Root cause: `src/tessellate/ai/composer_money.py:138-156` `_month_asked` and `_in_month` hold a month number only; `_subject` strips `this year` and `last year` as window words (`recognise.without_windows`) and nothing reads them.
- Class: every money question with a year word, and every month question on a notebook older than a year (see F1 for why the older notes are the ones that survive).
- Fix: parse a (year, month) window with `recognise`'s own window reader, default the month's year to the latest one with items, and filter on both.

### F6 (medium): model on and model off disagree on money and checklist questions

- Repro by reading (no real model ran): `_facts_turn` (`src/tessellate/api/routes_chat.py:4402-4423`) hands a model-on turn the engine's answer only for `prepared["stats"]` (counts, arithmetic) and `tool_read`. `composer_money` sums and `composer_slots` yes/no answers are not facts, so with a model on, "how much have I spent" is written by the model from up to 400 raw notes (`routes_chat.py:1686-1693` still swaps retrieval for every amount note), and "did I renew the membership" from the five retrieved notes. `_check_model_prose` (`routes_chat.py:4674-4700`) can only append a heads-up when the sum is in no note; a wrong sum of figures that are in the notes is not caught.
- Class: every question the composer answers exactly (money, slots, computed dates, counts by list) on the Chat tab or Ask with a model, which the owner said should be "what the composer can do but better".
- Fix: let `_facts_turn` run `composer_money.answer` and `composer_slots.answer` over `prepared["notes"]` and pass the lines as facts (the same `fact_check.keeps` gate), so the figure is the engine's on both paths.
- Not verified with a model: the seam only.

### F7 (medium): the digest's ContextVars are set per answer and never reset

- Repro: in one thread, `answer("Who is my manager?", notes, voice="playful")` then `composer_digest._VOICE.get()` is `playful`, `_VIEWS.get()` holds 59 views after a following `answer(q, [])` returned None before `_begin`, and `_TIMED` keeps the previous question's value. On the live route each `next()` of the stream runs in a copied context (`routes_chat.py:4926` `run_in_threadpool`), so requests do not see each other (verified: a fresh context reads the defaults).
- Root cause: `src/tessellate/ai/composer_digest.py:3068-3084` `_begin` sets ten vars (`_NAMES`, `_TODAY`, `_TIMED`, `_CURRENT`, `_VOICE`, `_TURN`, `_SEED`, `_GAPS`, `_VIEWS`, `_KNOWN`, `_ASKS_WORDS`) with no token or reset; `all_said` (3043) sets two of them and reads the rest; `web` and `PHRASES` read `_TIMED`/`_VOICE` wherever they are called.
- Class: every in-process caller that is not the stream: `_told_sources` (`routes_chat.py:3435`) answers up to three earlier questions, leaving the last one's names, seed, voice and timing for `all_said` of the current turn; `routes_entries.py:3711` and `routes_insights.py:423` (the Today and digest voices) and the test suite run in one context, so answers depend on the question before (`tests/test_composer_dates_1441.py` already sets vars by hand to cope).
- Fix: `_begin` returns the tokens and `answer`, `all_said`, `web` reset them in `finally` (as `sample` at 329 already does); or run the body under `contextvars.copy_context().run`.

### F8 (medium, perf): every answer re-reads every note it was given, and a "more" turn does it four times

- Repro: `composer_digest.answer("What do I know about Hobart?")` on 600 notes: 0.78 s, of which `_begin` → `composer.read_note` 0.53 s (33,000 `_stem` calls); 60 notes 0.32 s. The money path (F1) hands up to 400 notes to the same reader; `_told_sources` (`routes_chat.py:3435`) answers the last three questions again over the same notes before `composer.compose` answers "tell me more".
- Root cause: `composer_digest.py:3071` builds `NoteView`s from scratch per call; `composer.py:1228` `read_note` has no cache; the route builds the same list for the digest, the fallback and each re-answer.
- Class: every composed turn; cost grows with notes retrieved, which the money and recall windows (`routes_chat.py:1628`) make large.
- Fix: an LRU on `read_note` keyed by (`id`, `content_hash` or `edited_at`, `created_at`), and `_told_sources` reading the saved grounding rows of the earlier turns (`_save_ask_turn` stores them) instead of answering again.

### F9 (medium): passive yes/no questions miss the checklist reader

- Repro: `Did I renew the library membership?` → `Yes, your note of 29 October says so`; `Have I renewed my library membership?` → the same; `Is the library membership renewed?` → a quote of the Admin bits checklist with no yes or no. `Did I back up the laptop?` → `Not yet: "Back up laptop - due 2 November." is still open`; `Is the laptop backed up?` → the checklist quoted plus `You have just the one note on that so far.`
- Root cause: `src/tessellate/ai/composer_slots.py:825` `answer` routes on `did I`, `have I` and `still` openers; `is X done/renewed/backed up/paid` (be-verb plus participle) is not a shape, so the ordinary digest quotes.
- Class: every passive form of a checklist question, and "is X paid", "is X booked", "is X sent".
- Fix: add `^(?:is|are|was) (?:the |my )?(?P<thing>.+?) (?P<verb>\w+ed|done|paid|sent|booked)\??$` to the did reader, mapping the participle to `_verb_forms`.

### F10 (medium): "count my notes about X" answers one note and claims it is the only one

- Repro: `Count my notes about Hobart.` → `Don't count the balance as spending yet, from one of your notes. ... You have just the one note on that so far.` Six notes are tagged Hobart; `How many notes do I have about Hobart?` says six. `Do I have notes about Hobart?` and `How much have I written about Hobart?` each quote one note.
- Root cause: the question's verb (`count`) becomes a subject word and matches `Don't count the balance` (the class of Z16 to Z18); new here is `composer_digest.py:2780-2783` `_single_close`, which says `only_note` from `len(members) == 1` without checking how many views carry the topic, so the footer asserts a false count.
- Class: every subject word that is also a common verb (count, note, list, check, record), and every single-member answer on a many-note topic.
- Fix: `_single_close` says `only_note` only when `_members(topic, views)` has one view; strip count and list verbs from `_subject` before matching.

### F11 (low): the money subject keeps the question's verbs ("on book is")

- Repro: two notes `Paid $36 for my copy of Piranesi` and `Paid $20 for a used copy of Earthsea`; `How much book spending is actually recorded?` → `I found no amounts spent on book is in your notes.` On the live server with two matching items it read `You spent $72 on book is, going by Bookshop receipt`.
- Root cause: `src/tessellate/ai/composer_money.py:231-237` `_subject` strips a leading preposition and `my` only; `is`, `actually`, `recorded` stay as the "subject as typed".
- Class: every total question with words after the subject (`how much X spending is there`, `what did X cost me in total`).
- Fix: cut `said` at the first auxiliary or adverb (`is|was|are|actually|really|recorded|logged`) and drop `_STOP` words from the typed form too.

### F12 (low): a subject matches by exact stem only, so "books" misses "Bookshop receipt"

- Repro: the same two notes; `How much have I spent on books?` → `I found no amounts spent on books in your notes.`
- Root cause: `src/tessellate/ai/composer_money.py:160-168` `_about` tests `st in have` on stems; `book` is not `bookshop`.
- Class: compounds and category words (books/bookshop, food/foodhall, bike/bikeshop, rent/rental).
- Fix: prefix match on title and tag words (`any(w.startswith(st) for w in have)`), and when the subject matches nothing say the total with `I could not tell which were books` rather than "no amounts".

### F13 (low, architecture): eight readers of a note's title disagree

- Repro: run `commands._title`, `composer._title`, `composer_lists._title`, `composer_study._title`, `questions._title`, `study.title_of`, `tool_say._title`, `composer_frame.note_label` on `[ ] Renew library membership - due 28 October.\n[x] Email the landlord`: results `'[ ] Renew library membership -…'`, `'your untitled list'`, `'[ ] Renew library membership - due 28 October'` (three spellings) and `''`; on `**Admin bits**\nRenew membership` seven say `Admin bits` and `commands._title` says `**Admin bits**`.
- Root cause: eight private readers (`commands.py:848`, `composer.py:1018`, `composer_lists.py:378`, `composer_study.py:115`, `questions.py:87`, `study.py:167`, `tool_say.py:71`, `composer_frame.py:262`) each with their own markdown and checkbox rules.
- Class: every surface that names a note (the sources column, the why line, chips, the open-note answer, study decks) can name the same note differently in one answer.
- Fix: one `note_title(content, *, size=None)` in `composer_frame` with the checkbox and bold rules; the others call it (a lint in `tests/test_ui_recipes.py` style that forbids a second `def _title` in `ai/`).

### F14 (low, security): two compare regexes are quadratic on whitespace; not reachable through the route today

- Repro: `composer._COMPARE_SIDES[0].search(" " * 20000)` 65 s, `composer_digest._ASKS["compare"].search(" " * 20000)` 47 s (1.5 s and 0.9 s at 3,000). `ChatRequest.question` allows 20,000 characters (`routes_chat.py:392`). Through `POST /chat/stream` the same 20,000-space question answers in 0.04 s because `composer.rephrase` (`composer.py:530`) and `composer_lists.clean` collapse whitespace before any reader. Smaller ones on 3,000 spaces: `task_acts._DONE_TAIL` 0.60 s, `activity._DATE_STUB` 0.54 s, `composer_frame._PRESENTED_END` 0.36 s, `task_acts._TAIL_KIND` 0.36 s, `recognise._CLOCK_TAIL` 0.34 s (1,016 patterns timed; the rest under 0.1 s).
- Root cause: `composer.py:787` `^(?:...\s+)?(?P<a>.+?)\s+...` and `composer_digest.py` `_ASKS["compare"]` `[\w' -]{2,30}?\s+or\s+`: a lazy group followed by `\s+` backtracks over every split of a long run of spaces.
- Class: any new caller that passes raw text (a note's own line, an imported question list) to these readers; the guard is one `" ".join(q.split())` away from each of them, not in the pattern.
- Fix: collapse whitespace once in a `ChatRequest` validator and in `read_note`'s line splitter, and bound the lazy groups (`[^\n]{1,200}?`).

### F15 (low): an offer suggests a reminder for a task a later note records as done

- Repro: `When is the laptop backup due?` on the stress notebook ends `Remind you to renew library membership - due 28 October?` after note 7 (29 October) says it was renewed.
- Root cause: the offers in `composer_digest._offer`/`_finish` pick the first open checklist line of the lead note and never ask `composer_slots._done_later` (`composer_slots.py:222`).
- Class: every reminder offer over a list whose items were done in prose.
- Fix: the offer filters its candidate through the same done check as F3.

## What held up

- SQL: every query is SQLAlchemy with bound parameters; `LIKE` arguments go through `like_escape`/`autoescape` (`ai/filters.py`, `ai/slash.py`, `ai/timetravel.py`). No f-string or `%` SQL anywhere in `src/`.
- Auth: every data router is mounted with `require_unlock` (`api/app.py:1331-1448`); the open routers serve static files from an allow-list (`ai/translate.py:85-100`), the sandbox page, and the settings and reminders "open" routes. Before a password exists the API is open on loopback by design (`routes_auth.py:666`).
- Private notes: a private note holding `Paid $555 for the therapy session` was not read by the spending sum, the biggest-expense answer or the search path, with the vault open (live server; the money scan at `routes_chat.py:1691` does not filter `is_private` itself, so the protection is the sealed content, worth a direct `is_private == False` clause there too).
- Prompt injection: note, file and web text reach the model fenced (`ai/fence.py`); destructive tools park for a card; a note clipped from the web or imported starts the turn tainted (`agent.py:3276-3278`) so `read_url` and `web_search` park too. Verified by reading; the loop was not run with a model.
- Latency on the route for well-formed questions: 0.09 to 0.18 s at 63 notes, 0.1 s at 483 notes (the money scan is cheap; the cost is in reading, F8).

## What I could not verify

- Any model's prose (fake transport only): F6 is the seam, read from code.
- F1 at exactly 400 notes with pinned notes ahead of the window (the probe used 420 filler notes after the amount notes).
- The frontend's rendering of the grounding rows in F2 (the row count is from the result dict).
- The test-order coupling in F7 across the whole suite (one file's hand-set vars found by grep, not a failing run).
