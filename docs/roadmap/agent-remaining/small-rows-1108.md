# Small open rows, 2026-11-08 (smallrows1108)

Scope: open rows in `BACKLOG.md` and `*_PLAN.md` that are one or two files, under an hour, with no design decision open and no owner gate. Built, owner-decided and "needs Opus" rows are excluded below. This is a sampled survey, not an exhaustive one: `CHAT_PLAN.md` alone has about 167 open `| S |` rows, and only the ones listed here were checked against the code.

## Batch A: Appearance (Settings, Themes)

- `BACKLOG.md:1145` | Colours: JSON import/export of a palette | `frontend/js/settings.js`, `frontend/js/settings-controls.js` | Open. `LOOK_KEYS` is used only at `settings.js:1985` and `settings-data.js:973`. No look export exists. The download pattern is `downloadJson` (`frontend/js/skills.js:837`), already used for skills and personas (`settings-controls.js:844`).
- `BACKLOG.md:1147` | "Surprise me": a seeded pick of accent, palette, density | `frontend/js/settings.js` (`applySavedTheme`, line 2028), `frontend/js/settings-controls.js` | Open. `grep -i surprise frontend/js/settings*.js` finds nothing. The seam is `applySavedTheme`.
- `BACKLOG.md:1143` | Sizing: line-height and measure tokens | `frontend/css/00-tokens-shell.css`, `frontend/index.html` (Settings group near line 9355), `frontend/js/settings-controls.js` | Open, borderline: three files. No `--line-height` or `--measure` token exists in `frontend/css`, only generic `line-height` declarations.

Batch A count: 3

## Batch B: Chat composer (CHAT_PLAN deterministic rows)

- `CHAT_PLAN.md:1253` | U16 Hypotheticals: "what if I move to Lisbon" | `src/tessellate/ai/composer_ask.py` (shape regexes, lines 61 to 66), `src/tessellate/ai/composer_intent.py` | Open. `grep -rn "what if\|hypothes" src/tessellate/ai/composer*.py` finds nothing. The row asks for a new `hypothetical` kind that never states a consequence.
- `CHAT_PLAN.md:1254` | U17 Spelled numbers and ordinals in whole questions | `src/tessellate/ai/composer.py`, `src/tessellate/entry/timewords.py` | Open, partial. No `normalise()` stage exists in `src/tessellate/ai/composer*.py`. Number words are read only inside `timewords` and `reminder_parser`.
- `CHAT_PLAN.md:1282` | A22 "Where did I write X" answered in a sentence | `src/tessellate/ai/composer_body.py` (the `"where"` shape, line 45) | Open. `grep "It is in '"` over `src/tessellate/ai/` finds no sentence builder. `composer_aware.py:114` `_where` is the awareness line, not this.
- `CHAT_PLAN.md:1284` | A24 "show me something old" picks a random old note | `src/tessellate/ai/composer_voice.py`, `src/tessellate/ai/resurface.py` (`ranked` line 212, `for_day` line 257) | Open. No "something old" phrase in `src/tessellate/ai/`. The resurface seam exists.

Batch B count: 4

Batch count: 2 batches, 7 rows.

## Excluded (checked, not small or not open)

- `BACKLOG.md:1155` Live hover preview of a theme: not open. The owner decided on the eye-button preview instead of hover (`frontend/js/settings-controls.js:2971`, INBOX 1300 C21).
- `BACKLOG.md:3625` Search-result grouping by category: tagged "(needs Opus)" in the row. Excluded.
- `BACKLOG.md:1190`, `BACKLOG.md:1202` Global quick-capture hotkey: needs a new Python dependency, owner's call.
- `BACKLOG.md:1441`, `BACKLOG.md:1311` Real Ollama pull test and async httpx: need a real Ollama, or are optional pending measurement.
- `BACKLOG.md:2291` Audit-log size measurement script: tagged "(needs owner)".
- `BACKLOG.md:2148` Audio attachments: more than two files (`routes_files.py`, `note-cards.js`, Library).
- `BACKLOG.md:1763` `DELETE /notebook`: multi-file, plus a destructive-action design.
- `CHAT_PLAN.md:1298`-`1312` (X4 to X18): mostly built. `commands.py:45` `VERBS` already includes file, rename, pin, delete, add, summarise, open and cancel. `task_acts.py:187` `_CANCEL_LEADS` handles "never mind". `commands.py` and `reading.py` carry `CAPABILITY_LINE`. Not listed as open.
- `CHAT_PLAN.md:1277` A17 "Then and now" line: `timetravel.py` defines `Then`, but no `src/tessellate/ai` module imports it, so the wiring is unclear (see below).
- `CHAT_PLAN.md:1318` C1 greetings: "Good {tod}" and "Welcome back" exist (`composer_lines.py:256`). Only the "return after a gap" half may be open, so it is partial and not listed.

## Unclear

- Whether `timetravel.py` is wired in from `api/`: only `ai/` was grepped.
- Batch A's line-height row touches three files, which is over the two-file limit.
- The Co-Authored-By trailer: the task text named Opus 5.5, but the session attribution names Haiku 5.5. The session attribution was used.
