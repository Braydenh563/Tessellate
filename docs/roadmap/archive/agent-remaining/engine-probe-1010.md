# Engine probe, 2026-10-10 (Fable): what the real route answers today

Sixty questions were put to `composer.compose` directly and twenty-seven to
`POST /chat/stream` (notes only, no model) over the 77 showcase notes
(`tests/fixtures/composer/showcase_725.json`, seeded fresh so every note is
dated today and uncategorised; time questions are therefore not judged
here). Scripts: `$S/probe_composer.py`, `$S/probe_route.py`. Each row is a
failing test for Brief 39; the first block is bugs outside Phase 6's
numbered steps and comes first.

## Bugs (step 0 of Brief 39: a test each, then the fix)

| # | Question | Today, on the route | Expected |
| --- | --- | --- | --- |
| P1 | "who is Sam", "what did Sam say" | "Same breakfast as the long runs" (`Sam` matched inside `Same`) | subject terms match on word boundaries; when no note names Sam, say so |
| P2 | "hello", "thanks", "ok", "what is your name", "what can you do" with answer-from-notes on | an empty answer (no `answer` event) | the social or about-app answer, exactly as with the setting off |
| P3 | "what is 12 * 7" on the route | "Your five newest notes" (the recent fallback ran before `_sum`) | "12 * 7 is 84." (it is right when `compose` is called directly: the route's recent mode skips the utilities) |
| P4 | many answers | "(Your notes say this four times.)" on a sentence that exists in exactly one note (`Bib and pins the night before`; also `Whetstone at 15 degrees` four, `Cook grains` five) | the repetition count counts distinct notes, never retrieval rows or chunks; when it is one, nothing is said |
| P5 | "how many notes are about Harbor" | "You have 77 notes." (`notebook_stats` answered the question without its "about Harbor") | a count over the retrieval ("At least four of your notes mention Harbor", which `compose` already produces directly) |
| P6 | "what did I write last week", "when did I last write about running" | "No note found brings up 'last'"; "I couldn't find any reference to 'running'" with running notes present | time words (`last`, `recent`, `week`, `ago`) are never subject terms; the window goes to `when.py` |
| P7 | "are you an AI", "summarise my gym notes", "what did I write most about" | "Your five newest notes" | about-app answer; "No notes mention gym"; a measured answer (top terms or categories) |
| P8 | first `compose` call | 583 ms (the tables build on first use), then under 20 ms | the first call under 100 ms, or the tables built at import behind the 0.2 s import budget |

## Phase 6 shapes the probe confirms are missing (the spec covers them)

| # | Question | Today | Spec step |
| --- | --- | --- | --- |
| P9 | "what time is it", "what day is it today", "convert 5 miles to km" | a note quote ("Due in March") | utilities |
| P10 | "how many days until the dentist", "is the dentist before the boiler service" | the quote, no computation | the computed kind |
| P11 | "how many times did I mention Porto" | a quote and the repetition note | a count ("Porto appears in 5 notes, 7 times") |
| P12 | "list my work notes", "list everything tagged launch" | the checklist of one note | a list filtered by category or tag, or "no notes in Work" |
| P13 | "what are all the dates in my notes", "what is due this week" | a quote; nothing | the fact layer's dates and reminders |
| P14 | "delete the boiler note", "remind me about the dentist tomorrow", "move the sourdough note to Cooking", "tag the knife note with kitchen" | treated as questions | acts, with confirm and undo |
| P15 | "Here's the exact date:" followed by no date; "Out of the notes I looked at, one mentions X and one mentions Y. This is the information for both sides." | a lead-in promising a shape it does not deliver; a 20-word lead-in | a lead-in is chosen after the parts and names only what follows; the compare opener under eight words |
| P16 | "what is still open on the launch" | "63 open tickets" from another note | the unchecked checklist items of the launch note (the checklist parser exists; the shape does not reach it) |

Numbers: 60 direct questions in 0.89 s total; the route's answers in the
probe output. Not verified: time windows (every seeded note is dated today);
the social path with the setting off (not probed); P4's cause (fusion of
retrievers or chunking) is a reading, the count is measured.

## The other deterministic parts, probed the same way (`$S/probe_determ.py`, now = Tuesday 2026-10-06 14:30)

### `when.resolve` (Brief 39, step: the time window; TIMELINE Phase 5 shares it)

| Phrase | Today | Expected |
| --- | --- | --- |
| "last friday" | Fri 2026-10-09 (the next one) | Fri 2026-10-02 |
| "yesterday", "a week ago", "3 weeks ago", "the week before last", "since march", "in march", "march" | None | the past is a window: 2026-10-05; 2026-09-29; 2026-09-15; the week of 21 to 27 September; 1 March to now; 1 to 31 March 2026 (the most recent March) |
| "the 21st", "on the 14th", "21st of next month", "end of the month", "next month", "mid november", "end of day", "this weekend", "next weekend", "in a fortnight", "christmas", "new year" | None | 2026-10-21; 2026-10-14; 2026-11-21; 2026-10-31; 2026-11-01 (a window); 2026-11-15; today 17:00; Sat 2026-10-10; Sat 2026-10-17; 2026-10-20; 2026-12-25; 2027-01-01 |
| "later today" | today 09:00 (before now) | today, now plus three hours, capped at 20:00 |
| "2/11", "11/2" | None | the person's date order from their locale setting; say which was assumed |
| "noon", "at 5", "5pm", "17:30", "tomorrow at 9", "next tuesday morning", "first thing monday", "in 90 minutes", "nov 2", "2026-11-02", "the day after tomorrow" | right | hold |

### `when.parse_reminder_text` and `reminder_parser.parse_relative` (TIMELINE Phase 5 decision 15 to 18; Brief 55)

| Text | Today | Expected |
| --- | --- | --- |
| "water the plants every tuesday" | text "Water the plants every", one date | a recurring reminder (weekly, Tuesday), text "Water the plants" |
| "every morning at 7 stretch" | text "Every stretch", today 19:00 | daily at 07:00, text "Stretch" |
| "dentist 21st 9am" | tomorrow 09:00 | 2026-10-21 09:00 |
| "pay rent on the 1st" | None | 2026-11-01, monthly offered |
| "remind me in 20 minutes to check the oven" | text "In 20 minutes to check the oven" | text "Check the oven" |
| "in 1.5 hours", "tomorrow morning", "in 6 months", "in a year" | None | 16:00; tomorrow 09:00; 2027-04-06; 2027-10-06 |

### `intent.classify` (Brief 39 step: the query plan; the acts grammar)

| Message | Today | Expected |
| --- | --- | --- |
| "how do I change the theme", "where is the export button", "what is memorymap", "are you an ai", "can you help me", "help" | notes | about_app (the Guide) |
| "what's new" | smalltalk | about_app (the CHANGELOG, 25c) |
| "what is 12*7", "what time is it", "translate hello to french", "what's the weather" | notes | utility (arithmetic, clock, translate; weather is "not something the app knows, and nothing leaves this computer") |
| "tell me a joke" | notes | smalltalk |
| "open settings", "go to the graph", "show me the harbor note" | notes | an act: navigate |
| "delete the boiler note", "remind me tomorrow" | notes | an act (confirm, undo) |
| "asdfgh" | notes | unknown: ask, do not search |
| "continue", "more", "why", "shorter" | notes | a follow-on (`follow_on` with history) |

### `help_chat.topics_for` (the Guide; Brief 49's manual page and Phase 6's "one engine")

| Question | Today | Expected |
| --- | --- | --- |
| "phone", "can I use it on two computers", "is my data encrypted" | no topic | the phone over HTTPS topic (Brief 40 built it); the data-dir and sync answer ("one notebook per computer today; copy the folder or a backup"); the vault and recovery key topic |
| "how do I delete my data" | Undo and the bin | the privacy topic: the data folder, uninstall, the bin |
| "how do I share a note" | Every view has an address | export `.md`, the address, the phone; one topic that says all three |
| "what is filing" | Tags and categories | a filing topic of its own once section 23 lands |

### `taxonomy.extract_categories` (Brief 39b; WORLD_CLASS 23)

Seven of fifteen everyday notes get no category: "Leg day: squats 5x5", "Lentil dal with cumin", "Harbor launch plan: ship the mobile app", "Boiler service due in March", "Meeting with Priya about pricing", "Loaf 6: 78% hydration", "Sleep: screens off at 10:30", "Watched Dune part two". "Flight to Lisbon, hotel in Porto" gives Travel twice. "Essay about cutting sentences" gives Education. The pack's 527 categories are weak on the notes a person writes most (exercise, cooking, home, sleep, films, work projects); section 23's candidate layer must add the notebook's own category vocabulary and the owner's corrections before the pack's vote, and dedupe.

### Search without a model (`GET /search`, thirty queries over the showcase; `$S/probe_search_filing.py`)

Right on 27 of 30 (typo "dentst" corrected; numbers "41", "2h50", "14th" found; phrases ranked first). Findings: the `corrected` field returns a stem, not a correction ("boiler pressur", "offlin", "readi list", "screen off", "pastei de nata"); no screen reads it today, so it is API hygiene for 25a's box, which will. Stemming equates "books" with "booked" (Dentist and Flights rank for "books"; the composer's `_stem` has the same class of fault, "news" to "new"). "quinta" ranks the note whose body says it third behind two that do not. The 40-note filing fixture was not re-measured here (the probe seeded without categories, so the corpus had nothing to learn from); `tests/test_filing_accuracy.py` is the measurement (2 wrong of 40 after triage).
