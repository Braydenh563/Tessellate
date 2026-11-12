# composerA 1112: remaining list

Rows done (ledger-1112.md, headings Co1; Co1, Co2; composer-acts, -asks, -chat, -chips, -dialogue, -parity), each with a
test in `tests/test_composer_pa_*_1112.py` and a commit that names it:

- O4, O6, D23 (twice), F3: 29f06b285 (a reopened chat keeps its frame and objects; typed undo wording widened).
- F4: 49300e03a, 71f591ebd. F8: 41ed536f5. G11: 6f42341a5. F5: 3d8b1ff47. D10: dc0cdea76.
- F13: c83e19460, 5c5dff575. X4: ea5a6427d (B24, B26 Q5, B27 pinned on the chat route). P25: F8, F9, F13 h and i, b65de09f2.
- F1, PAR1: 5b5f6f6ab. P1, D28: 651624f81.

Left (one item):

- P1, the model-on look: the preview is now gated on the support judgement (`chat_chips.shows_first`), tested with the
  fake transport; whether a real model's first token still replaces a shown draft cleanly needs a real model
  (`scratchpad/llama-dev.sh serve`, then `pytest -m evals`).

Seen while working, not in the ledger (no row, no owner call needed):

- A three-way "which is oldest" over notes with little in common ("feeling pretty tired today", "landlord called back",
  "Shopping") retrieves only the best matching note by the sentence, so the answer names the other two as missing; two
  sides work. A follow-on that carried the cited note ids into the compare would fix it (`reading._follow_place` makes
  the sentence; `chat_turn._framed_scope` binds ids).
- "which is oldest, Shopping or Todo" answers with the Shopping checklist line, not a date comparison.
