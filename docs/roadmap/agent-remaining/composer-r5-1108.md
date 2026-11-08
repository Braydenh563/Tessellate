# composer-r5-1108: remaining list

Round 5 of the composer audits (rows left open in `composer-r4-1108.md`). Branch
`agent/composer-r5-1108`. Probed through `/chat/stream` (fixed clock, no model) on the
`tests/_seed_r2_1107.py` notebook plus a Sara, Gym and Atlas set (`tests/_r5_1108.py`), so
some differences from the auditors' answers are seed artefacts.

## Done

- Counting family R3-6, D4: the topic pool was built only for "how many notes about X"
  (`composer_overview._ASKS`), so "number of notes about X" counted the five likest notes;
  "count notes about X" ran the count tool (`act_registry` cue); "how many words in my longest
  note" fell to the notebook total (`notebook_stats.answer`).

## Next

- D3, D2, E5/D6, then E7, D10, E10, E22, E23, R3-2, R3-18, R3-20, R3-22, R3-33, R3-35, D21, D22.
