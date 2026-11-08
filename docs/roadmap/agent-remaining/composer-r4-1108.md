# composer-r4-1108: remaining list

Re-ask of the three composer audits on a reconstructed seed (about 63 notes,
rebuilt from the audit text), so some differences from the auditors' answers
are seed artefacts. The verbatim answers stayed in the session scratchpad, not
in git.

## Counts (91 rows: D 28, E 26, R3 37)

| | FIXED | PARTLY or OPEN | n/a or not re-driven |
| --- | --- | --- | --- |
| Before round 4 | 35 | 53 | 3 (D25 UI, D27, D28) |
| After round 4 | 41 | 47 | 3 |

The PARTLY/OPEN split was not made row by row (judgement), so they are one column.

## Fixed this round

- E6 budget: a limit in another note is not the budget (a0c50a10).
- R3-4 first/last note about X: ranked by day written (b5452fc9).
- E14 accents, E12 "dentist number", D15 "days until my passport expires",
  E17 date in a log extended later (df971114).

## Still open, high first

- R3-6 "number of notes about Sara" says two, "how many notes about Sara" says seven. Widening the overview regexes (composer_ask.py:256 and :544, composer_recall.py:45, composer_digest.py:670) changed nothing, so it was reverted. Find the earlier path first.
- D4 "how many words in my longest note" answers "You have 63 notes." (notebook_stats).
- "count notes about the dentist" answers the notebook total.
- D2 pin/favourite of an exact title asks "Which note".
- D3 "Lisbon vs Atlas" is not read as a compare.
- E5/D6 follow-on property ("what should I pack" after the Tokyo trip goes to the Lisbon list); the dentist chain loses its subject.
- E7 undo and untick, D10 multi-tick, E10 per-subject split, E22 lower-case "tokyo" count, E23 provenance repeats the answer.
- R3-2 lead drops the label, R3-18 time of the dentist appointment, R3-20 (Priya, weekend plans, Taxes), R3-22 "what do I need to read" named by date, R3-33 acts, R3-35 counts.
- D21 "what is my name" returns a Settings paragraph; D22 "list my checklists".
- D19, R3-36 chips and D25 UI were not measured.
- E17: on the probe's seed "when did I last run" still said "25 October 2025"; the test's seed passes, so another note in the probe seed may be the source.

## Not verified

No model ran. Reconstructed seed. Status marks are in this file only; the
audit files were not given a status column.
