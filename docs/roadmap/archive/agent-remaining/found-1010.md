# Found agent (Brief 64, F0): the foundation, measured

Head: `gemini/composer-improvements` at 79d82a486, 2026-10-10. Measurements
only, no fixes. Scripts: `scratchpad/reader_count.py` (step 1), the probe
scripts of step 2, `scratchpad/variety_metric.py` (step 3).

## 1. The reader count (`python scratchpad/reader_count.py --lines`)

A reader turns date or unit words into a value; a mention is the same word in
copy, a help topic or a prompt. Method: Python files are read with `ast` (a
string constant with regex syntax and a date word, or a unit word beside a
number, in a file that imports `re`; a table of three or more weekday or unit
names; a membership test against one date word), JavaScript files with a
regex-literal and `new RegExp` scan. `src/memorymap/vendor/`, comments and
docstrings are skipped; `ai/recognise.py` (not yet written) and
`entry/timewords.py` are the two allowed readers.

**Ratchet today: 6 files** outside the allowed two (5 compile a pattern, 1
tests date words by substring). `frontend/js`: 0 readers.

| File | Line | Verdict |
| --- | --- | --- |
| `ai/when.py` | 93-95, 99, 228-239, 292 | reader: `resolve`, `parse_reminder_text`, `_AGO` |
| `ai/reminder_parser.py` | 64 (and `parse_relative`) | reader: "in 30 mins" to a datetime |
| `search/query.py` | 120-130 (`_RANGE_RULES`) | reader: today, yesterday, this and last week, month, year, "N units back" to a range |
| `ai/notebook_stats.py` | 243 (`_recent_count`, 415) | reader: "this week", "past month" to seven or thirty days |
| `api/routes_vision.py` | 285-299 (`_period`) | reader by substring: "this week" in text to a range |
| `ai/composer.py` | 820 (`_DATE_CUE`, used at 843, 1483) | cue, no value: marks a sentence as dated, beside calls to `when.resolve` |

Not readers, listed by the scan: `ai/question_noise.py:42` ("hr", "hrs",
"mins" in the slang map), `ai/source_check.py:35` (weekday and month names in
a stop list of non-names). Mentions only: 46 files (the 17 under
`src/memorymap` are prompts, help topics, error copy and tool cue tuples,
for example `ai/tools/__init__.py:3843`; the 29 in `frontend/js` are copy and
`toLocale*` options), none to move.

Findings:
- **No unit reader exists.** Nothing in `src/memorymap` or `frontend/js`
  parses km, miles, kg, lb, celsius or fahrenheit; "convert 5 miles to km"
  (probe P9) has no code behind it. The only unit patterns are minutes and
  hours inside `when.py` and `reminder_parser.py`.
- **Five date readers, not four.** CHAT_PLAN section 1 names `when.resolve`,
  `parse_relative`, `timewords.find`, `search/query` and the composer; the scan
  adds `notebook_stats._recent_count` and `routes_vision._period`, each with
  its own "this week" and "last month", which neither resolves "last friday".
- Frontend presets (`presetDate("tomorrow")` in `shell-reminders.js`,
  `library.js`) pick a date from a menu choice; they read no text.

## 2. The probe tables re-run on the merged head (Brief 64 step 2)

`probe_determ.py` (now = Tue 2026-10-06 14:30) run from this worktree on
79d82a486, the same inputs as `engine-probe-1010.md` part 2. "Before" is that
file's Today column. `git log dc2cb8e69..HEAD` over `ai/when.py`, `intent.py`,
`reminder_parser.py`, `help_chat.py`, `help_topics_more.py`, `taxonomy.py`,
`entry/timewords.py` and `search/query.py` is empty: **nothing these tables
read has changed on the merged head, so every row is identical to the probe.**
The third column is the engine agent's worktree (`agent/engine-1010`, two
commits plus uncommitted edits, not merged), run the same way, so Brief 65 knows
what Brief 39 already moved.

| Table | Rows wrong before | Wrong on merged head | Wrong in the engine worktree |
| --- | --- | --- | --- |
| `when.resolve` (44 phrases) | 23 (the probe's 11 right rows still right) | 23 | 6 ("in march" wrong date, "march", "2/11", "11/2" None, and "next month" and "later today" differ from the probe's expected values) |
| `parse_reminder_text` (11 phrases) | 5 wrong: "water the plants every tuesday", "every morning at 7 stretch", "dentist 21st 9am", "pay rent on the 1st", "remind me in 20 minutes to check the oven" | 5 | 4 ("pay rent on the 1st" now resolves to 2026-11-01; no monthly offer) |
| `parse_relative` (9 phrases) | 4 None: "in 1.5 hours", "tomorrow morning", "in 6 months", "in a year" | 4 | 4 |
| `intent.classify` (40 messages) | 22 not the expected class | 22 | 22 ("are you an ai" moved from notes to smalltalk, expected about_app) |
| `help_chat.topics_for` (25 questions) | 6 gaps: phone, two computers, encrypted, delete my data, share a note, what is filing | 6 | 6 (identical output) |
| `taxonomy.extract_categories` (15 notes) | "seven of fifteen" in the probe text, which names eight | 8 of 15 get none, "Flight to Lisbon, hotel in Porto" gives Travel twice, "Essay about cutting sentences" gives Education | 8, same |

Engine worktree, `when.resolve` rows that moved (merged head, then worktree):
"last friday" 2026-10-09 to 2026-10-02 (right); "yesterday", "a week ago",
"3 weeks ago", "the week before last" None to 10-05, 09-29, 09-15, 09-21 (right);
"the 21st", "on the 14th", "21st of next month", "end of the month", "next
month", "end of day", "this weekend", "next weekend", "in a fortnight",
"christmas", "new year", "mid november" None to the probe's expected values
("next month" gives 2026-11-01 09:00 as a point; the probe wanted a window;
"later today" 09:00 to 17:30 where the probe wanted now plus three hours,
capped at 20:00). Still wrong there: **"in march" resolves to 2027-03-01 (the
next March; the probe's expected value is the most recent, 2026-03)**, "march"
alone, "2/11", "11/2", "q4" and "on my birthday" stay None. Two rows no
probe table listed: "q4" and "on my birthday" (None everywhere; the first is
a quarter, the second needs a stored birthday).

Found, not fixed: the probe's "seven of fifteen" taxonomy count is eight by its
own list; the engine worktree changes `when` while Brief 65 plans
`recognise.py` over the same words, so the two must be sequenced (Brief 65 says
"land the modules first, the delegation second"; the worktree is already on the
delegation side).

## 3. The variety metric and the maxims count (Brief 64 step 3)

`PYTHONPATH=src:. python scratchpad/variety_metric.py`, built on
`tests/_composer_eval.py` (`run`, `notes_for`, `opener`) and
`fixtures/composer/showcase_725.json`. Ten of the 25 questions (who, count,
compare, yesno, what, explain, what, count, status, list), each asked twenty
times in three conditions. An opener is the answer's first worded template
phrase ("Diving into your notes: "), or "(quote)" when the answer starts with
the person's own sentence. Facts are the quote, title and filed parts in
order, compared with the first letter's case folded (the composer lowers it
after a joiner: "Three gates" and "three gates" are one fact).

**What `_pick` takes.** `_pick(question, salt, options)` hashes the question
and a fixed salt string; `compose` has no chat or turn input. The only inputs
that change between two asks of one question are `previous` (the turn before's
answer, so the opener differs from it) and `said` (a follow-up, which changes
the facts, so it is not a variety input). Hence three conditions:

- **as shipped**: twenty identical calls.
- **previous**: a twenty-turn chat, each call given the turn before's answer.
- **salted**: `_pick`'s salt argument carries the turn number, as the F3
  realiser will salt per chat and turn; this measures the pool of options.

| Question | Shape | Openers, as shipped | Openers, previous (distinct texts) | Openers, salted (distinct texts) | Distinct fact sets, salted |
| --- | --- | --- | --- | --- | --- |
| Who asked for a public API? | who | 1 | 2 (2) | 3 (3) | 1 |
| How many beta testers are active? | count | 1 | 3 (3) | 3 (3) | 1 |
| Compare Lisbon and Porto | compare | 1 | 2 (2) | 1 (1) | 1 |
| Does Harbor work offline? | yesno | 1 | 2 (2) | 1 (3) | 1 |
| What do I know about sourdough? | what | 1 | 1 (2) | 1 (16) | 1 |
| How do I sharpen my knife? | explain | 1 | 2 (2) | 3 (3) | 1 |
| What is my half marathon training plan? | what | 1 | 3 (3) | 3 (3) | 1 |
| How much will the trip cost? | count | 1 | 3 (3) | 3 (3) | 1 |
| What is the status of the onboarding rewrite? | status | 1 | 2 (2) | 3 (3) | 1 |
| Which dinners take under 30 minutes? | list | 1 | 2 (2) | 3 (3) | 1 |

Mean distinct openers of twenty: **1.0 as shipped, 2.2 with `previous`, 2.4
salted; the most any question gave is 3.** The quoted facts are identical across
the twenty for 10 of 10 questions in every condition. Four questions are stuck
at one salted opener (compare and yesno have a fixed lead; the sourdough answer
opens with a measure, "At least three of your notes", and varies only its
joins, 16 distinct texts). The plan's floor of eight distinct openers in
twenty is out of reach of today's pools (three lead variants per shape).

**Maxims over the 25 eval answers as shipped** (169 sentences; sentences are
split at ". ? :" and line breaks, markdown marks off; the detail lines are in
the script's output):

| Maxim | Count | Reading |
| --- | --- | --- |
| Sentence with more than one number, app's own words | 6 | "Its checklist has two of four done:", "one mentions Lisbon and two mention Porto", "At least three of your notes mention ... from 3 September to 4 October", and three dated lead-ins ("Long before that, on 12 September, three workstreams:") |
| Sentence with more than one number, the note's quoted sentence | 16 | "Lisbon to Porto on the Alfa Pendular, 2h50.", "78% hydration, 20 hour cold proof."; the app cannot edit these |
| Number with no source span (in a template or measure part, so no grounding row points at it) | 19 numbers in 15 sentences | counts and dates the app computed: "lists four", "from 14 September", "(two notes)". Rule 5 allows measures, the lint will need to say which are computed |
| Sentence repeating another's fact (stem Jaccard 0.5 or more) | 0 answers; highest pair 0.42 | no answer says a thing twice by this measure |
| Answers quoting one sentence twice | 0 | |

Not verified: the openers are counted from the composer's parts, not read as
prose by a person; "three variants per shape" is read from the measured
maximum, not from the option lists; the three conditions are an experiment on
`_pick`, and the real route supplies no turn salt today (checked: the answer
call in `routes_chat.py` passes `said`, `voice`, `embed` and `previous` from
the history, never a turn or chat id, so the "previous" column is what a
real twenty-turn chat gives).
